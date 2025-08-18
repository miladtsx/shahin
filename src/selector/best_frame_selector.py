from collections import defaultdict
import os
import cv2
from src.segmentation.segmentation import PlateSegmention
from src.common_utils.config import Config
from src.preprocessor.preprocessor import PlatePreprocessor


class OnlineBestFrameSelector:
    def __init__(
        self,
        scorer,
        output_dir,
        no_improve_patience=10,  # frames without improvement
        track_timeout=10,
    ):  # frames after track disappears
        self.scorer = scorer
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        self.best_frames = {}  # vid -> best_crop
        self.best_scores = defaultdict(lambda: -1.0)
        self.last_update = {}  # vid -> last frame number
        self.missed_frames = defaultdict(int)  # vid -> how many frames since last seen

        self.no_improve_patience = no_improve_patience
        self.track_timeout = track_timeout

    def update(self, vid, crop, frame_idx):
        score = self.scorer(crop)
        improved = False
        if score > self.best_scores[vid]:
            self.best_scores[vid] = score
            self.best_frames[vid] = crop
            self.last_update[vid] = frame_idx
            improved = True
        return score, improved

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

    def finalize(self, vid):
        """Save best frame to disk and cleanup."""
        file_name = f"Vehicle_{vid}_plate.jpg"
        file_path = os.path.join(self.output_dir, file_name)
        if vid in self.best_frames:
            cv2.imwrite(file_path, self.best_frames[vid])
            # print(f"[Vehicle {vid}] ✅ Finalized and saved best plate")
        else:
            print(f"[Vehicle {vid}] ⚠️ No plate detected, operator input needed")
        self.best_frames.pop(vid, None)
        self.best_scores.pop(vid, None)
        self.last_update.pop(vid, None)
        self.missed_frames.pop(vid, None)

        preprocessor = PlatePreprocessor()
        preprocessor.preprocess(file_name)

        segmentation = PlateSegmention()
        segmentation.segment(file_name)


