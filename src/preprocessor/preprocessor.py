import os
import cv2
import numpy as np
from typing import Tuple
from src.common_utils.config import Config
from src.common_utils.resource_path import get_data_path


class PlatePreprocessor:
    def __init__(
        self,
        resize_dim: Tuple[int, int] = (256, 64),
        min_char_area: int = 80,
    ):
        conf = Config().config

        self.input_dir = get_data_path("detected_plates_dir")
        self.output_dir = get_data_path("preprocessed_plates_dir")
        self.resize_dim = resize_dim
        self.min_char_area = min_char_area
        os.makedirs(self.output_dir, exist_ok=True)

    def _save_debug(self, image, filename, tag):
        os.makedirs(f"debug/preprocess/{filename}", exist_ok=True)
        cv2.imwrite(f"debug/preprocess/{filename}/{tag}.jpg", image)

    def _preprocess(self, image: np.ndarray, filename) -> np.ndarray:

        # 1. Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        # 2. Otsu thresholding (invert: digits become white on black)
        _, binary_otsu = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        # 3. Morphological closing (to clean up character edges)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        morphed = cv2.morphologyEx(binary_otsu, cv2.MORPH_CLOSE, kernel)
        self._save_debug(morphed, filename, "morphed")

        return morphed

    def preprocess(self, file_name):
        if not file_name.lower().endswith((".png", ".jpg", ".jpeg")):
            return

        path = os.path.join(self.input_dir, file_name)
        image = cv2.imread(path)
        if image is None:
            print(f"[WARN] Failed to read {file_name}")
            return

        resized = cv2.resize(image, self.resize_dim)
        result = self._preprocess(resized, file_name)

        cv2.imwrite(os.path.join(self.output_dir, file_name), result)

    def preprocess_bulk(self):
        for filename in os.listdir(self.input_dir):
            if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
                continue

            path = os.path.join(self.input_dir, filename)
            image = cv2.imread(path)
            if image is None:
                print(f"[WARN] Failed to read {filename}")
                continue

            resized = cv2.resize(image, self.resize_dim)
            result = self._preprocess(resized, filename)

            cv2.imwrite(os.path.join(self.output_dir, filename), result)
