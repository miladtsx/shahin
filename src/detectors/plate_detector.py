from ultralytics import YOLO
import cv2
import torch

class PlateDetector:
    def __init__(self, model_path, allowed_classes):
        self.model = YOLO(model_path, task="obb", verbose=False)
        self.allowed = set(allowed_classes)
        self.class_names = self.model.names

    def detect(self, frame, conf_threshold=0.8):
        if frame.size == 0:
            return []
        results = self.model(frame, verbose=False)[0]
        output = []
        for box in results.boxes:
            cls_id = int(box.cls)
            cls_name = self.class_names[cls_id]
            conf = float(box.conf)
            if conf < conf_threshold:
                continue
            if cls_name in self.allowed:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                output.append({"cls": cls_name, "conf": conf, "bbox": (x1, y1, x2, y2)})
        return output

    def detect_batch(self, crops, conf_threshold=0.8, stride=32):
        if len(crops) == 0:
            return []

        batch, pad_info = self.preprocess_crops_pad_uniform(crops, self.model.device, stride)
        results = self.model(batch, verbose=False)

        batch_outputs = []
        for result, (top, bottom, left, right, h_orig, w_orig) in zip(results, pad_info):
            output = []
            for box in result.boxes:
                cls_id = int(box.cls)
                cls_name = self.class_names[cls_id]
                conf = float(box.conf)
                if conf < conf_threshold or cls_name not in self.allowed:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                # Map back to original crop by removing padding
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                x1 -= left
                x2 -= left
                y1 -= top
                y2 -= top
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(w_orig-1, x2)
                y2 = min(h_orig-1, y2)
                output.append({"cls": cls_name, "conf": conf, "bbox": (x1, y1, x2, y2)})
            batch_outputs.append(output)

        return batch_outputs

    def preprocess_crops_pad_uniform(self, crops, device, stride=32, pad_value=114):
        # Find max height and width in the batch
        max_h = max(c.shape[0] for c in crops)
        max_w = max(c.shape[1] for c in crops)

        # Make divisible by stride
        max_h = (max_h + stride - 1) // stride * stride
        max_w = (max_w + stride - 1) // stride * stride

        batch = []
        pad_info = []
        for crop in crops:
            h, w = crop.shape[:2]
            top = (max_h - h) // 2
            bottom = max_h - h - top
            left = (max_w - w) // 2
            right = max_w - w - left

            padded = cv2.copyMakeBorder(crop, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(pad_value,pad_value,pad_value))
            t = torch.from_numpy(padded).permute(2,0,1).float() / 255.0
            batch.append(t)
            pad_info.append((top, bottom, left, right, h, w))  # save original size for clipping

        return torch.stack(batch).to(device), pad_info

    def draw(self, frame, tracked_boxes):
        for det in tracked_boxes:
            plate_id = det.get('id', '-1')
            x1, y1, x2, y2 = det["bbox"]
            label = f"ID:{plate_id} {det['cls']} {det['conf']:.2f}"
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
