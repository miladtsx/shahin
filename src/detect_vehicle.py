import numpy as np
from src.detectors.vehicle_detector import VehicleDetector
from src.detectors.plate_detector import PlateDetector
from src.selector.best_frame_selector import OnlineBestFrameSelector
from src.score.score import score_quality
from src.tracker.sort.sort import Sort
from src.common_utils.video_loader import VideoLoader
from src.common_utils.config import Config


def run_plate_detection():
    conf = Config().config

    output_dir = conf.get("detected_plates_dir")

    # Init
    loader = VideoLoader(conf.get("video_path"))
    detector_vehicle = VehicleDetector(
        conf.get("model_vehicle"), conf.get("vehicle_classes")
    )
    detector_plate = PlateDetector(conf.get("model_plate"), conf.get("plate_classes"))
    tracker = Sort()
    selector = OnlineBestFrameSelector(score_quality, output_dir)

    frame_count = 0
    for frame in loader:
        if frame_count % conf.get("frame_skip", 1) != 0:
            frame_count += 1
            continue

        # 1. Detect & Track Vehicles
        vehicles = detector_vehicle.detect(
            frame, conf_threshold=conf["car_detection_threshold"]
        )
        if not vehicles or not len(vehicles):
            continue

        # Track vehicles
        # Convert to numpy array for SORT tracker
        # Each vehicle is represented as [x1, y1, x2, y2, score]
        # where (x1, y1) is the top-left corner and (x2, y2) is the bottom-right corner
        # score is the confidence score of the detection
        dets_np = np.array(vehicles, dtype=np.float64).reshape(-1, 5)
        tracked = tracker.update(dets_np)

        # Convert to dict format
        tracked_dicts = []
        for trk in tracked:
            x1, y1, x2, y2, track_id = map(int, trk)
            tracked_dicts.append({"id": track_id, "bbox": (x1, y1, x2, y2)})

        active_ids = set()
        for vehicle in tracked_dicts:
            vid = vehicle["id"]
            active_ids.add(vid)
            selector.mark_seen(vid)
            x1, y1, x2, y2 = vehicle["bbox"]
            vh_crop = frame[y1:y2, x1:x2]

            # 2. Detect Plate inside Vehicle Crop
            plates = detector_plate.detect(
                vh_crop, conf_threshold=conf.get("plate_detection_threshold")
            )
            if not plates:
                continue

            plate_crop = None
            best_score = -1
            best_crop = None
            for plate in plates:
                px1, py1, px2, py2 = plate["bbox"]
                pw, ph = px2 - px1, py2 - py1

                px1, py1, px2, py2 = shrink_box(px1, py1, px2, py2)
                plate_crop = vh_crop[py1:py2, px1:px2]
                if plate_crop.size == 0:
                    continue  # Avoid passing empty arrays to imshow

                if pw * ph < int(conf.get("crop_dimension_threshold", 0)):
                    continue  # skip tiny plates

                # Sanity check plate aspect ratio:
                aspect_ratio = pw / ph
                if aspect_ratio < 1.5 or aspect_ratio > 6.0:
                    continue

                if plate_crop.size == 0:
                    continue

                score = score_quality(plate_crop)

                # print(
                #     f"[Vehicle {vid} | Frame {frame_count}] Plate crop size: {plate_crop.shape[:2]}, Score: {score:.2f}"
                # )

                if score > best_score:
                    best_score = score
                    best_crop = plate_crop

            if best_crop is not None:
                score, improved = selector.update(vid, best_crop, frame_count)
                # if improved:
                #     print(
                #         f"[Vehicle {vid} | Frame {frame_count}] ✅ improved to {best_score:.2f}"
                #     )

            # check which tracks to finalize this frame
            to_finalize = selector.step_end(active_ids, frame_count)
            for vid in to_finalize:
                # TODO do it asyncronously
                selector.finalize(vid)

        frame_count += 1

# Shrink box by a fixed margin percentage
def shrink_box(x1, y1, x2, y2, shrink_ratio=0.5):
    w = x2 - x1
    h = y2 - y1
    dxl = int(w * 0.14)
    dxr = int(w * 0.06)
    dy = int(h * 0.23)
    return x1 + dxl, y1 + dy, x2 - dxr, y2 - dy
