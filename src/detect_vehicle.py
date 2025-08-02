import os
import cv2
from .detectors.vehicle_detector import VehicleDetector
from src.detectors.plate_detector import PlateDetector
from src.tracker.simple_tracker import PlateTracker
from src.selector.best_frame_selector import BestFrameSelector
from src.score.score import score_quality
from src.io_utils.video_loader import VideoLoader


def run_plate_detection(config):
    # Load config
    video_path = config["video_path"]
    output_dir = config["output_dir"]
    model_vehicle = config["model_vehicle"]
    model_plate = config["model_plate"]
    frame_skip = config.get("frame_skip", 1)
    vehicle_classes = config["vehicle_classes"]
    plate_classes = config["plate_classes"]
    # iou_threshold = config.get("iou_threshold", 0.7)

    # Init
    loader = VideoLoader(video_path)
    detector_vehicle = VehicleDetector(model_vehicle, vehicle_classes)
    detector_plate = PlateDetector(model_plate, plate_classes)
    tracker = PlateTracker()
    selector = BestFrameSelector(score_quality)
    os.makedirs(output_dir, exist_ok=True)

    frame_count = 0
    for frame in loader:
        if frame_count % frame_skip != 0:
            frame_count += 1
            continue

        # 1. Detect & Track Vehicles
        vehicles = detector_vehicle.detect(frame)
        tracked = tracker.update(vehicles, frame, frame_count)

        for vehicle in tracked:
            vid = vehicle["id"]
            x1, y1, x2, y2 = vehicle["bbox"]
            vh_crop = frame[y1:y2, x1:x2]

            # 2. Detect Plate inside Vehicle Crop
            plates = detector_plate.detect(vh_crop)
            if not plates:
                continue

            plate_crop = None
            best_score = -1
            best_crop = None
            for plate in plates:
                px1, py1, px2, py2 = plate["bbox"]
                pw, ph = px2 - px1, py2 - py1
                if pw * ph < 1500:
                    continue  # skip tiny plates

                # Sanity check plate aspect ratio:
                aspect_ratio = pw / ph
                if aspect_ratio < 1.5 or aspect_ratio > 6.0:
                    continue

                plate_crop = vh_crop[py1:py2, px1:px2]

                if plate_crop.size == 0:
                    continue

                score = score_quality(plate_crop)
                print(f"[Vehicle {vid} | Frame {frame_count}] Plate crop size: {plate_crop.shape[:2]}, Score: {score:.2f}")

                if score > best_score:
                    best_score = score
                    best_crop = plate_crop

            if best_crop is not None:
                selector.update(vid, best_crop)
                print(f"[Vehicle {vid} | Frame {frame_count}] ✅ Best score this frame: {best_score:.2f}")


            # 3. Score Sharpness
            if plate_crop is not None:
                selector.update(vid, plate_crop)

        frame_count += 1

    # 4. Save best plates
    for vid, best_plate in selector.get_best_frames().items():
        path = os.path.join(output_dir, f"Vehicle_{vid}_best_plate.jpg")
        cv2.imwrite(path, best_plate)

    print(f"✅ Done. Saved best plate for {len(selector.best_frames)} vehicles.")
