"""
# Synthetic Plate Generation Script
This script generates synthetic license plates by combining randomly selected digits and letters.
"""

import cv2
import numpy as np
import random
from pathlib import Path
import uuid

base_path = "/run/media/dev/SSD/labs/ai/shahin/res/data/"
DIGIT_DIR = Path(f"{base_path}/training_data/digits")
LETTER_DIR = Path(f"{base_path}/training_data/letters")
TEMPLATE_PATH = Path(f"{base_path}/plate_template.jpg")
OUTPUT_IMAGES = Path(f"{base_path}/synthetic/images")
OUTPUT_LABELS = Path(f"{base_path}/synthetic/labels")
OUTPUT_IMAGES.mkdir(parents=True, exist_ok=True)
OUTPUT_LABELS.mkdir(parents=True, exist_ok=True)

GLYPH_SIZE = (52, 100)
GLYPH_SIZE_REGION = (35, 80)
SLOT_COORDS = [
    # FIRST 2 DIGITS
    (90, 20, GLYPH_SIZE),
    (150, 20, GLYPH_SIZE),
    # ALPHABET
    (220, 25, (100, 110)),
    # 3 DIGITS
    (330, 20, GLYPH_SIZE),
    (380, 20, GLYPH_SIZE),
    (430, 20, GLYPH_SIZE),
    # REGION
    (565, 55, GLYPH_SIZE_REGION),
    (520, 55, GLYPH_SIZE_REGION),
    # (370, 20), (420, 30)
]


def load_images(folder):
    return [(cv2.imread(str(p), cv2.IMREAD_UNCHANGED), p.stem) for p in Path(folder).glob("*")]


digits = load_images(DIGIT_DIR)
letters = load_images(LETTER_DIR)
GLYPHS = "0123456789بجسصطقلمنوهی"
glyph_to_class = {g: i for i, g in enumerate(GLYPHS)}

for i in range(10):
    plate_img = 255 * np.ones((150, 700, 3), dtype=np.uint8)
    plate_h, plate_w = plate_img.shape[:2]
    boxes = []

    glyphs = [
        random.choice(digits), random.choice(digits), random.choice(letters),
        random.choice(digits), random.choice(digits), random.choice(digits),
        random.choice(digits), random.choice(digits)
    ]

    for idx, ((glyph_img, glyph_label), (x, y, (w, h))) in enumerate(zip(glyphs, SLOT_COORDS)):
        # Resize glyph with interpolation (anti-aliasing)
        glyph = cv2.resize(glyph_img, (w, h), interpolation=cv2.INTER_AREA) # type: ignore

        # Convert to grayscale
        gray = cv2.cvtColor(glyph, cv2.COLOR_BGR2GRAY)

        # Slight blur to smooth jagged edges
        gray = cv2.GaussianBlur(gray, (3, 3), sigmaX=0.5)

        # Binary inverse threshold to get mask (black foreground = 1)
        _, mask = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)

        # Optional: dilate to thicken glyph a bit
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        mask = cv2.dilate(mask, kernel, iterations=1)

        # Create 3-channel mask and white background
        mask_3ch = cv2.merge([mask, mask, mask])
        white_bg = 255 * np.ones((h, w, 3), dtype=np.uint8)

        # Apply mask to paste glyph (black foreground) on white background
        final_glyph = np.where(mask_3ch == 255, 0, white_bg)

        # Paste onto plate
        plate_img[y:y + h, x:x + w] = final_glyph

        # Save label
        x_c = (x + w / 2) / plate_w
        y_c = (y + h / 2) / plate_h
        w_n = w / plate_w
        h_n = h / plate_h

        class_id = glyph_to_class[glyph_label]
        boxes.append(f"{class_id} {x_c:.4f} {y_c:.4f} {w_n:.4f} {h_n:.4f}")

    img_id = uuid.uuid4().hex[:8]
    cv2.imwrite(str(OUTPUT_IMAGES / f"{img_id}.jpg"), plate_img)

    with open(OUTPUT_LABELS / f"{img_id}.txt", "w") as f:
        f.write("\n".join(boxes))
