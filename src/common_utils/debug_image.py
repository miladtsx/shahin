import matplotlib.pyplot as plt
import cv2
from matplotlib.pyplot import title

def show(img, title="debug"):
    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(title, 640, 480)
    cv2.imshow(title, img)
    cv2.waitKey(1)