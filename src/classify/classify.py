from ultralytics import YOLO
import os

# Load the trained model
model = YOLO("./runs/classify/train2/weights/last.pt")

# Predict a single image
input_dir = "/run/media/dev/SSD/labs/ai/shahin/out/segmentation/Vehicle_1_plate"
input_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]

for input_file in input_files:
    results = model.predict(input_file, device="cpu")
    pred = results[0]
    probs = pred.probs.data.cpu().numpy()
    class_id = probs.argmax()
    confidence = probs[class_id]
    class_name = pred.names[class_id]
    print(f"File: {os.path.basename(input_file)}, Predicted class: {class_name}, confidence: {confidence:.3f}")
