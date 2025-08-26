from ultralytics import YOLO


class GlyphClassifier:
    def __init__(
        self,
    ):
        self.digit_classifier_model = YOLO(
            "./res/models/digit_classifier_yolov8n.pt", verbose=False
        )
        self.alphabet_classifier_model = YOLO(
            "./res/models/alphabet_classifier_yolov8n.pt", verbose=False
        )

    def classify_digit(self, input_img):
        results = self.digit_classifier_model.predict(
            input_img, device="cpu", imgsz=32, verbose=False
        )
        pred = results[0]
        probs = pred.probs.data.cpu().numpy()
        class_id = probs.argmax()
        confidence = probs[class_id]
        class_name = pred.names[int(class_id)]
        return {
            "class_id": str(class_id),
            "class_name": class_name,
            "confidence": float(confidence),
        }

    def classify_alphabet(self, input_img):
        results = self.alphabet_classifier_model.predict(
            input_img, device="cpu", imgsz=32, verbose=False
        )
        pred = results[0]
        probs = pred.probs.data.cpu().numpy()
        class_id = probs.argmax()
        confidence = probs[class_id]
        class_name = pred.names[int(class_id)]
        return {
            "class_id": str(class_id),
            "class_name": class_name,
            "confidence": float(confidence),
        }
