# config.py
import yaml
from typing import TypedDict

class MyConfig(TypedDict):
    detected_plates_dir: str
    db_path: str
    video_path: str
    preprocessed_plates_dir: str
    segmentation_output_dir: str
    frame_skip: int
    vehicle_classes: list[int]
    plate_classes: list[str]
    model_plate: str
    model_vehicle: str
    car_detection_threshold: float
    plate_detection_threshold: float
    crop_dimension_threshold: int

class Config():
    _instance = None
    _config: MyConfig

    def __new__(cls, path="config.yaml"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            with open(path, "r") as f:
                cls._instance._config = yaml.safe_load(f)
        return cls._instance

    @property
    def config(self) -> MyConfig:
        return self._config
