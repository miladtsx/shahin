import os, cv2, random, numpy as np
import albumentations as A

# ---------- CONFIG ----------
DATASET_DIR = "./res/data/dataset/digits"
OUTPUT_DIR = "./res/data/train"
TARGET_PER_CLASS = 10000
IMG_SIZE = 32
SEED = 42
MAX_ERASE_FRACTION = 0.50
NOISE_RATIO = 0.5
COMBO_RATIO = 0.25
ROTATE_RATIO = 0.25
# ----------------------------

random.seed(SEED)
np.random.seed(SEED)


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)


def list_images(d):
    exts = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")
    return [os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(exts)]


def load_gray_resize(path):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise RuntimeError(f"Failed to read {path}")
    return cv2.resize(img, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_AREA)


# --- Augmentations ---

GAUSS_NOISE = A.GaussNoise(std_range=(0.1, 0.50), p=1.0)


def adjust_brightness_contrast_u8(img, brightness_limit=0.1, contrast_limit=0.1):
    alpha = 1.0 + np.random.uniform(-contrast_limit, contrast_limit)
    beta = np.random.uniform(-brightness_limit, brightness_limit) * 255.0
    return cv2.convertScaleAbs(img, alpha=alpha, beta=beta)


def add_noise(img):
    out = GAUSS_NOISE(image=img)["image"]
    if random.random() < 0.5:
        out = adjust_brightness_contrast_u8(out, 0.1, 0.1)
    return out


def erase_small_shapes(img, max_erase_fraction=MAX_ERASE_FRACTION, n_shapes=(1, 3)):
    h, w = img.shape
    limit = int(h * w * max_erase_fraction)
    mask = np.zeros((h, w), dtype=bool)
    for _ in range(random.randint(*n_shapes)):
        tmp = np.zeros_like(mask)
        shape = random.choice(["rect", "circle", "ellipse"])
        if shape == "rect":
            rh, rw = random.randint(1, int(h * 0.15)), random.randint(1, int(w * 0.15))
            x1, y1 = random.randint(0, w - rw), random.randint(0, h - rh)
            tmp[y1 : y1 + rh, x1 : x1 + rw] = True
        elif shape == "circle":
            r = random.randint(1, int(min(h, w) * 0.15))
            cx, cy = random.randint(r, w - r), random.randint(r, h - r)
            yy, xx = np.ogrid[:h, :w]
            tmp = ((xx - cx) ** 2 + (yy - cy) ** 2) <= r * r
        else:
            ax, ay = random.randint(1, int(w * 0.15)), random.randint(1, int(h * 0.15))
            cx, cy = random.randint(0, w - 1), random.randint(0, h - 1)
            ang = np.deg2rad(random.uniform(0, 360))
            yy, xx = np.ogrid[:h, :w]
            xr, yr = xx - cx, yy - cy
            ca, sa = np.cos(ang), np.sin(ang)
            xra, yra = xr * ca + yr * sa, -xr * sa + yr * ca
            tmp = (xra * xra) / (ax * ax) + (yra * yra) / (ay * ay) <= 1.0
        new_area = np.count_nonzero(tmp & ~mask)
        if np.count_nonzero(mask) + new_area <= limit:
            mask |= tmp
        else:
            break
    out = img.copy()
    out[mask] = 255
    return out


def rotate_image(img):
    angle = random.uniform(-1, 1)
    h, w = img.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        img,
        M,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )


# --- Main Augmentation ---
def augment_and_save(base_imgs, cls_dir, to_make):
    n_combo = int(to_make * COMBO_RATIO)
    n_rotate = int(to_make * ROTATE_RATIO)
    remaining = to_make - n_combo - n_rotate
    n_noise = int(remaining * NOISE_RATIO)
    n_erase = remaining - n_noise
    total_base = len(base_imgs)
    idx = 0

    aug_specs = [
        ("noise", n_noise),
        ("erase", n_erase),
        ("combo", n_combo),
        ("rotate", n_rotate),
    ]

    png_params = [cv2.IMWRITE_PNG_COMPRESSION, 3]

    for kind, n_aug in aug_specs:
        for i in range(n_aug):
            img = base_imgs[(idx + i) % total_base]
            if kind == "noise":
                aug = add_noise(img)
            elif kind == "erase":
                aug = erase_small_shapes(img)
            elif kind == "combo":
                aug = erase_small_shapes(img)
                aug = add_noise(aug)
            elif kind == "rotate":
                aug = rotate_image(img)
            else:
                aug = img
            cv2.imwrite(
                os.path.join(cls_dir, f"{kind}_{idx+i:05d}.png"), aug, png_params
            )
        idx += n_aug


def process_class(cls):
    src_imgs = list_images(os.path.join(DATASET_DIR, cls))
    if not src_imgs:
        print(f"[SKIP] {cls}: no images")
        return

    cls_dir = os.path.join(OUTPUT_DIR, cls)
    ensure_dir(cls_dir)
    base_imgs = [load_gray_resize(p) for p in src_imgs]

    for p, img in zip(src_imgs, base_imgs):
        cv2.imwrite(os.path.join(cls_dir, os.path.basename(p)), img)

    existing = len(base_imgs)
    to_make = max(0, TARGET_PER_CLASS - existing)
    if to_make > 0:
        augment_and_save(base_imgs, cls_dir, to_make)

    print(f"[DONE] {cls}: {existing + to_make} images")


def main():
    ensure_dir(OUTPUT_DIR)
    for cls in sorted(os.listdir(DATASET_DIR)):
        if os.path.isdir(os.path.join(DATASET_DIR, cls)):
            process_class(cls)


if __name__ == "__main__":
    main()
