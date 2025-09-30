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
        no_improve_patience=10,  # frames without improvement
        track_timeout=10,
        k=10,
    ):  # frames after track disappears
        self.scorer = scorer
        self.candidates = defaultdict(list)  # vid -> [(score, frame_idx, crop), ...]
        self.best_frames = {}  # vid -> best_crop
        self.best_scores = defaultdict(lambda: -1.0)
        self.last_update = {}  # vid -> last frame number
        self.missed_frames = defaultdict(int)  # vid -> how many frames since last seen
        self.k = k

        self.no_improve_patience = no_improve_patience
        self.track_timeout = track_timeout

    def update(self, vid, crop, frame_idx):
        score = self.scorer(crop)
        heappush(self.candidates[vid], (score, frame_idx, crop))
        if len(self.candidates[vid]) > self.k:
            heappop(self.candidates[vid])  # drop worst
        self.last_update[vid] = frame_idx
        self.missed_frames[vid] = 0
        return score

    def mark_seen(self, vid):
        self.missed_frames[vid] = 0

    def step_end(self, active_ids, frame_idx):
        """
        Call once per frame after updating all tracks.
        active_ids: set of IDs seen this frame
        frame_idx: current frame number
        """
        finalized = []
        for vid in list(self.best_frames.keys()):
            if vid not in active_ids:
                self.missed_frames[vid] += 1
            else:
                continue

            # finalize if track missing too long
            if self.missed_frames[vid] > self.track_timeout:
                finalized.append(vid)

            # or finalize if no improvement for too long
            elif (frame_idx - self.last_update.get(vid, 0)) > self.no_improve_patience:
                finalized.append(vid)

        return finalized

    def finalize(self, db, vid):
        """Select the best frame (Save to disk for debugging)."""
        try:
            if vid not in self.candidates:
                return
    
            # pick the best-scoring crop
            best_score, frame_idx, best_crop = max(self.candidates[vid], key=lambda x: x[0])
            
            save(best_crop, vid, "best")

            # downstream processing: use full path for processors
            preprocessor = PlatePreprocessor()
            preprocessor.preprocess(best_crop)

            segmentation = PlateSegmentation()
            glyphs = segmentation.segment(best_crop, vid)

            # Classify
            if glyphs is None:
                return

            classifier = GlyphClassifier()

            final_plate_text = [""] * 8

            def classify_glyph(idx_g):
                idx, g = idx_g
                try:
                    # item index 2 is non-digit.
                    if idx == 2:
                        class_id = classifier.classify_alphabet(g).get("class_name")
                    else:
                        class_id = to_farsi_number(
                            classifier.classify_digit(g).get("class_name")
                        )
                    return idx, str(class_id) if class_id is not None else ""
                except Exception as e:
                    logger.error(f"Glyph classification failed idx={idx} {e}")
                    raise

            # with ThreadPoolExecutor() as executor:
            #     results = executor.map(classify_glyph, glyphs)
            results = map(classify_glyph, glyphs)

            for idx, class_name in results:
                final_plate_text[idx] = class_name

            plate_text = "".join(final_plate_text)

            try:
                db.insert_plate(vid, plate_text)
            except Exception as e:
                logger.error(
                    f"[Vehicle {vid}] [Plate {plate_text}] ⚠️ Failed to write to DB: {e}"
                )
            finally:
                self.cleanup(vid)

            return final_plate_text
        except Exception as e:
            logger.error(f"[Vehicle {vid}] ⚠️ Failed to finalize track: {e}")

    def cleanup(self, vid):
        # Cleanup
        self.best_frames.pop(vid, None)
        self.best_scores.pop(vid, None)
        self.last_update.pop(vid, None)
        self.missed_frames.pop(vid, None)


def to_farsi_number(s):
    farsi_digits = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"]
    return "".join(farsi_digits[int(ch)] if ch.isdigit() else ch for ch in str(s))
