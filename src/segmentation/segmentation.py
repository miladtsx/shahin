import os
import cv2
import numpy as np
from typing import List, Tuple
from src.common_utils.config import Config
from src.common_utils.resource_path import get_data_path
from src.common_utils.image_save import save


class PlateSegmentation:
    def __init__(
        self,
    ):
        conf = Config().config
        self.input_dir = get_data_path("preprocessed_plates_dir")
        self.output_dir = get_data_path("segmentation_output_dir")

    def _resize_and_pad(
        self, image: np.ndarray, size: Tuple[int, int] = (32, 32)
    ) -> np.ndarray:
        """Resize while preserving aspect ratio and pad with zeros to fixed size."""
        h, w = image.shape
        scale = min(size[0] / h, size[1] / w)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

        canvas = np.zeros(size, dtype=np.uint8)
        x_offset = (size[1] - new_w) // 2
        y_offset = (size[0] - new_h) // 2
        canvas[y_offset : y_offset + new_h, x_offset : x_offset + new_w] = resized
        return canvas

    def _merge_dots_into_glyphs(
        self, boxes: List[Tuple[int, int, int, int]]
    ) -> List[Tuple[int, int, int, int]]:
        """
        Merge small boxes (dots) into larger glyph boxes.
        """
        merged = []
        used = set()

        sorted_boxes = sorted(
            enumerate(boxes), key=lambda x: x[1][2] * x[1][3], reverse=True
        )

        for i, (x1, y1, w1, h1) in sorted_boxes:
            if i in used:
                continue

            x1c = x1 + w1 // 2
            y1c = y1 + h1 // 2
            big_box = (x1, y1, w1, h1)

            for j, (x2, y2, w2, h2) in sorted_boxes:
                if j == i or j in used:
                    continue

                area1 = w1 * h1
                area2 = w2 * h2
                if area2 > 0.25 * area1:
                    continue  # not a dot

                x2c = x2 + w2 // 2
                y2c = y2 + h2 // 2

                x_overlap = abs(x1c - x2c) < max(w1, w2)
                y_distance = abs(y2c - y1c)
                vertically_close = y_distance < h1

                if x_overlap and vertically_close:
                    x_min = min(x1, x2)
                    y_min = min(y1, y2)
                    x_max = max(x1 + w1, x2 + w2)
                    y_max = max(y1 + h1, y2 + h2)
                    big_box = (x_min, y_min, x_max - x_min, y_max - y_min)
                    used.add(j)

            used.add(i)
            merged.append(big_box)

        return merged

    def _segment_glyphs(self, image: np.ndarray) -> List[np.ndarray]:
        """Returns list of 8 cropped glyph images from a preprocessed plate image."""
        gray = (
            cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        )
        _, thresh = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        raw_boxes = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            area = cv2.contourArea(c)
            aspect_ratio = w / h

            if area < 100:
                continue
            if aspect_ratio < 0.2 or aspect_ratio > 1.5:
                continue

            raw_boxes.append((x, y, w, h))

        # 🔧 Apply dot merging
        merged_boxes = self._merge_dots_into_glyphs(raw_boxes)
        boxes = sorted(merged_boxes, key=lambda b: b[0])

        glyphs = []
        for idx, (x, y, w, h) in enumerate(boxes):
            crop = thresh[y : y + h, x : x + w]
            # Invert before saving the glyph
            glyph = 255 - self._resize_and_pad(crop, (32, 32))
            glyphs.append(glyph)

        # Normalize to 8
        if len(glyphs) > 8:
            glyphs = glyphs[:8]
        elif len(glyphs) < 8:
            glyphs += [np.zeros((32, 32), dtype=np.uint8)] * (8 - len(glyphs))

        return glyphs

    def segment(self, image: np.ndarray, vid):
        """
        Accepts a preprocessed plate image (np.ndarray), returns list of (idx, glyph) tuples.
        """
        glyphs = self._segment_glyphs(image)

        results = []
        for idx, glyph in enumerate(glyphs):
            save(glyph, vid, f"_g_{idx}")
            results.append((idx, glyph))

        return results
