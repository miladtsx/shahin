import cv2
import time
from src.db.sqlite import DB
from src.detectors.vehicle_detector import VehicleDetector
from src.detectors.plate_detector import PlateDetector
from src.selector.best_frame_selector import OnlineBestFrameSelector
from src.score.score import score_quality
from src.tracker.sort.sort import Sort
from src.common_utils.video_loader import VideoLoader
from src.common_utils.config import Config, MyConfig
from src.common_utils.app_logger import get_logger, log_duration
from concurrent.futures import ThreadPoolExecutor
from src.common_utils.resource_path import get_resource_path, get_data_path
from src.common_utils.debug_image import show, draw_boxes
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
    executor = ThreadPoolExecutor(max_workers=8)

    logger.info("Starting continuous plate detection service...")

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

            frame_skip = max(conf.get("frame_skip", 1), 1)  # always ≥1

            logger.info("Starting video processing...")
            # region Processing
            for frame in loader:
                try:
                    # region Validate
                    if not frame.any() or frame.mean() < 5:  # near black
                        logger.warning("Black frame detected, camera may be dead")
                        continue
                    frame_index += 1
                    if frame_index % frame_skip != 0:
                        continue
                    # endregion

                    # region Hotzone
                    hot_zone = conf.get("hot_zone")
                    if hot_zone:
                        h, w = frame.shape[:2]
                        # Convert normalized points to pixel coordinates
                        hot_zone_pts = [
                            (int(p["x"] * w), int(p["y"] * h)) for p in hot_zone
                        ]

                        # Create a mask for the polygon
                        mask = np.zeros((h, w), dtype=np.uint8)
                        cv2.fillPoly(
                            mask, [np.array(hot_zone_pts, dtype=np.int32)], 255
                        )

                        # Apply mask to frame
                        roi = cv2.bitwise_and(frame, frame, mask=mask)

                    else:
                        hot_zone_pts = []
                        roi = frame

                    # endregion

                    # region Detect
                    try:
                        vehicles = vehicle_detector.detect(
                            roi, conf_threshold=conf["car_detection_threshold"]
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
                    active_boxes = {trk["id"]: trk["bbox"] for trk in tracked_vehicles}

                    active_ids = (
                        set()
                    )  # TODO POST MVP remove and use the internal selector tracking
                    # show(draw_boxes(frame, tracked_vehicles), "Vehicle Tracked")
                    # endregion

                    # region Selection
                    for t in tracked_vehicles:
                        vuuid = t["id"]
                        active_ids.add(vuuid)
                        selector.mark_seen(vuuid, frame_index, frame)
                        x1, y1, x2, y2 = t["bbox"]
                        vehicle_crops = []
                        cvc = frame[y1:y2, x1:x2]
                        if cvc.size > 0:
                            vehicle_crops.append(cvc)
                            # Batch plate detection
                            plates_batch = detector_plate.detect_batch(
                                vehicle_crops,
                                conf_threshold=conf.get("plate_detection_threshold"),
                            )

                            # region Score plate(s)
                            for plates, vh_crop in zip(plates_batch, vehicle_crops):
                                if not plates:
                                    continue

                                # Process all valid plates and let OnlineBestFrameSelector handle quality evaluation
                                for plate in plates:
                                    try:
                                        # clean cut the plate crop
                                        px1, py1, px2, py2 = shrink_box(*plate["bbox"])

                                        plate_crop = vh_crop[py1:py2, px1:px2]
                                        if plate_crop.size == 0:
                                            continue
                                        # show(plate_crop, "Plate")

                                        # Let OnlineBestFrameSelector handle quality evaluation
                                        selector.update(
                                            vuuid,
                                            plate_crop,
                                            frame_index,
                                            full_frame=frame,
                                            vehicle_crop=t.get("bbox"),
                                        )
                                    except Exception as e:
                                        # if failed to process one plate, keep processing other plates.
                                        # one failure should not bring the whole system down.
                                        logger.error(
                                            f"Error processing plate for vehicle {vuuid}: {e}"
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
                            # executor.submit(selector.finalize, db, vid)
                            selector.finalize(vuuid)
                    # endregion

                except Exception as e:
                    logger.error(f"Error processing frame {frame_index}: {e}")
                    continue
            # endregion
        # region Graceful Exit Handling
        except Exception as e:
            logger.error(f"Video processing failed: {e}")
            logger.info("Restarting video processing in 1 seconds...")
            time.sleep(1)  # Wait before retrying
        except KeyboardInterrupt:
            logger.info("Received shutdown signal, stopping gracefully...")
            break
        finally:
            # Cleanup
            logger.info("Shutting down plate detection service...")
            executor.shutdown(wait=True)
            db.close()
            logger.info("Plate detection service stopped.")
        # endregion


# Shrink box by a fixed margin percentage
def shrink_box(x1, y1, x2, y2, shrink_ratio=0.5):
    w = x2 - x1
    h = y2 - y1
    dxl = int(w * 0.14)
    dxr = int(w * 0.06)
    dy = int(h * 0.23)
    return x1 + dxl, y1 + dy, x2 - dxr, y2 - dy
