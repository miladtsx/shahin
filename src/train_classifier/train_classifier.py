from ultralytics import YOLO

# Create a new YOLO model (use yolov8n backbone for speed)
model = YOLO("./res/models/base_classifier_yolov8n-cls.pt", verbose=False)  # pretrained classifier model

# Train
model.train(
    data="./res/data/train_split",
    epochs=20,
    batch=32,                  # reduce if CPU is slow
    imgsz=32,
    device="cpu"
)
