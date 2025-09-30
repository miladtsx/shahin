from ultralytics import YOLO
import cv2
import numpy as np

class VehicleDetector:
    def __init__(self, model_path, allowed_classes):
        self.model = YOLO(model_path, task="detect", verbose=False)
        self.allowed = set(allowed_classes)
        self.class_names = self.model.names

    def detect(self, frame, conf_threshold=0.5):
        results = self.model(frame, verbose=False)[0]
        boxes_data = results.boxes.data.cpu().numpy()  # x1,y1,x2,y2,score,class_id
        
        if boxes_data.size == 0:
            return np.empty((0, 5), dtype=np.float64)

        # Ensure class IDs are ints for filtering
        scores = boxes_data[:, 4]
        class_ids = boxes_data[:, 5].astype(int)

        # Mask: allowed classes AND confidence threshold
        allowed_set = set(self.allowed)
        mask = (scores >= conf_threshold) & np.array([cid in allowed_set for cid in class_ids])
        
        filtered = boxes_data[mask, :5].astype(np.float64)  # x1,y1,x2,y2,score
        return filtered if filtered.shape[0] > 0 else np.empty((0, 5), dtype=np.float64)



    def draw(self, frame, tracked_boxes):
        for det in tracked_boxes:
            car_id = det.get("id", "-1")
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
