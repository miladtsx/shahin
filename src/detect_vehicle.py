from src.detectors.vehicle_detector import VehicleDetector
from src.io_utils.video_loader import VideoLoader
import os
import cv2

def run_vehicle_detection(config):
    # Setup
    video_path = config["video_path"]
    output_dir = config["output_dir"]
    frame_skip = config["frame_skip"]
    vehicle_classes = config["vehicle_classes"]
    model_path = config["model_path"]

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Initialize
    loader = VideoLoader(video_path)
    detector = VehicleDetector(model_path, vehicle_classes)

    frame_count = 0
    saved_count = 0

    for frame in loader:
        if frame_count % frame_skip == 0:
            boxes = detector.detect(frame)
            annotated = detector.draw(frame.copy(), boxes)

            out_path = os.path.join(output_dir, f"frame_{frame_count}.jpg")
            cv2.imwrite(out_path, annotated)
            saved_count += 1

        frame_count += 1

    print(f"✅ Done! {saved_count} frames saved to {output_dir}")
