from ultralytics import YOLO
import numpy as np
import uuid


class VehicleDetector:
    def __init__(self, model_path, allowed_classes):
        self.model = YOLO(model_path, task="detect", verbose=False)
        self.allowed = set(allowed_classes)
        self.class_names = self.model.names
        self.id_map = {}

    def get_uuid(self, tracked_vehicle):
        vid = tracked_vehicle["id"]
        if vid not in self.id_map:
            self.id_map[vid] = str(uuid.uuid4())
        tracked_vehicle["id"] = self.id_map[vid]
        return tracked_vehicle

    def detect(self, frame, conf_threshold=0.5):
        results = self.model(frame, verbose=False)[0]
        boxes_data = results.boxes.data.cpu().numpy()  # x1,y1,x2,y2,conf,class_id

        if boxes_data.size == 0:
            return np.empty((0, 5), dtype=np.float64)

        # Ensure class IDs are ints for filtering
        conf = boxes_data[:, 4]
        class_ids = boxes_data[:, 5].astype(int)

        # Mask: allowed classes AND confidence threshold
        mask = (conf >= conf_threshold) & np.isin(class_ids, list(self.allowed))

        filtered = boxes_data[mask, :5].astype(np.float64)  # x1,y1,x2,y2,conf
        return filtered if filtered.shape[0] > 0 else np.empty((0, 5), dtype=np.float64)
