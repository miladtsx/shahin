from src.detectors.vehicle_detector import VehicleDetector
from src.io_utils.video_loader import VideoLoader
from src.tracker.simple_tracker import SimpleTracker
import os
import cv2

def run_vehicle_detection(config):
    # Setup
    video_path = config["video_path"]
    output_dir = config["output_dir"]
    frame_skip = config["frame_skip"]
    vehicle_classes = config["vehicle_classes"]
    model_path = config["model_path"]
    iou_threshold = config["iou_threshold"]

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Initialize
    loader = VideoLoader(video_path)
    detector = VehicleDetector(model_path, vehicle_classes)
    tracker = SimpleTracker(iou_threshold=iou_threshold)

    frame_count = 0
    saved_count = 0

    for frame in loader:
        if frame_count % frame_skip == 0:
            boxes = detector.detect(frame)
            tracked_boxes = tracker.update(boxes)
            annotated_frame = detector.draw(frame.copy(), tracked_boxes)

            # Save full annotated frame for visualization (optional)
            cv2.imwrite(
                os.path.join(output_dir, f"frame_{frame_count}.jpg"), annotated_frame
            )

            # Save each tracked vehicle's annotated frame
            for det in tracked_boxes:
                car_id = det.get("id", "-1")
                x1, y1, x2, y2 = det["bbox"]

                # Crop vehicle region
                vehicle_crop = frame[y1:y2, x1:x2]

                # Save to a per-ID folder
                id_dir = os.path.join(output_dir, f"ID_{car_id}")
                os.makedirs(id_dir, exist_ok=True)

                crop_filename = os.path.join(id_dir, f"frame_{frame_count}.jpg")
                cv2.imwrite(crop_filename, vehicle_crop)

            saved_count += 1

        frame_count += 1

    print(f"✅ Done! {saved_count} frames saved to {output_dir}")
