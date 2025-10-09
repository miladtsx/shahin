import sqlite3
from src.common_utils.app_logger import get_logger
from src.common_utils.resource_path import get_data_path

logger = get_logger("database", logfile="logs/app.jsonl")


class DB:
    def __init__(self):
        self._conn = sqlite3.connect(self.get_db_path(), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._conn.execute("PRAGMA synchronous = FULL;")
        self.initialize_db()

    def get_db_path(self):
        return get_data_path("plates.db")

    def initialize_db(self):
        cur = self._conn.cursor()
        cur.execute(
            """
                CREATE TABLE IF NOT EXISTS plates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id TEXT,
                    plate_text TEXT,
                    car_type TEXT,
                    car_color TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
        )
        self._conn.commit()
        logger.info("initialize_db_success", extra={"db_path": self.get_db_path()})

    def close(self):
        self._conn.close()
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

        try:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO plates (vehicle_id, plate_text) VALUES (?, ?)",
                (str(vid), plate_text),
            )
            self._conn.commit()
        except Exception as e:
            logger.exception("db_insert_error", extra={"error": str(e)})

    def get_reader_connection(self):
        """Optional: use only for read-only operations in other threads."""
        conn = sqlite3.connect(self.get_db_path(), check_same_thread=False)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = FULL;")
        return conn
