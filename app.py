from flask import Flask, request, jsonify
import base64
import mysql.connector
import numpy as np
import fingerprint_feature_extractor
import fingerprint_enhancer
from scipy.spatial.distance import cdist
import cv2

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


def get_user_from_database(pin):
    # cursor = db.cursor()
    cursor = db.cursor(dictionary=True)
    query = 'SELECT * FROM users WHERE pin = %s'
    cursor.execute(query, (pin,))
    results = cursor.fetchall()

    if results:
        fingerprints = {
            'id': results[0]['id'],
            'name': results[0]['name'],
            'email': results[0]['email'],
            'image': results[0]['image']
        }
        return fingerprints
    else:
        raise Exception("User not found")

# //////////////////////new
def decode_base64_image(base64_str):
    # Strip the "data:image/png;base64," prefix
    if base64_str.startswith("data:image/png;base64,"):
        base64_str = base64_str.split(",")[1]  # Get the Base64 encoded part
    
    img_data = base64.b64decode(base64_str)
    img_array = np.frombuffer(img_data, dtype=np.uint8)
    return cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)


def print_minutiae_features(features):
    for feature in features:
        print(f"locX: {feature.locX}, locY: {feature.locY}, Orientation: {feature.Orientation}, Type: {feature.Type}")

def from_db_minutiae(data):
    features_list = []
    for i, base64_string in enumerate(data):
        base64_data = base64_string.split(",")[1]
        image_data = base64.b64decode(base64_data)
        np_array = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
        img_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # img_gray = cv2.GaussianBlur(img_gray, (5, 5), 0)
        # img_gray = cv2.equalizeHist(img_gray)
        img_enhanced = fingerprint_enhancer.enhance_fingerprint(img_gray)
        if img_enhanced.dtype == bool:
                img_enhanced = np.uint8(img_enhanced * 255)
                # Normalize pixel values to 0-255
                img_enhanced = cv2.normalize(img_enhanced, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
                FeaturesTerminations, FeaturesBifurcations = fingerprint_feature_extractor.extract_minutiae_features(img_enhanced, spuriousMinutiaeThresh=10, invertImage=False, showResult=False, saveResult=False)
                features_list.append({
                    'terminations': FeaturesTerminations,
                    'bifurcations': FeaturesBifurcations
                })
    return features_list
    
def incoming_minutiae(data):
    features_list = []
    base64_data = data.split(",")[1]
    image_data = base64.b64decode(base64_data)
    np_array = np.frombuffer(image_data, np.uint8)
    image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
    img_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # img_gray = cv2.GaussianBlur(img_gray, (5, 5), 0)
    # img_gray = cv2.equalizeHist(img_gray)
    
    img_enhanced = fingerprint_enhancer.enhance_fingerprint(img_gray)
    if img_enhanced.dtype == bool:
                img_enhanced = np.uint8(img_enhanced * 255)
                # Normalize pixel values to 0-255
                img_enhanced = cv2.normalize(img_enhanced, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
                FeaturesTerminations, FeaturesBifurcations = fingerprint_feature_extractor.extract_minutiae_features(img_enhanced, spuriousMinutiaeThresh=10, invertImage=False, showResult=False, saveResult=False)
                features_list.append({
                    'terminations': FeaturesTerminations,
                    'bifurcations': FeaturesBifurcations
                })
    return features_list

def extract_feature_data(minutiae_feature):
    # Extract the data from the MinutiaeFeature object
    # Adjust according to the structure of your MinutiaeFeature class
    # print(minutiae_feature.Orientation)
    return {
        'type': minutiae_feature.Type,  # 'termination' or 'bifurcation'
        'x': minutiae_feature.locX,        # x-coordinate
        'y': minutiae_feature.locY,        # y-coordinate
        'angle': minutiae_feature.Orientation # angle of the minutiae
    }

def compare_minutiae(db_data, incoming_data):
    # Example comparison function: count common minutiae based on position and type
    matches = 0
    for db_feature in db_data:
        for incoming_feature in incoming_data:
            if (db_feature['x'] == incoming_feature['x'] and
                db_feature['y'] == incoming_feature['y'] and
                db_feature['type'] == incoming_feature['type']):
                matches += 1
    return matches

def match_minutiae(db_data, user_data):
    # Extract x and y coordinates from both datasets
    db_coords = np.array([(m['x'], m['y']) for m in db_data])
    user_coords = np.array([(m['x'], m['y']) for m in user_data])

    # Calculate pairwise distances between all points
    distances = cdist(db_coords, user_coords)
    # print(distances)
    # Set a threshold for matching (adjust as needed)
    threshold = 10  # Adjust this based on your specific requirements

    # Find the number of matches within the threshold
    num_matches = np.sum(distances < threshold)

    # Calculate a matching score (adjust as needed)
    match_score = num_matches / min(len(db_coords), len(user_coords))
    print(match_score)
    # Set a threshold for the match score (adjust as needed)
    match_threshold = 0.6  # Adjust this based on your desired accuracy 60%

    return match_score >= match_threshold

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


        extract_min_db = from_db_minutiae(base64_strings);

        db_minutiae_data = []
        for db_fingerprint in extract_min_db:
            for termination in db_fingerprint['terminations']:
                db_minutiae_data.append(extract_feature_data(termination))
            for bifurcation in db_fingerprint['bifurcations']:
                db_minutiae_data.append(extract_feature_data(bifurcation))

        incoming_bio_min = incoming_minutiae(biometrics_capture);
        incoming_minutiae_data = []
        for incoming_fingerprint in incoming_bio_min:
            for termination in incoming_fingerprint['terminations']:
                incoming_minutiae_data.append(extract_feature_data(termination))
            for bifurcation in incoming_fingerprint['bifurcations']:
                incoming_minutiae_data.append(extract_feature_data(bifurcation))
                
        # matches = compare_minutiae(db_minutiae_data, incoming_minutiae_data)
        if match_minutiae(db_minutiae_data, incoming_minutiae_data):
            print("Fingerprints match!")
        else:
            print("Fingerprints do not match.")
        return jsonify("Done")

    except Exception as e:
        return jsonify({'error': str(e)})
    


@app.route('/get_userinfo', methods=['POST'])
def get_userinfo():
    try:
        data = request.get_json()
        pin = data['PIN']
        fingerprints_data = get_user_from_database(pin);
        return jsonify(fingerprints_data)
    except Exception as e:
        return jsonify({'error': str(e)})
    

if __name__ == '__main__':
    app.run(debug=False, port=5012)
