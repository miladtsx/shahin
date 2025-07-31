import numpy as np

class SimpleTracker:
    def __init__(self, iou_threshold=0.5):
        self.next_id = 0
        self.tracks = {}
        self.iou_threshold = iou_threshold
    
    def _iou(self, boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        if interArea == 0:
            return 0.0
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        iou = interArea / float(boxAArea + boxBArea - interArea)
        return iou

    def update(self, detections):
        assigned = []
        new_tracks = {}

        for det in detections:
            matched = False
            for track_id, prev_box in self.tracks.items():
                iou = self._iou(det["bbox"], prev_box)
                if iou >= self.iou_threshold:
                    det["id"] = track_id
                    new_tracks[track_id] = det["bbox"]
                    assigned.append(track_id)
                    matched = True
                    break
            if not matched:
                det["id"] = self.next_id
                new_tracks[self.next_id] = det["bbox"]
                self.next_id += 1

        self.tracks = new_tracks
        return detections