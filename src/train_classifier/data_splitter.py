import os, shutil, random

DATA_DIR = "./res/data/train"
OUTPUT_DIR = "./res/data/train_split"
VAL_RATIO = 0.2
random.seed(42)

for class_name in os.listdir(DATA_DIR):
    class_path = os.path.join(DATA_DIR, class_name)
    if not os.path.isdir(class_path):
        continue
    
    imgs = os.listdir(class_path)
    random.shuffle(imgs)
    split_idx = int(len(imgs) * VAL_RATIO)
    
    train_imgs = imgs[split_idx:]
    val_imgs = imgs[:split_idx]
    
    for subset, subset_imgs in zip(["train", "val"], [train_imgs, val_imgs]):
        out_class_dir = os.path.join(OUTPUT_DIR, subset, class_name)
        os.makedirs(out_class_dir, exist_ok=True)
        for img in subset_imgs:
            shutil.copy(os.path.join(class_path, img), os.path.join(out_class_dir, img))
