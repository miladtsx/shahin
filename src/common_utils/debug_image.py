import matplotlib.pyplot as plt
import cv2
from matplotlib.pyplot import title


def show(img, title="debug"):
    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(title, 640, 480)
    cv2.imshow(title, img)
    cv2.waitKey(1)


def draw_boxes(frame, detections, label="obj", color=(0, 255, 0)):
    """
    detections: list of dicts with 'bbox' and optional 'conf'
    bbox format: (x1, y1, x2, y2)
    """
    for det in detections:
        x1, y1, x2, y2 = map(int, det["bbox"])
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        vid = det.get("id")
        txt = f"{(vid and vid[:3]) or label}"
        if "conf" in det:
            txt += f" {det['conf']:.2f}"

        # small text above box
        cv2.putText(frame, txt, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # large text inside box (centered)
        text_size, _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)
        text_w, text_h = text_size
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        cv2.putText(
            frame,
            txt,
            (cx - text_w // 2, cy + text_h // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            color,
            3,
        )
    return frame
