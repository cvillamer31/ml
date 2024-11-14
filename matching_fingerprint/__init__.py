# import minutiae_matching
from . import minutiae_matching
import numpy as np
from typing import List
import cv2
import base64




def fingerprints_matching(image_path1, image_path2):
    # Extract the minutiae from the two images
    minutiae1 = minutiae_matching.extract_minutiae(image_path1)
    minutiae2 = minutiae_matching.extract_minutiae(image_path2)

    # Perform minutiae matching
    match_result = minutiae_matching.match(minutiae1, minutiae2)

    # Return the matching score
    return match_result
