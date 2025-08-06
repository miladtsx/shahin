import os
import cv2
import numpy as np
from src.detectors.vehicle_detector import VehicleDetector
from src.detectors.plate_detector import PlateDetector
from src.selector.best_frame_selector import BestFrameSelector
from src.score.score import score_quality
from src.tracker.sort.sort import Sort
from src.io_utils.video_loader import VideoLoader


def run_plate_detection(config):

    output_dir = config["detected_plates_dir"]

    # Init
    loader = VideoLoader(config["video_path"])
    detector_vehicle = VehicleDetector(
        config["model_vehicle"], config["vehicle_classes"]
    )
    detector_plate = PlateDetector(config["model_plate"], config["plate_classes"])
    tracker = Sort()
    selector = BestFrameSelector(score_quality)
    os.makedirs(output_dir, exist_ok=True)

    frame_count = 0
    for frame in loader:
        if frame_count % config.get("frame_skip", 1) != 0:
            frame_count += 1
            continue

        # 1. Detect & Track Vehicles
        vehicles = detector_vehicle.detect(
            frame, conf_threshold=config["car_detection_threshold"]
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

        for vehicle in tracked_dicts:
            vid = vehicle["id"]
            x1, y1, x2, y2 = vehicle["bbox"]
            vh_crop = frame[y1:y2, x1:x2]

            # 2. Detect Plate inside Vehicle Crop
            plates = detector_plate.detect(
                vh_crop, conf_threshold=config["plate_detection_threshold"]
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

                if pw * ph < int(config["crop_dimension_threshold"]):
                    continue  # skip tiny plates

                # Sanity check plate aspect ratio:
                aspect_ratio = pw / ph
                if aspect_ratio < 1.5 or aspect_ratio > 6.0:
                    continue

                if plate_crop.size == 0:
                    continue

                score = score_quality(plate_crop)

                print(
                    f"[Vehicle {vid} | Frame {frame_count}] Plate crop size: {plate_crop.shape[:2]}, Score: {score:.2f}"
                )

                if score > best_score:
                    best_score = score
                    best_crop = plate_crop

            if best_crop is not None:
                selector.update(vid, best_crop)
                print(
                    f"[Vehicle {vid} | Frame {frame_count}] ✅ Best score this frame: {best_score:.2f}"
                )

            # # 3. Score Sharpness
            # if plate_crop is not None:
            #     selector.update(vid, plate_crop)

        frame_count += 1

    # 4. Save best plates
    for vid, best_plate in selector.get_best_frames().items():
        path = os.path.join(output_dir, f"Vehicle_{vid}_best_plate.jpg")
        # cv2.imshow(f"Vehicle_{vid}_best_plate.jpg", best_plate)
        # cv2.waitKey(0)  # Press any key to continue
        # cv2.destroyAllWindows()
        cv2.imwrite(path, best_plate)

    print(f"✅ Done. Saved best plate for {len(selector.best_frames)} vehicles.")

# Shrink box by a fixed margin percentage
def shrink_box(x1, y1, x2, y2, shrink_ratio=0.5):
    w = x2 - x1
    h = y2 - y1
    dxl = int(w * 0.14)
    dxr = int(w * 0.06)
    dy = int(h * 0.23)
    return x1 + dxl, y1 + dy, x2 - dxr, y2 - dy