#!/run/media/dev/SSD/labs/ai/shahin/.venv/bin/python3
import yaml
from src.detect_vehicle import run_plate_detection


def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def main():
    config = load_config()
    print("🚗 Starting Plate detection pipeline...")
    run_plate_detection(config)
    print("✅ Plate detection complete.")

    # 🔜 TODO: Track plates across frames
    # 🔜 TODO: Score & select best frame per plate
    # 🔜 TODO: Upload selected frame to remote OCR

if __name__ == "__main__":
    main()