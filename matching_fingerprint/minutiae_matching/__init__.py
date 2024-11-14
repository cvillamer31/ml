import numpy as np
from typing import List
import cv2
import base64
from normalization import normalize
from segementation import create_segmented_and_variance_images
import orentation
from gabor_filter import gabor_filter
from frequency import ridge_freq

class Minutia:
    def __init__(self, x: int, y: int, angle: float, type: str):
        self.x = x
        self.y = y
        self.angle = angle
        self.type = type


def distance(m1: Minutia, m2: Minutia) -> float:
    # Calculate the Euclidean distance between two minutiae
    dx = m1.x - m2.x
    dy = m1.y - m2.y
    return np.sqrt(dx * dx + dy * dy)


def angle_difference(a1: float, a2: float) -> float:
    # Calculate the difference between two angles, in degrees
    return np.abs((a1 - a2 + 180) % 360 - 180)


def match_score(m1: Minutia, m2: Minutia) -> float:
    # Calculate the matching score between two minutiae
    d = distance(m1, m2)
    da = angle_difference(m1.angle, m2.angle)
    if d > 20 or da > 30:
        return 0.0
    else:
        return 1.0 - 0.1 * d - 0.4 * da / 30.0


def match(minutiae1: List[Minutia], minutiae2: List[Minutia]) -> float:
    # Calculate the matching score between two sets of minutiae
    score = 0.0
    for m1 in minutiae1:
        best_score = 0.0
        for m2 in minutiae2:
            s = match_score(m1, m2)
            if s > best_score:
                best_score = s
        score += best_score
    return score / len(minutiae1)


def extract_minutiae(image_path) -> List[Minutia]:
    # Load the fingerprint image and convert it to grayscale
    # image = cv2.imread(image_path)
    # image = image_path
    base64_data = image_path.split(",")[1]

    image_data = base64.b64decode(base64_data)
    block_size = 16
    np_array = np.frombuffer(image_data, np.uint8)
    image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # normalized_img = cv2.normalize(image, None, 100, 100, cv2.NORM_MINMAX)
    (segmented_img, normim, mask) = create_segmented_and_variance_images(gray, block_size, 0.2)
    angles = orentation.calculate_angles(gray, W=block_size, smoth=False)
    orientation_img = orentation.visualize_angles(segmented_img, mask, angles, W=block_size)
    freq = ridge_freq(normim, mask, angles, block_size, kernel_size=5, minWaveLength=5, maxWaveLength=15)
    gabor_img = gabor_filter(normim, angles, freq)
    # cv2.imshow('Grayscale Image', gabor_img )


    # # Wait for a key press and close the window
    # cv2.waitKey(0)  # Waits indefinitely until a key is pressed
    # cv2.destroyAllWindows()  # Closes all OpenCV windows
    # Apply a threshold to the image to create a binary image
    _, binary = cv2.threshold(gabor_img, 0, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    # print(binary)
    # Find the contours in the binary image
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Extract the minutiae from the contours
    minutiae = []
    for cnt in contours:
        hull = cv2.convexHull(cnt, returnPoints=False)
        hull[::-1].sort(axis=0)
        defects = cv2.convexityDefects(cnt, hull)
        if defects is not None:
            for i in range(defects.shape[0]):
                s, e, _, d = defects[i, 0]
                start = tuple(cnt[s][0])
                end = tuple(cnt[e][0])
                angle = np.arctan2(end[1]-start[1], end[0]-start[0]) * 180 / np.pi
                minutia = Minutia(start[0], start[1], angle, "ending")
                minutiae.append(minutia)
                if d > 100:
                    far = tuple(cnt[int((s+e)/2)][0])
                    minutia = Minutia(far[0], far[1], angle, "bifurcation")
                    minutiae.append(minutia)

    return minutiae
