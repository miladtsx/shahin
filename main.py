#!/run/media/dev/SSD/labs/ai/shahin/.venv/bin/python3
from src.detect_vehicle import run_plate_detection

if __name__ == "__main__":
    try:
        run_plate_detection()
    except Exception as e:
        print(f"Error: {e}")
