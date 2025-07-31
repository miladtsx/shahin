from ultralytics import YOLO
import cv2

class VehicleDetector:
    def __init__(self, model_path, allowed_classes):
        self.model = YOLO(model_path)
        self.allowed = set(allowed_classes)
        self.class_names = self.model.names

    def detect(self, frame):
        results = self.model(frame)[0]
        output = []
        for box in results.boxes:
            cls_id = int(box.cls)
            cls_name = self.class_names[cls_id]
            conf = float(box.conf)
            if cls_name in self.allowed:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                output.append({"cls": cls_name, "conf": conf, "bbox": (x1, y1, x2, y2)})
        return output

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
