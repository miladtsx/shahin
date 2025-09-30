from collections import defaultdict
from heapq import heappush, heappop, nsmallest
import os
from src.classify.classify import GlyphClassifier
from src.segmentation.segmentation import PlateSegmentation
from src.preprocessor.preprocessor import PlatePreprocessor
from src.common_utils.app_logger import get_logger
from src.common_utils.image_save import save

logger = get_logger("best_frame_selector", logfile="logs/app.jsonl")


class OnlineBestFrameSelector:
    def __init__(
        self,
        scorer,
        no_improve_patience=10,
        track_timeout=10,
        k=10,
        improve_margin=0.1,  # relative margin to trigger re-OCR
    ):
        self.scorer = scorer
        self.candidates = defaultdict(list)  # vid -> [(score, frame_idx, crop), ...]
        self.best_frames = {}  # vid -> (score, crop, frame_idx)
        self.last_update = {}  # vid -> last frame number
        self.missed_frames = defaultdict(int)
        self.k = k
        self.no_improve_patience = no_improve_patience
        self.track_timeout = track_timeout
        self.improve_margin = improve_margin
        self.ocr_results = {}  # vid -> latest OCR text

    def update(self, vid, crop, frame_idx, db=None, executor=None):
        score = self.scorer(crop)
        heappush(self.candidates[vid], (score, frame_idx, crop))
        if len(self.candidates[vid]) > self.k:
            heappop(self.candidates[vid])
        self.last_update[vid] = frame_idx
        self.missed_frames[vid] = 0

        prev_best = self.best_frames.get(vid)
        if prev_best is None or score > prev_best[0] * (1 + self.improve_margin):
            # Found a significantly better frame -> trigger OCR now
            self.best_frames[vid] = (score, crop, frame_idx)
            if executor and db:
                executor.submit(self._run_ocr, db, vid, crop)

        return score

    def _run_ocr(self, db, vid, crop):
        """Run OCR immediately on the current best crop and overwrite previous result."""
        try:
            save(crop, vid, "best_live")

            preprocessor = PlatePreprocessor()
            preprocessor.preprocess(crop)

            segmentation = PlateSegmentation()
            glyphs = segmentation.segment(crop, vid)
            if glyphs is None:
                return

            classifier = GlyphClassifier()
            final_plate_text = [""] * 8

            for idx, g in glyphs:
                if idx == 2:
                    class_id = classifier.classify_alphabet(g).get("class_name")
                else:
                    class_id = to_farsi_number(
                        classifier.classify_digit(g).get("class_name")
                    )
                final_plate_text[idx] = class_id if class_id else ""

            plate_text = "".join(final_plate_text)
            self.ocr_results[vid] = plate_text

            try:
                db.insert_plate(vid, plate_text)
            except Exception as e:
                logger.error(
                    f"[Vehicle {vid}] [Plate {plate_text}] DB insert failed: {e}"
                )

        except Exception as e:
            logger.error(f"[Vehicle {vid}] Live OCR failed: {e}")

    def mark_seen(self, vid):
        self.missed_frames[vid] = 0

    def step_end(self, active_ids, frame_idx):
        finalized = []
        for vid in list(self.best_frames.keys()):
            if vid not in active_ids:
                self.missed_frames[vid] += 1
            else:
                continue

            if self.missed_frames[vid] > self.track_timeout:
                finalized.append(vid)
            elif (frame_idx - self.last_update.get(vid, 0)) > self.no_improve_patience:
                finalized.append(vid)

        return finalized

    def finalize(self, db, vid):
        """Clean up state; OCR is already done incrementally."""
        try:
            if vid in self.ocr_results:
                logger.info(f"[Vehicle {vid}] Final plate: {self.ocr_results[vid]}")
            self.cleanup(vid)
        except Exception as e:
            logger.error(f"[Vehicle {vid}] Finalize error: {e}")

    def cleanup(self, vid):
        self.best_frames.pop(vid, None)
        self.candidates.pop(vid, None)
        self.last_update.pop(vid, None)
        self.missed_frames.pop(vid, None)
        self.ocr_results.pop(vid, None)


def to_farsi_number(s):
    farsi_digits = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"]
    return "".join(farsi_digits[int(ch)] if ch.isdigit() else ch for ch in str(s))
