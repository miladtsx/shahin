import matplotlib.pyplot as plt
import cv2

def show(img, title="debug"):
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    plt.figure(title)
    plt.imshow(img, cmap="gray" if img.ndim == 2 else None)
    plt.axis("off")
    plt.show(block=False)
    plt.pause(1)