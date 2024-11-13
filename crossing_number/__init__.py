import cv2 as cv
import numpy as np
import math

def minutiae_at(pixels, i, j, kernel_size):
    """
    https://airccj.org/CSCP/vol7/csit76809.pdf pg93
    Crossing number methods is a really simple way to detect ridge endings and ridge bifurcations.
    Then the crossing number algorithm will look at 3x3 pixel blocks:

    if middle pixel is black (represents ridge):
    if pixel on boundary are crossed with the ridge once, then it is a possible ridge ending
    if pixel on boundary are crossed with the ridge three times, then it is a ridge bifurcation

    :param pixels:
    :param i:
    :param j:
    :return:
    """
    # if middle pixel is black (represents ridge)
    if pixels[i][j] == 1:

        if kernel_size == 3:
            cells = [(-1, -1), (-1, 0), (-1, 1),        # p1 p2 p3
                   (0, 1),  (1, 1),  (1, 0),            # p8    p4
                  (1, -1), (0, -1), (-1, -1)]           # p7 p6 p5
        else:
            cells = [(-2, -2), (-2, -1), (-2, 0), (-2, 1), (-2, 2),                 # p1 p2   p3
                   (-1, 2), (0, 2),  (1, 2),  (2, 2), (2, 1), (2, 0),               # p8      p4
                  (2, -1), (2, -2), (1, -2), (0, -2), (-1, -2), (-2, -2)]           # p7 p6   p5

        values = [pixels[i + l][j + k] for k, l in cells]

        # count crossing how many times it goes from 0 to 1
        crossings = 0
        for k in range(0, len(values)-1):
            crossings += abs(values[k] - values[k + 1])
        crossings //= 2

        # if pixel on boundary are crossed with the ridge once, then it is a possible ridge ending
        # if pixel on boundary are crossed with the ridge three times, then it is a ridge bifurcation
        if crossings == 1:
            return "ending"
        if crossings == 3:
            return "bifurcation"

    return "none"

def calculate_direction(binary_image, position, kernel_size=5):
    """Calculates the ridge orientation at a given minutia point."""
    x, y = position
    half_size = kernel_size // 2
    
    # Extract neighborhood
    neighborhood = binary_image[max(y-half_size, 0):y+half_size+1, max(x-half_size, 0):x+half_size+1]
    neighborhood = neighborhood.astype(np.uint8)
    # Compute gradients
    grad_x = cv.Sobel(neighborhood, cv.CV_64F, 1, 0, ksize=3)
    grad_y = cv.Sobel(neighborhood, cv.CV_64F, 0, 1, ksize=3)
    
    # Average gradient direction
    angle = np.arctan2(grad_y.mean(), grad_x.mean())  # in radians
    angle_degrees = np.degrees(angle)
    return angle_degrees


def estimate_ridge_count(binary_image, position, search_radius=10):
    """Estimates ridge count by analyzing pixels within the radius of a minutia point."""
    x, y = position
    height, width = binary_image.shape
    
    ridge_count = 0
    last_pixel_value = binary_image[y, x]
    
    # Check pixels in a circular radius
    for angle in range(0, 360, 10):  # sampling every 10 degrees
        rad = np.radians(angle)
        for r in range(1, search_radius + 1):
            x_new = int(x + r * np.cos(rad))
            y_new = int(y + r * np.sin(rad))
            if 0 <= x_new < width and 0 <= y_new < height:
                pixel_value = binary_image[y_new, x_new]
                # Count ridge transitions (0 to 1 or 1 to 0)
                if pixel_value != last_pixel_value:
                    ridge_count += 1
                    last_pixel_value = pixel_value
            else:
                break  # Out of bounds

    return ridge_count // 2  # Dividing by 2 as each ridge transition has two sides

def find_neighbors(minutia, minutiae_list, distance_threshold=10):
    """Find all minutiae within a certain distance of the given minutia."""
    neighbors = []
    x1, y1 = minutia['position']
    
    for other_minutia in minutiae_list:
        if other_minutia == minutia:
            continue  # Skip the minutia itself
        x2, y2 = other_minutia['position']
        distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
        if distance <= distance_threshold:
            neighbors.append(other_minutia)
    
    return neighbors

def calculate_minutiaes(im, kernel_size=3):
    biniry_image = np.zeros_like(im)
    biniry_image[im<10] = 1.0
    biniry_image = biniry_image.astype(np.int8)

    (y, x) = im.shape
    result = cv.cvtColor(im, cv.COLOR_GRAY2RGB)
    colors = {"ending" : (150, 0, 0), "bifurcation" : (0, 150, 0)}
    minutiae_list = []  # To store minutiae details
    # iterate each pixel minutia
    for i in range(1, x - kernel_size//2):
        for j in range(1, y - kernel_size//2):
            minutiae = minutiae_at(biniry_image, j, i, kernel_size)
            if minutiae != "none":
                direction = calculate_direction(biniry_image, (i, j))
                ridge_count = estimate_ridge_count(biniry_image, (i, j))
                minutiae_list.append({
                    "type": minutiae, 
                    "position": (i, j),
                    "direction": direction,
                    "ridge_count": ridge_count
                })


                # minutiae_list.append({
                #     "neighbors": find_neighbors(minutiae_list, minutiae_list, 10), 
                # })

                # dta = find_neighbors(minutiae_list, minutiae_list, 10);
                # print(dta)
                # minutiae_list['neighbors'] = find_neighbors(minutiae_list, minutiae_list, 10)
                cv.circle(result, (i,j), radius=2, color=colors[minutiae], thickness=2)

    return result, minutiae_list