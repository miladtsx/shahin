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

logger = get_logger("detect", logfile="logs/app.jsonl")


def run_plate_detection():
    conf = Config().config
    db = DB()

    # Init
    with log_duration(logger, "init_components"):
        loader = VideoLoader(conf.get("video_path"))
        detector_vehicle = VehicleDetector(
            get_resource_path("res/models/vehicle_detector_yolov11n.pt"),
            [
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
        executor = ThreadPoolExecutor(max_workers=4)

    frame_count = 0
    try:
        original_frame = None
        for frame in loader:
            frame_count += 1
            if frame_count % conf.get("frame_skip", 1) != 0:
                continue

            # 1. Detect vehicles
            # with log_duration(logger, "detect_vehicles", frame=frame_count):
            vehicles = detector_vehicle.detect(
                frame, conf_threshold=conf["car_detection_threshold"]
            )
            if vehicles.size == 0:
                continue

            # 2. Track vehicles
            tracked = tracker.update(vehicles)
            tracked_dicts = [
                {"id": int(trk[4]), "bbox": tuple(map(int, trk[:4]))} for trk in tracked
            ]

            active_ids = set()
            vehicle_crops = []
            vehicle_ids = []

            # 3. Prepare crops
            for trk in tracked_dicts:
                vid = trk["id"]
                active_ids.add(vid)
                selector.mark_seen(vid)
                x1, y1, x2, y2 = trk["bbox"]
                crop = frame[y1:y2, x1:x2]
                original_frame = frame
                if crop.size > 0:
                    vehicle_crops.append(crop)
                    vehicle_ids.append(vid)

            # 4. Batch plate detection
            plates_batch = detector_plate.detect_batch(
                vehicle_crops, conf_threshold=conf.get("plate_detection_threshold")
            )

            # 5. Process detected plates
            for vid, plates, vh_crop in zip(vehicle_ids, plates_batch, vehicle_crops):
                if not plates:
                    continue
                best_crop = None
                best_score = -1

                for plate in plates:
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

                    score = score_quality(plate_crop)
                    if score > best_score:
                        best_score = score
                        best_crop = plate_crop

                if best_crop is not None:
                    score, improved = selector.update(vid, best_crop, frame_count)

            # 6. Finalize tracks once per frame
            to_finalize = selector.step_end(active_ids, frame_count)
            for vid in to_finalize:
                save(original_frame, vid, "original")
                executor.submit(selector.finalize, db, vid)
    except Exception as e:
        logger.exception(f"run_plate_detection_failed: {e}")
    finally:
        logger.info(
            "run_plate_detection_finished",
            extra={"event": "run_plate_detection_finished"},
        )
        executor.shutdown(wait=True)
        db.close()


# Shrink box by a fixed margin percentage
def shrink_box(x1, y1, x2, y2, shrink_ratio=0.5):
    w = x2 - x1
    h = y2 - y1
    dxl = int(w * 0.14)
    dxr = int(w * 0.06)
    dy = int(h * 0.23)
    return x1 + dxl, y1 + dy, x2 - dxr, y2 - dy
