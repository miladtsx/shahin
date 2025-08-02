from collections import defaultdict

class BestFrameSelector:
    def __init__(self, scorer):
        self.best_frames = {}
        self.best_scores = defaultdict(lambda: -1.0)
        self.score_quality = scorer

    def update(self, plate_id, crop):
        score = self.score_quality(crop)
        if score > self.best_scores[plate_id]:
            self.best_scores[plate_id] = score
            self.best_frames[plate_id] = crop
        return score

    def get_best_frames(self):
        return self.best_frames