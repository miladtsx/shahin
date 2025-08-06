#!/run/media/dev/SSD/labs/ai/shahin/.venv/bin/python3
import yaml
from src.detect_vehicle import run_plate_detection
from src.preprocessor.preprocessor import PlatePreprocessor
from src.segmentation.segmentation import PlateSegmention


def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def detect_plates(config):
    print("🚗 Starting Plate detection pipeline...")
    run_plate_detection(config)  # TODO move configs out of the method
    print("✅ Plate detection complete.")


def preprocess_plates(config):
    print("📈 Starting preprocessing...")
    preprocessor = PlatePreprocessor(
        input_dir=config["detected_plates_dir"],
        output_dir=config["preprocessed_plates_dir"]
    )
    preprocessor.preprocess()

    print("✅ Preprocessing complete.")

def segmentation(config):
    print("📈 Starting Segmentation...")
    segmentation = PlateSegmention(
        input_dir=config["preprocessed_plates_dir"],
        output_dir=config["segmentation_output_dir"]
    )
    segmentation.segment()

    print("✅ Segmentation complete.")


def main():
    config = load_config()
    #detect_plates(config)
    #preprocess_plates(config)
    #segmentation(config)


if __name__ == "__main__":
    main()
