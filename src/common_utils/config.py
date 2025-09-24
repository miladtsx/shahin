# config.py
import yaml, os, sys
from typing import TypedDict, List


class MyConfig(TypedDict):
    video_path: str
    frame_skip: int
    car_detection_threshold: float
    plate_detection_threshold: float
    crop_dimension_threshold: int


DEFAULT_CONFIG: MyConfig = {
    "video_path": "rtsp://127.0.0.1:8554/live.stream",
    "frame_skip": 24,
    "car_detection_threshold": 0.6,
    "plate_detection_threshold": 0.5,
    "crop_dimension_threshold": 2400,
}


class Config:
    _instance = None
    _config: MyConfig

    def __new__(cls, path="config.yaml"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)

            base_path = os.path.dirname(sys.executable)
            config_path = os.path.join(base_path, path)

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
