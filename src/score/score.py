import cv2
import numpy as np

def score_quality(img: np.ndarray) -> float:
    if img is None or img.size == 0:
        return 0.0

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    area = h * w

    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    contrast = np.std(gray.astype(np.float32))
    brightness = np.mean(gray.astype(np.float32)) / 255.0
    aspect_ratio = w / h
    aspect_score = 1.0 if 1.5 <= aspect_ratio <= 6.0 else 0.5

    if area < 1500 or lap_var < 10:  # More lenient than before
        return 0.0

    # Normalize everything
    norm_area = min(float(area) / 20000, 1.0)  # Scales up to 200x100 plate
    norm_lap = min(float(lap_var) / 1000.0, 1.0)
    norm_contrast = min(float(contrast) / 64.0, 1.0)

    score = (
        0.4 * norm_area +
        0.3 * norm_lap +
        0.1 * norm_contrast +
        0.1 * brightness +
        0.1 * aspect_score
    )

    return float(score)
