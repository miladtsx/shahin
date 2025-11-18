import os, sys
from pathlib import Path

_MODELS_OVERRIDE = os.environ.get("SHAHIN_MODELS_DIR")


def get_resource_path(relative_path):
    """Return absolute path to resource inside EXE or dev environment."""
    normalized = relative_path.replace("\\", "/")
    if _MODELS_OVERRIDE and normalized.startswith("res/models/"):
        return str(Path(_MODELS_OVERRIDE) / Path(relative_path).name)

    if getattr(sys, "frozen", False):
        # Path inside the PyInstaller bundle
        base_path = sys._MEIPASS
    else:
        # Normal Python execution
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_data_path(data_item):
    """Return absolute path to resource inside user directory."""
    if sys.platform == "win32":
        data_dir = Path(os.getenv("LOCALAPPDATA")) / "shahin"
    else:
        data_dir = Path.home() / ".shahin"

    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / data_item)
