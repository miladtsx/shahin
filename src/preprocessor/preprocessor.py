import cv2
import numpy as np
from typing import Tuple


class PlatePreprocessor:
    def __init__(
        self,
        resize_dim: Tuple[int, int] = (256, 64),
        min_char_area: int = 80,
    ):
        self.resize_dim = resize_dim
        self.min_char_area = min_char_area

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Convert the image to binary color for easier classification
        """
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
        return morphed

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Accepts an image (np.ndarray), resizes and preprocesses it, returns the processed image.
        """
        resized = cv2.resize(image, self.resize_dim)
        return self._preprocess(resized)
