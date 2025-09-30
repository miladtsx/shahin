import cv2
import time
from src.db.sqlite import DB
from src.detectors.vehicle_detector import VehicleDetector
from src.detectors.plate_detector import PlateDetector
from src.selector.best_frame_selector import OnlineBestFrameSelector
from src.score.score import score_quality
from src.tracker.sort.sort import Sort
from src.common_utils.video_loader import VideoLoader
from src.common_utils.config import Config
from src.common_utils.app_logger import get_logger, log_duration
from concurrent.futures import ThreadPoolExecutor
from src.common_utils.resource_path import get_resource_path, get_data_path
from src.common_utils.image_save import save
from src.common_utils.debug_image import show

logger = get_logger("detect", logfile="logs/app.jsonl")


def run_plate_detection():
    """Main function that runs continuously, handling video input failures gracefully"""
    conf = Config().config
    db = DB()

    # Initialize components
    detector_vehicle = VehicleDetector(
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
    tracker = Sort()
    selector = OnlineBestFrameSelector(score_quality)
    executor = ThreadPoolExecutor(max_workers=8)

    logger.info("Starting continuous plate detection service...")

    # Continuous operation loop
    while True:
        try:
            logger.info("Initializing video loader...")
            loader = VideoLoader(
                conf.get("video_path"),
                retry_delay=conf.get("video_retry_delay", 5),
                max_retry_delay=conf.get("video_max_retry_delay", 60),
            )

            frame_count = 0
            original_frame = None

            logger.info("Starting video processing...")
            for frame in loader:
                if not frame.any() or frame.mean() < 5:  # near black
                    logger.warning("Black frame detected, camera may be dead")
                    continue
                frame_count += 1
                if frame_count % conf.get("frame_skip", 1) != 0:
                    continue

                # 1. Detect vehicles
                try:
                    # with log_duration(logger, "detect_vehicles", frame=frame_count):
                    vehicles = detector_vehicle.detect(
                        frame, conf_threshold=conf["car_detection_threshold"]
                    )
                    if vehicles.size == 0:
                        continue
                except Exception as e:
                    logger.error(
                        f"Vehicle detection failed at frame {frame_count}: {e}"
                    )
                    continue

                # 2. Track vehicles
                try:
                    tracked = tracker.update(vehicles)
                    tracked_vehicles = [
                        {"id": int(trk[4]), "bbox": tuple(map(int, trk[:4]))}
                        for trk in tracked
                    ]
                except Exception as e:
                    logger.error(f"Vehicle tracking failed at frame {frame_count}: {e}")
                    continue

                active_ids = set()
                vehicle_crops = []
                vehicle_ids = []

                # 3. Prepare crops
                for trk in tracked_vehicles:
                    vid = trk["id"]
                    active_ids.add(vid)
                    selector.mark_seen(vid)
                    x1, y1, x2, y2 = trk["bbox"]
                    car_crop = frame[y1:y2, x1:x2]
                    original_frame = frame
                    if car_crop.size > 0:
                        vehicle_crops.append(car_crop)
                        vehicle_ids.append(vid)

                # 4. Batch plate detection (only for vehicles with valid crops)
                plates_batch = []
                if vehicle_crops:  # Only run plate detection if we have valid crops
                    try:
                        plates_batch = detector_plate.detect_batch(
                            vehicle_crops,
                            conf_threshold=conf.get("plate_detection_threshold"),
                        )
                    except Exception as e:
                        logger.error(
                            f"Plate detection failed at frame {frame_count}: {e}"
                        )
                        plates_batch = [
                            [] for _ in vehicle_crops
                        ]  # Empty results for all vehicles

                # 5. Process detected plates
                for vid, plates, vh_crop in zip(
                    vehicle_ids, plates_batch, vehicle_crops
                ):
                    if not plates:
                        continue

                    # Process all valid plates and let OnlineBestFrameSelector handle quality evaluation
                    for plate in plates:
                        try:
                            px1, py1, px2, py2 = shrink_box(*plate["bbox"])

                            plate_crop = vh_crop[py1:py2, px1:px2]
                            if plate_crop.size == 0:
                                continue

                            pw, ph = px2 - px1, py2 - py1
                            if pw * ph < int(conf.get("crop_dimension_threshold", 0)):
                                continue
                            aspect_ratio = pw / ph
                            if aspect_ratio < 1.5 or aspect_ratio > 6.0:
                                continue

                            # Let OnlineBestFrameSelector handle quality evaluation
                            selector.update(vid, plate_crop, frame_count, db, executor)
                        except Exception as e:
                            logger.error(
                                f"Error processing plate for vehicle {vid}: {e}"
                            )
                            continue

                # 6. Finalize tracks once per frame
                try:
                    to_finalize = selector.step_end(active_ids, frame_count)
                    if len(to_finalize):
                        print("Finalizing tracks:", to_finalize)
                        for vid in to_finalize:
                            save(original_frame, vid, "original")
                            executor.submit(selector.finalize, db, vid)
                except Exception as e:
                    logger.error(
                        f"Track finalization failed at frame {frame_count}: {e}"
                    )

        except Exception as e:
            logger.error(f"Video processing failed: {e}")
            logger.info("Restarting video processing in 10 seconds...")
            time.sleep(10)  # Wait before retrying

        except KeyboardInterrupt:
            logger.info("Received shutdown signal, stopping gracefully...")
            break

    # Cleanup
    logger.info("Shutting down plate detection service...")
    executor.shutdown(wait=True)
    db.close()
    logger.info("Plate detection service stopped.")


# Shrink box by a fixed margin percentage
def shrink_box(x1, y1, x2, y2, shrink_ratio=0.5):
    w = x2 - x1
    h = y2 - y1
    dxl = int(w * 0.14)
    dxr = int(w * 0.06)
    dy = int(h * 0.23)
    return x1 + dxl, y1 + dy, x2 - dxr, y2 - dy


def draw_boxes(frame, detections, color=(0, 255, 0), label="obj"):
    """
    detections: list of dicts with 'bbox' and optional 'conf'
    bbox format: (x1, y1, x2, y2)
    """
    for det in detections:
        x1, y1, x2, y2 = map(int, det["bbox"])
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        txt = f"{det['id']}"
        if "conf" in det:
            txt += f" {det['conf']:.2f}"

        # small text above box
        cv2.putText(frame, txt, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # large text inside box (centered)
        text_size, _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)
        text_w, text_h = text_size
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        cv2.putText(
            frame,
            txt,
            (cx - text_w // 2, cy + text_h // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            color,
            3,
        )
    return frame
