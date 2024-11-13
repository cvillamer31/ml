from flask import Flask, request, jsonify
import base64
import mysql.connector
import cv2
import numpy as np
from normalization import normalize
from segementation import create_segmented_and_variance_images
import orentation
from frequency import ridge_freq
from gabor_filter import gabor_filter
from skeletonize import skeletonize
from crossing_number import calculate_minutiaes
from poincare import calculate_singularities
# from fingerprints_matching import FingerprintsMatching
from scipy.spatial.distance import euclidean
import math

# print(fingerprints_matching.__file__)

app = Flask(__name__)

# Set up MySQL connection
db = mysql.connector.connect(
    host="172.105.116.65",
    user="philstud_ml",
    password="Rk88j;OcQ8f3",
    database="philstud_biomentrics",
    ssl_disabled=True  # Disable SSL if not required
)

# Function to fetch fingerprints from the database
def get_fingerprints_from_database(user_id):
    cursor = db.cursor()
    query = 'SELECT id, name FROM users WHERE pin = %s'
    cursor.execute(query, (user_id,))
    results = cursor.fetchall()
    # print(results)
    if results:
        fingerprints = results[0]
        if fingerprints[0] > 0:  # Checking if the user exists
            query_fingerprint = 'SELECT id, user_id, img_1, img_2, img_3 FROM biometrics_data WHERE user_id = %s'
            cursor.execute(query_fingerprint, (fingerprints[0],))
            results_fingerprint = cursor.fetchall()

            if results_fingerprint:
                fingerprints_data = results_fingerprint[0]  # Only return the first match
                return fingerprints_data
            else:
                raise Exception("No biometrics data found for this user")
        else:
            raise Exception("User not found")
    else:
        raise Exception("User not found")




def calculate_angle(minutia1, minutia2):
    """Calculate the angle between two minutiae points (in degrees)."""
    x1, y1 = minutia1['position']
    x2, y2 = minutia2['position']
    
    # Calculate the differences in x and y coordinates
    delta_x = x2 - x1
    delta_y = y2 - y1
    
    # Calculate the angle in radians and convert to degrees
    angle = math.atan2(delta_y, delta_x)
    angle_degrees = math.degrees(angle)
    
    # Normalize angle to be between 0 and 360 degrees
    if angle_degrees < 0:
        angle_degrees += 360
    
    return angle_degrees


def calculate_signature_vector(minutia, neighbors):
    """Calculate features like type, orientation, and distance to neighbors"""
    type = minutia['type']
    orientation = minutia['direction']
    # Example with distance to closest neighbor
    relative_distance = euclidean(minutia['position'], neighbors[0]['position']) if neighbors else 0
    angle_to_neighboring = calculate_angle(minutia, neighbors[0]) if neighbors else 0
    return [type, orientation, relative_distance, angle_to_neighboring]

def fingerprint_pipline(input_img):
    block_size = 16
    base64_data = input_img.split(",")[1]
    image_data = base64.b64decode(base64_data)
    np_array = np.frombuffer(image_data, np.uint8)
    image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
    grayscale_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    normalized_img = normalize(grayscale_image.copy(), float(100), float(100))
     # ROI and normalisation
    (segmented_img, normim, mask) = create_segmented_and_variance_images(normalized_img, block_size, 0.2)

    angles = orentation.calculate_angles(normalized_img, W=block_size, smoth=False)
    orientation_img = orentation.visualize_angles(segmented_img, mask, angles, W=block_size)
    # find the overall frequency of ridges in Wavelet Domain
    freq = ridge_freq(normim, mask, angles, block_size, kernel_size=5, minWaveLength=5, maxWaveLength=15)
     # create gabor filter and do the actual filtering
    gabor_img = gabor_filter(normim, angles, freq)
     # thinning oor skeletonize
    thin_image = skeletonize(gabor_img)

    # minutias
    minutias = calculate_minutiaes(thin_image)

    # print(minutias[1])
    return minutias[1]
    # singularities
    singularities_img = calculate_singularities(thin_image, angles, 1, block_size, mask)


def compare_signature_vectors(vector1, vector2):
    """Implement similarity measure (Euclidean, or custom weighted)"""
    similarity = sum((v1 - v2) ** 2 for v1, v2 in zip(vector1, vector2)) ** 0.5
    return similarity

def calculate_distance(minutia1, minutia2):
    """
    Calculate Euclidean distance between two minutiae positions.
    """
    return np.sqrt((minutia1[0] - minutia2[0]) ** 2 + (minutia1[1] - minutia2[1]) ** 2)

def calculate_direction_difference(direction1, direction2):
    """
    Calculate the difference between two minutiae directions. Normalize it to [-180, 180] degrees.
    """
    diff = direction1 - direction2
    if diff > 180:
        diff -= 360
    elif diff < -180:
        diff += 360
    return abs(diff)


def minutiae_match(incoming_minutiae, stored_minutiae, position_threshold=5, direction_threshold=15, match_threshold=0.6):
    """
    Function to match incoming minutiae with stored minutiae data.
    
    :param incoming_minutiae: List of minutiae from incoming fingerprint
    :param stored_minutiae: List of minutiae from stored fingerprint data (e.g., from database)
    :param position_threshold: Maximum allowed position distance to consider a match (in pixels)
    :param direction_threshold: Maximum allowed direction difference to consider a match (in degrees)
    :param match_threshold: Minimum percentage of minutiae that should match to consider it a successful match
    :return: True if match is found, False otherwise
    """
    matched_count = 0
    for incoming in incoming_minutiae:
        incoming_position = incoming['position']
        incoming_direction = incoming['direction']
        
        for stored in stored_minutiae:
            stored_position = stored['position']
            stored_direction = stored['direction']
            
            # Check position match
            position_distance = calculate_distance(incoming_position, stored_position)
            direction_diff = calculate_direction_difference(incoming_direction, stored_direction)
            
            if position_distance <= position_threshold and direction_diff <= direction_threshold:
                matched_count += 1
                break  # Once a match is found, no need to check further for this minutia
    
    # Calculate match percentage
    match_percentage = matched_count / len(incoming_minutiae)
    print(f"Match Percentage: {match_percentage * 100}%")
    
    # Return if the match percentage exceeds the threshold
    return match_percentage >= match_threshold

@app.route('/compare', methods=['POST'])
def compare():
    try:
        # Get the incoming data from the request body
        data = request.get_json()
        pin = data['PIN']
        biometrics_capture = data['biometrics_capture']
        

        # Get the user's fingerprint data from the database
        fingerprints_data = get_fingerprints_from_database(pin);

        fingerprint1 = fingerprints_data[2]
        fingerprint2 = fingerprints_data[3]
        fingerprint3 = fingerprints_data[4]

        base64_strings = [fingerprint1, fingerprint2, fingerprint3]

        income_min = fingerprint_pipline(biometrics_capture)
        db_min = []
        for i, base64_string in enumerate(base64_strings):

            db_min_det = fingerprint_pipline(base64_string)
            print(db_min_det[0])
            # db_min.append(db_min_det)


        # is_match = minutiae_match(income_min, db_min)
        # print(f"Is match: {is_match}")
        print(income_min)
        # match_score = match_minutiae(income_min, db_min, threshold=0.75)
        # print(match_score[0])
        return jsonify("Done")

    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5012)
