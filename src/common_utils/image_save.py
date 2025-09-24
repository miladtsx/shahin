import cv2, os
from .resource_path import get_data_path


def save_debug(image, filename, tag):
    os.makedirs(f"debug/segmentation/{filename}", exist_ok=True)
    cv2.imwrite(f"debug/segmentation/{filename}/{tag}.jpg", image)


def save(image, vid, tag):
    """
    Save image in user directory
    """
    file_path = f"{get_data_path("out")}/{vid}/"
    try:
        os.makedirs(file_path, exist_ok=True)
        cv2.imwrite(os.path.join(file_path, f"{tag}.jpg"), image)
    except Exception as e:
        print(f"Error saving image {file_path}: {e}")
