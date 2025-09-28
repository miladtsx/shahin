from src.detect_vehicle import run_plate_detection
from src.common_utils.app_logger import get_logger, log_duration
import sys
logger = get_logger("app", logfile="logs/app.jsonl")

def main():
    logger.info("application_start", extra={"event": "application_start"})
    try:
        run_plate_detection()

        logger.info("application_exit", extra={"event": "application_exit"})
    except Exception:
        logger.exception("unhandled_exception")
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
