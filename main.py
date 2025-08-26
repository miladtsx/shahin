#!/run/media/dev/SSD/labs/ai/shahin/.venv/bin/python3
from src.db.sqlite import DB
from src.detect_vehicle import run_plate_detection
from src.common_utils.app_logger import get_logger, log_duration


logger = get_logger("app", logfile="logs/app.jsonl")


def main():
    logger.info("application_start", extra={"event": "application_start"})
    try:
        with log_duration(logger, "initialize_db"):
            db = DB()
            db.initialize_db()

        with log_duration(logger, "run_plate_detection"):
            run_plate_detection()

        logger.info("application_exit", extra={"event": "application_exit"})
    except Exception:
        # structured exception with stack trace
        logger.exception("unhandled_exception")


if __name__ == "__main__":
    main()
