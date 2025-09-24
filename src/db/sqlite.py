import sqlite3
import threading
import queue
from src.common_utils.app_logger import get_logger, log_duration
from src.common_utils.resource_path import get_data_path

logger = get_logger("database", logfile="logs/app.jsonl")


class DB:
    def __init__(self):
        self._task_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()
        with log_duration(logger, "initialize_db"):
            self.initialize_db()

    def get_db_path(self):
        return get_data_path("plates.db")

    def initialize_db(self):
        with sqlite3.connect(self.get_db_path()) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                    CREATE TABLE IF NOT EXISTS plates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        vehicle_id TEXT,
                        plate_text TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
            )
            conn.commit()
        logger.info("initialize_db_success", extra={"db_path": self.get_db_path()})

    def _writer_loop(self):
        conn = sqlite3.connect(self.get_db_path())
        cur = conn.cursor()
        while not self._stop_event.is_set():
            try:
                task = self._task_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if task is None:
                break
            try:
                cur.execute(*task)
                conn.commit()
            except Exception as e:
                logger.exception("db_writer_error", extra={"error": str(e)})
            finally:
                logger.info("db_writer_task_done", extra={"task": task})
                self._task_queue.task_done()
        conn.close()

    def stop(self):
        self._task_queue.join()
        self._stop_event.set()
        self._task_queue.put(None)
        self._writer_thread.join()

    logger.info("db_stopped")

    def insert_plate(self, vid: int, plate_text: str):
        # Validate input
        if (
            not isinstance(vid, int)
            or vid < 1
            or vid > 2**31 - 1
            or not isinstance(plate_text, str)
            or len(plate_text) < 7
        ):
            logger.exception(
                "Invalid input types",
                extra={
                    "vehicle_id": vid,
                    "plate_text": plate_text,
                },
            )
            raise ValueError("Invalid input types")

        self._task_queue.put(
            (
                "INSERT INTO plates (vehicle_id, plate_text) VALUES (?, ?)",
                (str(vid), plate_text),
            )
        )
        logger.info("insert_plate_enqueued", extra={"vehicle_id": vid})
