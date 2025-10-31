import cv2
import time
from typing import Optional
from src.db.sqlite import DB
from src.detectors.vehicle_detector import VehicleDetector
from src.detectors.plate_detector import PlateDetector
from src.selector.best_frame_selector import OnlineBestFrameSelector
from src.score.score import score_quality
from src.tracker.sort.sort import Sort
from src.common_utils.video_loader import VideoLoader
from src.common_utils.config import Config, MyConfig
from src.common_utils.app_logger import get_logger
from src.common_utils.resource_path import get_resource_path
import numpy as np

logger = get_logger("detect", logfile="logs/app.jsonl")


def run_plate_detection():
    """Main function that runs continuously, handling video input failures gracefully"""
    conf: MyConfig = Config().config
    db = DB()

    # Initialize components
    vehicle_detector = VehicleDetector(
        get_resource_path("res/models/vehicle_detector_yolov11n.pt"),
        [
            1,  # Bicycle
            2,  # car
            3,  # motorcycle
            5,  # bus
            7,  # truck
        ],
    )
    detector_plate = PlateDetector(
        get_resource_path("res/models/license_plate_detector.pt"), ["license_plate"]
    )
    tracker = Sort(max_age=120, min_hits=1, iou_threshold=0.3)
    selector = OnlineBestFrameSelector(
        db,
        score_quality,
        no_improve_patience=conf.get("no_improve_patience", 20),
        track_timeout=conf.get("track_timeout", 15),
    )

    logger.info("Starting continuous plate detection service...")

    frame_skip = max(conf.get("frame_skip", 1), 1)  # always ≥1
    rotation_angle = float(conf.get("rotation_angle", 0) or 0)
    hot_zone_def = conf.get("hot_zone")
    hot_zone_mask = None
    cached_mask_shape = None
    car_detection_threshold = conf.get("car_detection_threshold")
    plate_detection_threshold = conf.get("plate_detection_threshold")
    rotation_cache = {"shape": None, "matrix": None}

    try:
        # Continuous Monitoring
        while True:
            try:
                logger.info("Initializing video loader...")
                loader = VideoLoader(
                    conf.get("video_path"),
                    retry_delay=conf.get("video_retry_delay", 5),
                    max_retry_delay=conf.get("video_max_retry_delay", 60),
                )

                frame_index = 0

                logger.info("Starting video processing...")
                # region Processing
                for frame in loader:
                    try:
                        if frame is None:
                            logger.warning("Empty frame received from loader")
                            continue

                        if rotation_angle:
                            frame = rotate_frame(frame, rotation_angle, rotation_cache)

                        # region Validate
                        if not frame.any() or frame.mean() < 5:  # near black
                            logger.warning("Black frame detected, camera may be dead")
                            continue
                        frame_index += 1
                        if frame_index % frame_skip != 0:
                            continue
                        # endregion

                        # region Hotzone
                        if hot_zone_def:
                            h, w = frame.shape[:2]
                            if cached_mask_shape != (h, w):
                                hot_zone_mask = np.zeros((h, w), dtype=np.uint8)
                                cv2.fillPoly(
                                    hot_zone_mask,
                                    [
                                        np.array(
                                            [
                                                (int(p["x"] * w), int(p["y"] * h))
                                                for p in hot_zone_def
                                            ],
                                            dtype=np.int32,
                                        )
                                    ],
                                    255,
                                )
                                cached_mask_shape = (h, w)

                            roi = cv2.bitwise_and(frame, frame, mask=hot_zone_mask)
                        else:
                            roi = frame

                        # endregion

                        # region Detect
                        try:
                            vehicles = vehicle_detector.detect(
                                roi, conf_threshold=car_detection_threshold
                            )
                            if vehicles.size == 0:
                                continue
                        except Exception as e:
                            logger.error(
                                f"Vehicle detection failed at frame {frame_index}: {e}"
                            )
                            continue
                        # endregion

                        # region Track
                        tracked = tracker.update(vehicles)
                        if tracked.size == 0:
                            continue
                        tracked_vehicles = [
                            {"id": int(trk[4]), "bbox": tuple(map(int, trk[:4]))}
                            for trk in tracked
                        ]
                        # Update tracker IDs to UUIDs
                        tracked_vehicles = [
                            vehicle_detector.get_uuid(trk) for trk in tracked_vehicles
                        ]
                        if not tracked_vehicles:
                            continue
                        active_boxes = {
                            trk["id"]: trk["bbox"] for trk in tracked_vehicles
                        }

                        active_ids = (
                            set()
                        )  # TODO POST MVP remove and use the internal selector tracking
                        # show(draw_boxes(frame.copy(), tracked_vehicles), "Vehicle Tracked")
                        vehicle_crops = []
                        crop_meta = []
                        # endregion

                        # region Selection
                        for t in tracked_vehicles:
                            vuuid = t["id"]
                            active_ids.add(vuuid)
                            selector.mark_seen(vuuid, frame_index, frame)
                            vehicle_crop_bbox = t.get("bbox")
                            if not vehicle_crop_bbox:
                                continue
                            x1, y1, x2, y2 = vehicle_crop_bbox
                            vehicle_crop = frame[y1:y2, x1:x2]
                            if vehicle_crop.size == 0:
                                continue
                            vehicle_crops.append(vehicle_crop)
                            crop_meta.append(
                                {
                                    "id": vuuid,
                                    "vehicle_bbox": vehicle_crop_bbox,
                                    "vehicle_crop": vehicle_crop,
                                }
                            )

                        if vehicle_crops:
                            plates_batch = detector_plate.detect_batch(
                                vehicle_crops,
                                conf_threshold=plate_detection_threshold,
                            )

                            # region Score plate(s)
                            for meta, plates in zip(crop_meta, plates_batch):
                                if not plates:
                                    continue

                                for plate in plates:
                                    try:

                                        plate_bbox = plate.get("bbox")
                                        if not plate_bbox:
                                            continue
                                        vehicle_crop = meta["vehicle_crop"]
                                        px1, py1, px2, py2 = shrink_box(*plate_bbox)
                                        plate_crop = vehicle_crop[py1:py2, px1:px2]
                                        if plate_crop.size == 0:
                                            continue

                                        selector.update(
                                            meta["id"],
                                            plate_crop,
                                            frame_index,
                                            full_frame=frame,
                                            vehicle_bbox=meta.get("vehicle_bbox"),
                                        )
                                    except Exception as e:
                                        logger.error(
                                            f"Error processing plate for vehicle {meta.get('id')}: {e}"
                                        )
                                        continue
                            # endregion

                        # endregion

                        # region Finalize
                        to_finalize = selector.to_finalize(
                            active_ids, frame_index, active_boxes=active_boxes
                        )
                        if len(to_finalize):
                            for vuuid in to_finalize:
                                selector.finalize(vuuid)
                        # endregion

                    except Exception as e:
                        logger.error(f"Error processing frame {frame_index}: {e}")
                        continue
                # endregion
            except KeyboardInterrupt:
                logger.info("Received shutdown signal, stopping gracefully...")
                break
            except Exception as e:
                logger.error(f"Video processing failed: {e}")
                logger.info("Restarting video processing in 1 seconds...")
                time.sleep(1)  # Wait before retrying
    finally:
        # Cleanup
        logger.info("Shutting down plate detection service...")
        db.close()
        logger.info("Plate detection service stopped.")


# Shrink box by a fixed margin percentage
def rotate_frame(
    frame: np.ndarray, angle: float, cache: Optional[dict] = None
) -> np.ndarray:
    """Rotate frame around its center, keeping original dimensions. Cache the transform per frame size."""
    if not angle:
        return frame
    if cache is None:
        cache = {}

    (h, w) = frame.shape[:2]
    if cache.get("shape") != (h, w):
        center = (w / 2, h / 2)
        cache["matrix"] = cv2.getRotationMatrix2D(center, angle, 1.0)
        cache["shape"] = (h, w)

    rotation_matrix = cache["matrix"]
    rotated = cv2.warpAffine(
        frame,
        rotation_matrix,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated


def shrink_box(x1, y1, x2, y2):
    w = x2 - x1
    h = y2 - y1
    dxl = int(w * 0.14)
    dxr = int(w * 0.06)
    dy = int(h * 0.23)
    return x1 + dxl, y1 + dy, x2 - dxr, y2 - dy
