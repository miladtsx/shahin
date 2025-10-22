from collections import defaultdict
from heapq import heappush, heappop
from src.classify.classify import GlyphClassifier
from src.segmentation.segmentation import PlateSegmentation
from src.preprocessor.preprocessor import PlatePreprocessor
from src.common_utils.app_logger import get_logger
from src.common_utils.image_save import save
from src.common_utils.debug_image import show

logger = get_logger("best_frame_selector", logfile="logs/app.jsonl")
# @dev for easier visual debugging
LOG_UUID_FRACTION = 3


class OnlineBestFrameSelector:
    def __init__(
        self,
        scorer,
        no_improve_patience=20,  # Increased patience
        track_timeout=15,  # Increased timeout
    ):
        self.scorer = scorer

        self.best_sharp_frame = {}  # vid -> (score, crop, frame_idx, original_frame)
        self.best_visible_frame = {}  # vid -> (score, crop, frame_idx, original_frame)

        self.last_seen = {}  # vid -> last frame number it was seen
        self.missed_frames = defaultdict(int)
        self.last_known_frame = {}  # vid -> most recent original_frame for audit
        self.last_known_box = {}  # vid -> most recent bbox for audit
        self.finalized = set()
        self.lost_boxes = {}  # vid -> (bbox, last_seen_frame)

        # OCR components initialized once for efficiency
        self.preprocessor = PlatePreprocessor()
        self.segmentation = PlateSegmentation()
        self.classifier = GlyphClassifier()

        self.no_improve_patience = no_improve_patience
        self.track_timeout = track_timeout

    def update(
        self, vid, crop, plate_confidence, frame_idx, original_frame=None, bbox=None
    ):
        """
        Update the selector with a new candidate frame for a vehicle.
        This method only stores the best frame found so far, without triggering OCR.
        """
        score = plate_confidence

        self.last_seen[vid] = frame_idx
        self.missed_frames[vid] = 0  # Reset missed counter on update

        # 1. Update sharpest frame
        prev_score = self.best_sharp_frame.get(vid, (float("-inf"),))[0]
        if score > prev_score:
            self.best_sharp_frame[vid] = (
                score,
                crop.copy(),
                frame_idx,
                original_frame.copy(),
            )
            logger.debug(
                f"[Vehicle {vid[:LOG_UUID_FRACTION]}] New sharpest frame {score:.2f} at {frame_idx}"
            )

        # 2. Update fully visible frame if applicable
        if bbox is not None and self.is_fully_visible(bbox, original_frame.shape):
            prev_vid_score = self.best_visible_frame.get(vid, (float("-inf"),))[0]
            if score > prev_vid_score:
                self.best_visible_frame[vid] = (
                    score,
                    crop.copy(),
                    frame_idx,
                    original_frame.copy(),
                )
                logger.debug(
                    f"[Vehicle {vid[:LOG_UUID_FRACTION]}] New fully visible frame {score:.2f} at {frame_idx}"
                )

        return score

    def mark_seen(self, vid, frame_idx, original_frame=None):
        """Marks a vehicle as seen in the current frame, even if no plate was detected."""
        self.last_seen[vid] = frame_idx
        self.missed_frames[vid] = 0
        if original_frame is not None:
            # Store the latest frame for potential audit
            self.last_known_frame[vid] = original_frame.copy()

    def step_end(self, active_ids, frame_idx, active_boxes=None):
        """
        Decide which tracks to finalize at the end of each frame.
        Optionally takes active_boxes: dict[vid -> (x1, y1, x2, y2)]
        """
        finalized = []

        # Update last_known_box each frame
        if active_boxes:
            for vid, box in active_boxes.items():
                self.last_known_box[vid] = box

        # Try to reconnect lost tracks with new ones
        if active_boxes:
            for new_vid, new_box in active_boxes.items():
                for lost_vid, (lost_box, last_seen_fidx) in list(
                    self.lost_boxes.items()
                ):
                    if (
                        frame_idx - last_seen_fidx < self.track_timeout
                        and self.iou(new_box, lost_box) > 0.3
                    ):
                        logger.info(f"Merging {new_vid[:8]} ← {lost_vid[:8]}")
                        self.merge_ids(new_vid, lost_vid)
                        self.lost_boxes.pop(lost_vid, None)
                        break

        # Handle timeouts
        for vid in list(self.last_seen.keys()):
            if vid in self.finalized:
                continue
            if vid not in active_ids:
                self.missed_frames[vid] += 1
                if self.missed_frames[vid] > self.track_timeout + 1:
                    if vid in self.last_known_box:
                        # store last known box for spatial matching
                        self.lost_boxes[vid] = (
                            self.last_known_box[vid],
                            self.last_seen[vid],
                        )
                    # mark as pending finalization, not immediate
                    finalized.append(vid)

            else:
                self.missed_frames[vid] = 0
                self.last_seen[vid] = frame_idx

        # prune old lost
        self.lost_boxes = {
            v: (b, f)
            for v, (b, f) in self.lost_boxes.items()
            if frame_idx - f < 3 * self.track_timeout
        }

        # remove vids that just got merged (recovered from lost_boxes)
        finalized = [vid for vid in finalized if vid not in self.lost_boxes]

        return finalized

    def finalize(self, db, vid):
        """
        Processes the best available frame for a vehicle upon finalization.
        This is where OCR and database insertion happens.
        """
        if vid in self.finalized:
            logger.debug(
                f"[Vehicle {vid[:LOG_UUID_FRACTION]}] Already finalized, skipping."
            )
            return
        self.finalized.add(vid)

        best_frame_data = self.best_visible_frame.get(vid) or self.best_sharp_frame.get(
            vid
        )
        if not best_frame_data:
            last_frame = self.last_known_frame.get(vid)
            if last_frame is not None:
                logger.info(
                    f"[Vehicle {vid[:LOG_UUID_FRACTION]}] Saving last known frame for manual review."
                )
                save(last_frame, vid, "failed_capture")
                try:
                    # Insert into DB with a default/error value
                    db.insert_plate(vid, "DETECTION_FAILED")
                except Exception as e:
                    logger.error(
                        f"[Vehicle {vid[:LOG_UUID_FRACTION]}] DB insert failed for failed capture: {e}"
                    )
            else:
                logger.error(
                    f"[Vehicle {vid[:LOG_UUID_FRACTION]}] No frame available to save for failed capture."
                )

            self.cleanup(vid)
            return

        score, crop, frame_idx, original_frame = best_frame_data
        logger.info(
            f"[Vehicle {vid[:LOG_UUID_FRACTION]}] Finalizing with best frame from index {frame_idx} (score: {score:.2f})."
        )
        save(original_frame, vid, "original_final")
        save(crop, vid, "plate_final")

        try:
            preprocessed = self.preprocessor.preprocess(crop)
            # show(preprocessed, "Preprocessed_Final")
            glyphs = self.segmentation.segment(preprocessed, vid)
            if not glyphs:
                logger.warning(
                    f"[Vehicle {vid[:LOG_UUID_FRACTION]}] Segmentation failed, no glyphs found."
                )
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
                logger.warning(
                    f"[Vehicle {vid[:LOG_UUID_FRACTION]}] OCR resulted in an empty plate text."
                )
                self.cleanup(vid)
                return

            # logger.info(f"[Vehicle {vid[:LOG_UUID_FRACTION]}] Final plate: {plate_text}")
            db.insert_plate(vid, plate_text)

        except Exception as e:
            logger.error(
                f"[Vehicle {vid[:LOG_UUID_FRACTION]}] Final processing failed: {e}",
                exc_info=True,
            )
        finally:
            # Ensure cleanup happens even if processing fails
            self.cleanup(vid)

    def cleanup(self, vid):
        """Removes all tracking information for a vehicle ID."""
        self.best_sharp_frame.pop(vid, None)
        self.best_visible_frame.pop(vid, None)
        self.last_seen.pop(vid, None)
        self.missed_frames.pop(vid, None)
        self.last_known_frame.pop(vid, None)
        self.last_known_box.pop(vid, None)
        self.lost_boxes.pop(vid, None)
        # self.finalized.discard(vid)
        logger.debug(f"[Vehicle {vid[:LOG_UUID_FRACTION]}] Cleaned up tracking state.")

    def merge_ids(self, new_vid, lost_vid):
        if lost_vid in self.best_sharp_frame:
            self.best_sharp_frame[new_vid] = self.best_sharp_frame.pop(lost_vid)
        if lost_vid in self.best_visible_frame:
            self.best_visible_frame[new_vid] = self.best_visible_frame.pop(lost_vid)
        if lost_vid in self.last_seen:
            self.last_seen[new_vid] = self.last_seen.pop(lost_vid)
        if lost_vid in self.missed_frames:
            self.missed_frames[new_vid] = self.missed_frames.pop(lost_vid)
        self.finalized.discard(lost_vid)
        self.lost_boxes.pop(lost_vid, None)

    # merge new tracks with recently lost ones (fix ID resets)
    def iou(self, b1, b2):
        x1, y1, x2, y2 = b1
        X1, Y1, X2, Y2 = b2
        inter_x1 = max(x1, X1)
        inter_y1 = max(y1, Y1)
        inter_x2 = min(x2, X2)
        inter_y2 = min(y2, Y2)
        inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
        area1 = (x2 - x1) * (y2 - y1)
        area2 = (X2 - X1) * (Y2 - Y1)
        union = area1 + area2 - inter_area
        return inter_area / union if union > 0 else 0.0

    def is_fully_visible(self, bbox, frame_shape):
        x1, y1, x2, y2 = bbox
        h, w = frame_shape[:2]
        return x1 >= 0 and y1 >= 0 and x2 <= w and y2 <= h


def to_farsi_number(s):
    if s is None:
        return ""
    farsi_digits = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"]
    return "".join(farsi_digits[int(ch)] if ch.isdigit() else ch for ch in str(s))
