# config.py
import yaml, os
from typing import List
from typing import TypedDict
from src.common_utils.resource_path import get_data_path


class Point(TypedDict):
    x: float
    y: float


class MyConfig(TypedDict):
    camera_location: str
    video_path: str
    frame_skip: int
    car_detection_threshold: float
    plate_detection_threshold: float
    crop_dimension_threshold: int
    hot_zone: List[Point]
    track_expiry: int  # Frames until car tracking expires
    rotation_angle: float
    failure_grace_seconds: int


DEFAULT_CONFIG: MyConfig = {
    "camera_location": "تعیین نشده",
    "video_path": "rtsp://127.0.0.1:8554/live.stream",
    "frame_skip": 1,
    "car_detection_threshold": 0.6,
    "plate_detection_threshold": 0.5,
    "crop_dimension_threshold": 2400,
    "hot_zone": [  # polygon with 4 points by default
        {"x": 0.25, "y": 0.25},
        {"x": 0.75, "y": 0.25},
        {"x": 0.75, "y": 0.75},
        {"x": 0.25, "y": 0.75},
    ],
    "track_expiry": 120,
    "rotation_angle": 0,
    "failure_grace_seconds": 10,
}


class Config:
    _instance = None
    _config: MyConfig

    def __new__(cls, path="config.yaml"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)

            config_path = get_data_path("config.yaml")

            # Create a default conf file if does not exists
            if not os.path.exists(config_path):
                print(f"WARNING: {config_path} not found. Creating default.")
                with open(config_path, "w") as f:
                    yaml.safe_dump(DEFAULT_CONFIG, f)
                cls._instance._config = DEFAULT_CONFIG
            else:
                with open(config_path, "r") as f:
                    cls._instance._config = yaml.safe_load(f)

        return cls._instance

    @property
    def config(self) -> MyConfig:
        return self._config
