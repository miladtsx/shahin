from collections import defaultdict
from heapq import heappush, heappop
from src.classify.classify import GlyphClassifier
from src.segmentation.segmentation import PlateSegmentation
from src.preprocessor.preprocessor import PlatePreprocessor
from src.common_utils.app_logger import get_logger
from src.common_utils.image_save import save
from src.common_utils.debug_image import show

logger = get_logger("best_frame_selector", logfile="logs/app.jsonl")


class OnlineBestFrameSelector:
    def __init__(
        self,
        scorer,
        no_improve_patience=20,  # Increased patience
        track_timeout=15,  # Increased timeout
    ):
        self.scorer = scorer
        self.best_frames = {}  # vid -> (score, crop, frame_idx, original_frame)
        self.last_seen = {}  # vid -> last frame number it was seen
        self.missed_frames = defaultdict(int)
        self.last_known_frame = {}  # vid -> most recent original_frame for audit

        # OCR components initialized once for efficiency
        self.preprocessor = PlatePreprocessor()
        self.segmentation = PlateSegmentation()
        self.classifier = GlyphClassifier()

        self.no_improve_patience = no_improve_patience
        self.track_timeout = track_timeout

    def update(self, vid, crop, frame_idx, original_frame=None):
        """
        Update the selector with a new candidate frame for a vehicle.
        This method only stores the best frame found so far, without triggering OCR.
        """
        score = self.scorer(crop)
        self.last_seen[vid] = frame_idx
        self.missed_frames[vid] = 0  # Reset missed counter on update

        prev_best_score = self.best_frames.get(vid, (float("-inf"),))[0]
        if score > prev_best_score:
            # Found a new best frame, store it.
            # We store a copy of the crop and frame to avoid issues with buffer reuse.
            self.best_frames[vid] = (
                score,
                crop.copy(),
                frame_idx,
                original_frame.copy(),
            )
            logger.debug(
                f"[Vehicle {vid}] New best frame found with score {score:.2f} at frame {frame_idx}."
            )

        return score

    def mark_seen(self, vid, frame_idx, original_frame=None):
        """Marks a vehicle as seen in the current frame, even if no plate was detected."""
        self.last_seen[vid] = frame_idx
        self.missed_frames[vid] = 0
        if original_frame is not None:
            # Store the latest frame for potential audit
            self.last_known_frame[vid] = original_frame.copy()

    def step_end(self, active_ids, frame_idx):
        """
        Identifies tracks that should be finalized because they are no longer active
        or haven't improved for a while.
        """
        finalized = []
        all_tracked_vids = list(self.last_seen.keys())

        for vid in all_tracked_vids:
            # Condition 1: Vehicle has disappeared from the frame
            if vid not in active_ids:
                self.missed_frames[vid] += 1
                if self.missed_frames[vid] > self.track_timeout:
                    finalized.append(vid)
                    continue

            # Condition 2: Vehicle is present, but no better frame has been found recently
            if vid in self.best_frames:
                last_improvement_frame = self.best_frames[vid][2]
                if (frame_idx - last_improvement_frame) > self.no_improve_patience:
                    finalized.append(vid)

        return list(set(finalized))

    def finalize(self, db, vid):
        """
        Processes the best available frame for a vehicle upon finalization.
        This is where OCR and database insertion happens.
        """
        best_frame_data = self.best_frames.get(vid)
        if not best_frame_data:
            logger.warning(
                f"[Vehicle {vid}] Finalized without any suitable plate candidate."
            )
            last_frame = self.last_known_frame.get(vid)
            if last_frame is not None:
                logger.info(f"[Vehicle {vid}] Saving last known frame for manual review.")
                save(last_frame, vid, "failed_capture")
                try:
                    # Insert into DB with a default/error value
                    db.insert_plate(vid, "DETECTION_FAILED")
                except Exception as e:
                    logger.error(
                        f"[Vehicle {vid}] DB insert failed for failed capture: {e}"
                    )
            else:
                logger.error(f"[Vehicle {vid}] No frame available to save for failed capture.")

            self.cleanup(vid)
            return

        score, crop, frame_idx, original_frame = best_frame_data
        logger.info(
            f"[Vehicle {vid}] Finalizing with best frame from index {frame_idx} (score: {score:.2f})."
        )
        save(original_frame, vid, "original_final")
        save(crop, vid, "plate_final")

        try:
            preprocessed = self.preprocessor.preprocess(crop)
            # show(preprocessed, "Preprocessed_Final")
            glyphs = self.segmentation.segment(preprocessed, vid)
            if not glyphs:
                logger.warning(f"[Vehicle {vid}] Segmentation failed, no glyphs found.")
                self.cleanup(vid)
                return

            final_plate_text = [""] * 8
            for idx, g in glyphs:
                if idx == 2:
                    class_name = self.classifier.classify_alphabet(g).get("class_name")
                else:
                    class_name = to_farsi_number(
                        self.classifier.classify_digit(g).get("class_name")
                    )
                final_plate_text[idx] = class_name if class_name else ""

            plate_text = "".join(final_plate_text).strip()
            if not plate_text:
                logger.warning(f"[Vehicle {vid}] OCR resulted in an empty plate text.")
                self.cleanup(vid)
                return

            logger.info(f"[Vehicle {vid}] Final plate: {plate_text}")
            db.insert_plate(vid, plate_text)

        except Exception as e:
            logger.error(f"[Vehicle {vid}] Final processing failed: {e}", exc_info=True)
        finally:
            # Ensure cleanup happens even if processing fails
            self.cleanup(vid)

    def cleanup(self, vid):
        """Removes all tracking information for a vehicle ID."""
        self.best_frames.pop(vid, None)
        self.last_seen.pop(vid, None)
        self.missed_frames.pop(vid, None)
        self.last_known_frame.pop(vid, None)
        logger.debug(f"[Vehicle {vid}] Cleaned up tracking state.")


def to_farsi_number(s):
    if s is None:
        return ""
    farsi_digits = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"]
    return "".join(farsi_digits[int(ch)] if ch.isdigit() else ch for ch in str(s))