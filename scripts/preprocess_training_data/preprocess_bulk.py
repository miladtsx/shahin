import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.preprocessor.preprocessor import PlatePreprocessor
import os, cv2
from src.common_utils.image_save import save

RAW_PLATES_DIR = "./res/dataset/newplates/"


def preprocess_data():
    # load raw plates
    preprocessor = PlatePreprocessor()
    for filename in os.listdir(RAW_PLATES_DIR):
        if filename.endswith(".jpg"):
            img_path = os.path.join(RAW_PLATES_DIR, filename)
            img = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if img is None:
                print(f"Warning: failed to read image: {img_path}")
                continue
            processed = preprocessor.preprocess(img)
            if processed is None:
                print(f"Warning: preprocessor returned None for: {img_path}")
                continue
            save(
                processed,
                "preprocessed",
                filename,
                path="./res/dataset/newplates/preprocessed",
            )


if __name__ == "__main__":
    preprocess_data()
