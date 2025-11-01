from collections import defaultdict
from heapq import heappush, nlargest
from src.classify.classify import GlyphClassifier
from src.segmentation.segmentation import PlateSegmentation
from src.preprocessor.preprocessor import PlatePreprocessor
from src.common_utils.app_logger import get_logger
from src.common_utils.image_save import save
from src.common_utils.debug_image import show, draw_boxes
from src.common_utils.config import Config, MyConfig
from dataclasses import dataclass
import numpy as np
from typing import Dict, List, Tuple
import time

logger = get_logger("best_frame_selector", logfile="logs/app.jsonl")
# @dev for easier visual debugging
LOG_UUID_FRACTION = 3
TOP_K = 10  # keep top 10 frames per vehicle


@dataclass
class FrameData:
    confidence_score: float
    cropped_frame: np.ndarray
    frame_idx: int
    full_frame: np.ndarray


class BestFrameSelector:
    def __init__(
        self,
        db,
        scorer,
        no_improve_patience=20,  # Increased patience
        track_timeout=15,  # Increased timeout
    ):
        self.scorer = scorer
        self.db = db
        self.config: MyConfig = Config().config

        self.top_plates: Dict[str, List[Tuple[float, int, FrameData]]] = {}
        self.top_fully_visible_vehicle: Dict[
            str, List[Tuple[float, int, FrameData]]
        ] = {}

        self.last_seen_frame_idx = {}  # vid -> last frame number it was seen
        self.missed_frames = defaultdict(int)
        # To prevent cars escaping
        self.last_known_full_frame = {}
        self.last_known_box_for_spatial_matching = {}
        self.finalized = set()
        self.lost_boxes = {}  # vid -> (bbox, last_seen_frame)
        self.pending_failures: Dict[str, Dict] = {}

        # OCR components initialized once for efficiency
        self.preprocessor = PlatePreprocessor()
        self.segmentation = PlateSegmentation()
        self.classifier = GlyphClassifier()

        self.no_improve_patience = no_improve_patience
        self.track_timeout = track_timeout
        failure_grace_cfg = self.config.get("failure_grace_seconds")
        self.failure_grace_seconds = (
            int(failure_grace_cfg) if failure_grace_cfg is not None else 10
        )

    def update(
        self,
        vid,
        crop,
        frame_idx,
        full_frame,
        vehicle_bbox,
    ):
        """
        Update the selector with a new candidate frame for a vehicle.
        This method only stores the best frame found so far, without triggering OCR.
        """
        self.last_seen_frame_idx[vid] = frame_idx
        self.missed_frames[vid] = 0

        quality_score = self.scorer(crop)
        if quality_score == 0.0:
            return
        # --- Update plate confidence candidates ---
        heap: List[Tuple[float, int, FrameData]] = self.top_plates.setdefault(vid, [])
        heappush(
            heap,
            (
                quality_score,
                frame_idx,
                FrameData(quality_score, crop.copy(), frame_idx, full_frame.copy()),
            ),
        )
        # keep only top K by confidence
        self.top_plates[vid] = nlargest(TOP_K, heap, key=lambda x: x[0])

        # --- Update fully visible vehicle candidates ---
        if vehicle_bbox is not None and self.is_fully_visible(
            vehicle_bbox, full_frame.shape
        ):
            heap_vis: List[Tuple[float, int, FrameData]] = (
                self.top_fully_visible_vehicle.setdefault(vid, [])
            )
            visibility_score = (
                quality_score  # could replace with sharpness or other metric
            )
            heappush(
                heap_vis,
                (
                    visibility_score,
                    frame_idx,
                    FrameData(quality_score, crop.copy(), frame_idx, full_frame.copy()),
                ),
            )
            self.top_fully_visible_vehicle[vid] = nlargest(
                TOP_K, heap_vis, key=lambda x: x[0]
            )

    def mark_seen(self, vid, frame_idx, original_frame=None):
        """Marks a vehicle as seen in the current frame, even if no plate was detected."""
        self.last_seen_frame_idx[vid] = frame_idx
        self.missed_frames[vid] = 0
        if original_frame is not None:
            # Store the latest frame for potential audit
            self.last_known_full_frame[vid] = original_frame.copy()

    def to_finalize(self, active_ids, frame_idx, active_boxes=None):
        """
        Decide which tracks to finalize at the end of each frame.
        Optionally takes active_boxes: dict[vid -> (x1, y1, x2, y2)]
        """
        finalized = []

        # TODO use last_known_frame instead!
        # which contains the full frame
        # Update last_known_box each frame
        if active_boxes:
            for vid, box in active_boxes.items():
                self.last_known_box_for_spatial_matching[vid] = box

        # Try to reconnect lost tracks with new ones
        if active_boxes:
            for new_vid, new_box in active_boxes.items():
                cx_new, cy_new = (new_box[0] + new_box[2]) // 2, (
                    new_box[1] + new_box[3]
                ) // 2
                for lost_vid, (lost_box, last_seen_fidx) in list(
                    self.lost_boxes.items()
                ):
                    if frame_idx - last_seen_fidx >= self.track_timeout:
                        continue
                    cx_lost, cy_lost = (lost_box[0] + lost_box[2]) // 2, (
                        lost_box[1] + lost_box[3]
                    ) // 2
                    dist = ((cx_new - cx_lost) ** 2 + (cy_new - cy_lost) ** 2) ** 0.5
                    if dist < 50:  # tune this threshold to your camera/frame size
                        logger.info(
                            f"Merging {new_vid[:LOG_UUID_FRACTION]} ← {lost_vid[:LOG_UUID_FRACTION]} via centroid distance"
                        )
                        self.merge_ids(new_vid, lost_vid, frame_idx)
                        self.lost_boxes.pop(lost_vid, None)
                        break

        # If the car is out of the hotzone, mark it to be finalized
        for vid in list(self.last_seen_frame_idx.keys()):
            # Remove potential duplicates
            if vid in self.finalized:
                continue
            if vid not in active_ids:
                self.missed_frames[vid] += 1
                if self.missed_frames[vid] > self.track_timeout + 1:
                    if vid in self.last_known_box_for_spatial_matching:
                        self.lost_boxes[vid] = (
                            self.last_known_box_for_spatial_matching[vid],
                            self.last_seen_frame_idx[vid],
                        )
                    finalized.append(vid)
            else:
                self.missed_frames[vid] = 0
                self.last_seen_frame_idx[vid] = frame_idx

        # TODO how about logging the old lost ones? in case we missed any car?
        # prune old lost
        self.lost_boxes = {
            vid: (spatial_box, last_seen_f_idx)
            for vid, (spatial_box, last_seen_f_idx) in self.lost_boxes.items()
            if frame_idx - last_seen_f_idx < 3 * self.track_timeout
        }

        # remove vids that just got merged (recovered from lost_boxes)
        finalized = [vid for vid in finalized if vid not in self.lost_boxes]

        return finalized

    def finalize(self, vid, frame_idx=None):
        """Selects and saves the best frame once a vehicle leaves the hotzone."""

        if vid in self.finalized:
            return
        self.finalized.add(vid)

        pending_record = self.pending_failures.get(vid)

        # Extract and remove best candidates so we can still inspect them before cleanup
        plate_candidates = self.top_plates.pop(vid, [])
        vehicle_candidates = self.top_fully_visible_vehicle.pop(vid, [])

        # Pick best available frame
        best_frame_data = None
        if plate_candidates:
            best_frame_data = max(plate_candidates, key=lambda x: x[0])[2]
        elif vehicle_candidates:
            best_frame_data = max(vehicle_candidates, key=lambda x: x[0])[2]

        if not best_frame_data:
            last_frame = self.last_known_full_frame.get(vid)
            last_known_box = self.last_known_box_for_spatial_matching.get(vid)
            last_seen_idx = self.last_seen_frame_idx.get(vid, frame_idx)
            if last_frame is not None:
                # annotate the last frame with a box if available
                if last_known_box is not None:
                    x1, y1, x2, y2 = last_known_box
                    # center, double width/height, clamp to image bounds
                    cx = (x1 + x2) / 2.0
                    cy = (y1 + y2) / 2.0
                    w = (x2 - x1) * 2.0
                    h = (y2 - y1) * 2.0
                    new_x1 = int(max(0, cx - w / 2.0))
                    new_y1 = int(max(0, cy - h / 2.0))
                    new_x2 = int(min(last_frame.shape[1], cx + w / 2.0))
                    new_y2 = int(min(last_frame.shape[0], cy + h / 2.0))
                    draw_boxes(
                        last_frame, [{"bbox": (new_x1, new_y1, new_x2, new_y2)}], "?"
                    )
                save(last_frame, vid, "failed_capture")
                failure_record = {
                    "timestamp": time.time(),
                    "camera_location": self.config.get("camera_location"),
                    "db_uuid": vid,
                    "last_box": last_known_box,
                    "last_seen_idx": last_seen_idx,
                }
                self.pending_failures[vid] = failure_record
                self.db.insert_plate(
                    vid, "DETECTION_FAILED", self.config.get("camera_location")
                )
            else:
                # TODO real error that must be sent to dev team
                # A car triggered detection but nothing is saved
                logger.error(
                    f"[Vehicle {vid[:LOG_UUID_FRACTION]}] No frame available to save."
                )
                failure_record = None

            lost_entry = None
            if failure_record and failure_record.get("last_box") is not None:
                lost_entry = (
                    failure_record["last_box"],
                    failure_record.get("last_seen_idx", frame_idx),
                )

            self._cleanup_tracking_state(vid)
            if lost_entry and all(v is not None for v in lost_entry):
                self.lost_boxes[vid] = lost_entry
            return

        artifact_uuid = (
            pending_record["db_uuid"]
            if pending_record and pending_record.get("db_uuid")
            else vid
        )

        # Save best frames
        save(best_frame_data.full_frame, artifact_uuid, "original")
        save(best_frame_data.cropped_frame, artifact_uuid, "plate")
        try:
            preprocessed = self.preprocessor.preprocess(best_frame_data.cropped_frame)
            # show(preprocessed, "Preprocessed_Final")
            glyphs = self.segmentation.segment(preprocessed, vid)
            if not glyphs:
                logger.error(f"[Vehicle {vid}] Segmentation failed, no glyphs found.")
                self._cleanup_tracking_state(vid)
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
                logger.error(f"[Vehicle {vid}] OCR resulted in an empty plate text.")
                self._cleanup_tracking_state(vid)
                return

            logger.info(
                f"[Vehicle {vid[:LOG_UUID_FRACTION]}] Final plate: {plate_text}"
            )
            resolved_uuid = None
            if pending_record and pending_record.get("db_uuid"):
                resolved_uuid = self.db.resolve_failed_detection(
                    pending_record["db_uuid"], plate_text
                )
            target_uuid = resolved_uuid or vid
            self.db.insert_plate(
                target_uuid, plate_text, self.config.get("camera_location")
            )

        except Exception as e:
            logger.error(
                f"[Vehicle {vid}] Final processing failed: {e}",
                exc_info=True,
            )
        finally:
            # Successful or not, this VID no longer needs a pending failure entry.
            self.pending_failures.pop(vid, None)
            # Clean lightweight tracking data only (heaps already popped)
            self._cleanup_tracking_state(vid)

    def _cleanup_tracking_state(self, vid):
        """Internal cleanup that leaves already-popped heaps untouched."""
        for d in [
            self.last_seen_frame_idx,
            self.missed_frames,
            self.last_known_full_frame,
            self.last_known_box_for_spatial_matching,
            self.lost_boxes,
        ]:
            d.pop(vid, None)

    def merge_ids(self, new_vid, lost_vid, frame_idx=None):
        if lost_vid in self.top_plates:
            self.top_plates[new_vid] = self.top_plates.pop(lost_vid)
        if lost_vid in self.top_fully_visible_vehicle:
            self.top_fully_visible_vehicle[new_vid] = (
                self.top_fully_visible_vehicle.pop(lost_vid)
            )
        if lost_vid in self.last_seen_frame_idx:
            self.last_seen_frame_idx[new_vid] = self.last_seen_frame_idx.pop(lost_vid)
        if lost_vid in self.missed_frames:
            self.missed_frames[new_vid] = self.missed_frames.pop(lost_vid)
        self.finalized.discard(lost_vid)
        self.lost_boxes.pop(lost_vid, None)
        if lost_vid in self.pending_failures:
            data = self.pending_failures.pop(lost_vid)
            data["timestamp"] = time.time()
            if frame_idx is not None:
                data["last_seen_idx"] = frame_idx
            if new_vid in self.last_known_box_for_spatial_matching:
                data["last_box"] = self.last_known_box_for_spatial_matching[new_vid]
            self.pending_failures[new_vid] = data

    def is_fully_visible(self, bbox, frame_shape):
        x1, y1, x2, y2 = bbox
        h, w = frame_shape[:2]
        return x1 >= 0 and y1 >= 0 and x2 <= w and y2 <= h

    def flush_pending_failures(self, force=False):
        if not self.pending_failures:
            return

        now = time.time()
        to_flush = []
        if force:
            to_flush = list(self.pending_failures.keys())
        else:
            for vid, data in self.pending_failures.items():
                ts = data.get("timestamp", now)
                if ts is None or now - ts >= self.failure_grace_seconds:
                    to_flush.append(vid)

        for vid in to_flush:
            self.pending_failures.pop(vid, None)
            self.lost_boxes.pop(vid, None)


def to_farsi_number(s):
    if s is None:
        return ""
    farsi_digits = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"]
    return "".join(farsi_digits[int(ch)] if ch.isdigit() else ch for ch in str(s))
