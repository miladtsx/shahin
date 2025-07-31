#!/run/media/dev/SSD/labs/ai/shahin/.venv/bin/python3
import yaml
from src.detect_vehicle import run_vehicle_detection


def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def main():
    config = load_config()
    print("🚗 Starting vehicle detection pipeline...")
    run_vehicle_detection(config)
    print("✅ Vehicle detection complete.")

    # 🔜 TODO: Track vehicles across frames
    # 🔜 TODO: Detect license plates inside each box
    # 🔜 TODO: Score & select best frame per vehicle
    # 🔜 TODO: Upload selected frame to remote OCR

if __name__ == "__main__":
    main()