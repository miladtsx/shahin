import os
import cv2
import numpy as np
from typing import List, Tuple
import uuid


class PlatePreprocessor:
    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        resize_dim: Tuple[int, int] = (256, 64),
        min_char_area: int = 80,
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.resize_dim = resize_dim
        self.min_char_area = min_char_area
        self.templates = self._load_templates(
            "/run/media/dev/SSD/labs/ai/shahin/res/data/training_data/digits/"
        )

        os.makedirs(output_dir, exist_ok=True)

    def _load_templates(self, dir_path: str) -> dict:
        templates = {}
        for fname in os.listdir(dir_path):
            if not fname.endswith(".jpg"):
                continue
            label = os.path.splitext(fname)[0]
            img = cv2.imread(os.path.join(dir_path, fname), cv2.IMREAD_GRAYSCALE)
            img = cv2.resize(img, (32, 32)) # type: ignore
            _, img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
            templates[label] = img
        return templates

    # TODO check this out
    def recognize(self, glyph: np.ndarray) -> str:
        glyph = cv2.resize(glyph, (32, 32))
        _, glyph = cv2.threshold(glyph, 127, 255, cv2.THRESH_BINARY)

        best_label = None
        best_score = float("inf")

        for label, template in self.templates.items():
            score = np.sum(glyph != template)  # Hamming distance
            if score < best_score:
                best_score = score
                best_label = label

        return best_label # type: ignore

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

    def preprocess(self):
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
