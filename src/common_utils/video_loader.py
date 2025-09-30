import cv2
import time
from src.common_utils.app_logger import get_logger

logger = get_logger("video_loader", logfile="logs/app.jsonl")

class VideoLoader:
    def __init__(self, path, retry_delay=5, max_retry_delay=60):
        self.path = path
        self.retry_delay = retry_delay
        self.max_retry_delay = max_retry_delay
        self.current_delay = retry_delay
        self.cap = None
        self._initialize_capture()

    def _initialize_capture(self):
        """Initialize video capture with retry logic"""
        while True:
            try:
                logger.info(f"Attempting to open video: {self.path}")
                self.cap = cv2.VideoCapture(self.path)
                
                if self.cap.isOpened():
                    logger.info(f"Successfully opened video: {self.path}")
                    self.current_delay = self.retry_delay  # Reset delay on success
                    return
                else:
                    logger.warning(f"Failed to open video: {self.path}")
                    self.cap.release()
                    
            except Exception as e:
                logger.error(f"Error opening video {self.path}: {e}")
            
            # Wait before retry with exponential backoff
            logger.info(f"Retrying in {self.current_delay} seconds...")
            time.sleep(self.current_delay)
            
            # Increase delay for next retry (with cap)
            self.current_delay = min(self.current_delay * 2, self.max_retry_delay)

    def _reconnect(self):
        """Reconnect to video source"""
        logger.warning("Video connection lost, attempting to reconnect...")
        if self.cap:
            self.cap.release()
        self._initialize_capture()

    def __iter__(self):
        return self

    def __next__(self):
        ret, frame = self.cap.read()
        if not ret:
            # Video ended or connection lost, try to reconnect
            self._reconnect()
            ret, frame = self.cap.read()
            if not ret:
                # Still can't read, wait and try again
                logger.warning("Still cannot read from video, waiting...")
                time.sleep(self.current_delay)
                self._reconnect()
                ret, frame = self.cap.read()
                if not ret:
                    raise StopIteration
        return frame

    def __del__(self):
        if self.cap:
            self.cap.release()
