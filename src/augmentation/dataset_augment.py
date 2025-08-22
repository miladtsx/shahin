import os, cv2, random, numpy as np
import albumentations as A
from glob import glob

# ---------- CONFIG ----------
DATASET_DIR = "./res/data/dataset"
OUTPUT_DIR = "./res/data/augmented_dataset"
TARGET_PER_CLASS = 1000
IMG_SIZE = 128
SEED = 42
# ----------------------------

random.seed(SEED)
np.random.seed(SEED)

# ----------- UTILITIES -----------


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)


def list_images(d):
    exts = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")
    return [p for p in glob(os.path.join(d, "*")) if p.lower().endswith(exts)]


def load_gray(path):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise RuntimeError(f"Failed to read image: {path}")
    return img


# ----------- CUSTOM AUGMENTATION OPS -----------


def erase_natural_shapes_rgb(img, max_erase_fraction=0.6, n_shapes=(1,5)):
    """
    Works on RGB images. White-fill occlusions.
    Total erased pixels limited to max_erase_fraction of image.
    """
    h, w = img.shape[:2]
    out = img.copy()
    erased_pixels = 0
    max_pixels = int(h * w * max_erase_fraction)

    for _ in range(random.randint(*n_shapes)):
        shape_type = random.choice(['rect', 'circle', 'triangle', 'ellipse', 'polygon'])
        temp = out.copy()

        white = (255, 255, 255)

        if shape_type == 'rect':
            rh = random.randint(2, int(h*0.25))
            rw = random.randint(2, int(w*0.25))
            x1 = random.randint(0, w - rw)
            y1 = random.randint(0, h - rh)
            temp[y1:y1+rh, x1:x1+rw] = white

        elif shape_type == 'circle':
            radius = random.randint(2, int(min(h,w)*0.25))
            center = (random.randint(0, w-1), random.randint(0, h-1))
            cv2.circle(temp, center, radius, white, -1)

        elif shape_type == 'triangle':
            pts = np.array([[random.randint(0,w-1), random.randint(0,h-1)] for _ in range(3)], np.int32)
            cv2.fillPoly(temp, [pts], white)

        elif shape_type == 'ellipse':
            center = (random.randint(0, w-1), random.randint(0, h-1))
            axes = (random.randint(2,int(w*0.25)), random.randint(2,int(h*0.25)))
            angle = random.uniform(0, 360)
            cv2.ellipse(temp, center, axes, angle, 0, 360, white, -1)

        elif shape_type == 'polygon':
            n_pts = random.randint(3,6)
            pts = np.array([[random.randint(0,w-1), random.randint(0,h-1)] for _ in range(n_pts)], np.int32)
            cv2.fillPoly(temp, [pts], white)

        # count newly erased pixels (all channels must be 255)
        mask_old = np.all(out==255, axis=2)
        mask_new = np.all(temp==255, axis=2)
        new_erased = np.sum(mask_new & ~mask_old)

        if erased_pixels + new_erased <= max_pixels:
            out = temp
            erased_pixels += new_erased
        else:
            break

    return out

def random_erode(img, ksize=(1,3), iters=(1,2)):
    """Erode each channel independently to simulate fading strokes."""
    out = img.copy()
    for c in range(3):
        k = random.randint(*ksize)
        i = random.randint(*iters)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
        out[:,:,c] = cv2.erode(out[:,:,c], kernel, iterations=i)
    return out

def apply_scratches_pipeline(img):
    out = erase_natural_shapes_rgb(img)
    if random.random() < 0.6:
        out = random_erode(out)
    return out

# ----------- ALBUMENTATIONS PIPELINES -----------

base_resize = [] if IMG_SIZE is None else [A.Resize(IMG_SIZE, IMG_SIZE)]

noise_pipeline = A.Compose(
    [
        *base_resize,
        A.GaussNoise(std_range=(0.1, 0.5), p=1.0),
        A.RandomBrightnessContrast(brightness_limit=0.15, contrast_limit=0.15, p=0.4),
    ]
)

angle_pipeline = A.Compose(
    [
        *base_resize,
        A.Affine(
            rotate=(-5, 5),
            translate_percent=(0.02, 0.05),
            scale=(0.9, 1.1),
            shear=(-5, 5),
            p=0.7,
        ),
        A.Perspective(scale=(0.02, 0.06), keep_size=True, fit_output=False, p=0.5),
    ]
)


def scratches_transform(image, **kwargs):
    return apply_scratches_pipeline(image)

scratch_pipeline = A.Compose(
    [
        *base_resize,
        A.Affine(scale=(0.9, 1.1), translate_percent=(0.02, 0.05),
                 rotate=(-10, 10), shear=(-5, 5), p=1.0),
        A.Lambda(image=scratches_transform),
    ]
)
# ----------- MAIN AUGMENTATION -----------


def augment_once(img, kind):
    if kind == "noise":
        return noise_pipeline(image=img)["image"]
    if kind == "angle":
        return angle_pipeline(image=img)["image"]
    if kind == "scratch":
        # apply scratch on grayscale, then convert to RGB
        aug = scratch_pipeline(image=cv2.cvtColor(img, cv2.COLOR_GRAY2RGB))["image"]
        return aug
    raise ValueError(kind)


def per_class_counts(target):
    n_noise = int(round(0.10 * target))
    n_angle = int(round(0.10 * target))
    n_scratch = target - n_noise - n_angle
    return n_noise, n_angle, n_scratch

def to_binary(img, threshold=128):
    """Convert grayscale or RGB image to binary (0 or 255)."""
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY)
    return binary


def process_class(cls, src_imgs):
    out_dir = os.path.join(OUTPUT_DIR, cls)
    ensure_dir(out_dir)
    existing = 0

    # Copy originals
    for p in src_imgs:
        img = load_gray(p)
        if IMG_SIZE is not None:
            img = cv2.resize(img, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_AREA)
        cv2.imwrite(os.path.join(out_dir, os.path.basename(p)), img)
        existing += 1

    to_make = max(0, TARGET_PER_CLASS - existing)
    n_noise, n_angle, n_scratch = per_class_counts(to_make)
    base_cycle = 0

    def pick_base():
        nonlocal base_cycle
        p = src_imgs[base_cycle % len(src_imgs)]
        base_cycle += 1
        return load_gray(p)

    idx = 0
    for kind, n_aug in [("noise", n_noise), ("angle", n_angle), ("scratch", n_scratch)]:
        for _ in range(n_aug):
            img = pick_base()
            aug = augment_once(img, kind)
            binary_aug = to_binary(aug)
            cv2.imwrite(os.path.join(out_dir, f"{cls}_{kind}_{idx:04d}.png"), binary_aug)
            idx += 1

    total = len(list_images(out_dir))
    print(f"[DONE] {cls}: {total} images")


def main():
    ensure_dir(OUTPUT_DIR)
    class_dirs = [
        d
        for d in sorted(os.listdir(DATASET_DIR))
        if os.path.isdir(os.path.join(DATASET_DIR, d))
    ]
    for cls in class_dirs:
        src_imgs = list_images(os.path.join(DATASET_DIR, cls))
        if not src_imgs:
            print(f"[SKIP] {cls}: no images")
            continue
        process_class(cls, src_imgs)


if __name__ == "__main__":
    main()
