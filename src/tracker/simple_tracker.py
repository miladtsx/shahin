import numpy as np
import cv2
import hashlib

def compute_hash(image):
    #TODO Replace hashlib with perceptual hash like phash (PIL + DCT).
    return hashlib.md5(cv2.resize(image, (16, 16)).tobytes()).hexdigest()

class PlateTrack:
    def __init__(self, track_id, bbox, crop, frame_number):
        self.id = track_id
        self.bbox = bbox
        self.centroid = self._get_centroid(bbox)
        self.image_hash = compute_hash(crop)
        self.last_frame = frame_number

    def _get_centroid(self, bbox):
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def is_similar(self, bbox, crop, frame_number, distance_thresh=30, hash_thresh=5):
        c_new = self._get_centroid(bbox)
        dist = np.linalg.norm(np.array(self.centroid) - np.array(c_new))
        if dist > distance_thresh:
            return False

        hash_new = compute_hash(crop)
        hamming_dist = sum(a != b for a, b in zip(self.image_hash, hash_new))
        if hamming_dist > hash_thresh:
            return False

        # Update track
        self.bbox = bbox
        self.centroid = c_new
        self.image_hash = hash_new
        self.last_frame = frame_number
        return True


class PlateTracker:
    def __init__(self, max_age=30):
        self.tracks = []
        self.next_id = 0
        self.max_age = max_age

    def update(self, detections, frame, frame_number):
        results = []
        new_tracks = []

        for det in detections:
            bbox = det["bbox"]
            x1, y1, x2, y2 = map(int, bbox)
            crop = frame[y1:y2, x1:x2]
            assigned = False

            for track in self.tracks:
                if track.is_similar(bbox, crop, frame_number):
                    det["id"] = track.id
                    results.append(det)
                    new_tracks.append(track)
                    assigned = True
                    break

            if not assigned:
                track = PlateTrack(self.next_id, bbox, crop, frame_number)
                det["id"] = self.next_id
                self.next_id += 1
                results.append(det)
                new_tracks.append(track)

        # Remove old tracks
        self.tracks = [
            t for t in new_tracks if frame_number - t.last_frame <= self.max_age
        ]
        return results
