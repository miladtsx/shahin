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
                    uuid TEXT PRIMARY KEY,
                    plate_text TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """
        )
        cur.execute(
            """
                CREATE TABLE IF NOT EXISTS metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate_uuid TEXT NOT NULL UNIQUE,
                    car_type TEXT,
                    car_color TEXT,
                    driver_name TEXT,
                    FOREIGN KEY (plate_uuid) REFERENCES plates(uuid)
                );
            """
        )
        cur.execute(
            """
                CREATE TABLE IF NOT EXISTS traffic (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate_uuid TEXT NOT NULL,
                    location TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (plate_uuid) REFERENCES plates(uuid)
                );
            """
        )
        self._conn.commit()
        logger.info("initialize_db_success", extra={"db_path": self.get_db_path()})

    def close(self):
        self._conn.close()
        logger.info("db_stopped")

    def insert_plate(
        self, vehicle_id: str, plate_text: str, location=None, metadata=None
    ):
        try:
            cur = self._conn.cursor()
            plate_uuid = vehicle_id

            if plate_text != 'DETECTION_FAILED':
                # ensure plate exists
                cur.execute("SELECT uuid FROM plates WHERE plate_text = ?", (plate_text,))
                row = cur.fetchone()
                if row:
                    plate_uuid = row[0]
            else:
                cur.execute(
                    "INSERT INTO plates (uuid, plate_text) VALUES (?, ?)",
                    (plate_uuid, plate_text),
                )

            # optionally insert/update metadata
            if metadata:
                cur.execute(
                    """
                    INSERT INTO metadata (plate_uuid, car_type, car_color, driver_name)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(plate_uuid) DO UPDATE SET
                        car_type=excluded.car_type,
                        car_color=excluded.car_color,
                        driver_name=excluded.driver_name
                """,
                    (
                        plate_uuid,
                        metadata.get("car_type"),
                        metadata.get("car_color"),
                        metadata.get("driver_name"),
                    ),
                )

            # insert traffic record
            cur.execute(
                "INSERT INTO traffic (plate_uuid, location) VALUES (?, ?)",
                (plate_uuid, location),
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
