from ultralytics import YOLO
import cv2

class VehicleDetector:
    def __init__(self, model_path, allowed_classes):
        self.model = YOLO(model_path)
        self.allowed = set(allowed_classes)
        self.class_names = self.model.names

    def detect(self, frame, conf_threshold=0.5):
        results = self.model(frame)[0]
        detections_ = []
        for detection in results.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = detection
            if int(class_id) in self.allowed:
                detections_.append([x1, y1, x2, y2, score])
        return detections_

    def draw(self, frame, tracked_boxes):
        for det in tracked_boxes:
            car_id = det.get('id', '-1')
            x1, y1, x2, y2 = det["bbox"]
            label = f"ID:{car_id} {det['cls']} {det['conf']:.2f}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                frame,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )
        return frame
