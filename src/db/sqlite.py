import sqlite3
import threading
import queue
from datetime import datetime
import os
from src.common_utils.config import Config


class DB:
    def __init__(self):
        conf = Config().config
        self.db_path = conf.get("db_path")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._task_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()
        self.initialize_db()

    def initialize_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                    CREATE TABLE IF NOT EXISTS plates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        vehicle_id TEXT,
                        image_path TEXT,
                        plate_text TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
            )
            conn.commit()

    def _writer_loop(self):
        conn = sqlite3.connect(self.db_path)
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
                print(f"[DB ERROR] {e}")
            finally:
                self._task_queue.task_done()
        conn.close()

    def stop(self):
        self._task_queue.join()
        self._stop_event.set()
        self._task_queue.put(None)
        self._writer_thread.join()

    def insert_plate(self, vid: int, file_path: str, plate_text: str):
        # Validate input
        if (
            not isinstance(vid, int)
            or vid < 1
            or vid > 2**31 - 1
            or not isinstance(file_path, str)
            or not isinstance(plate_text, str)
            or len(plate_text) < 7
        ):
            raise ValueError("Invalid input types")

        self._task_queue.put(
            (
                "INSERT INTO plates (vehicle_id, image_path, plate_text) VALUES (?, ?, ?)",
                (str(vid), file_path, plate_text),
            )
        )
