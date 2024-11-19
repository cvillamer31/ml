from flask import Flask, request, jsonify, g
import base64
import mysql.connector
import numpy as np
import fingerprint_feature_extractor
import fingerprint_enhancer
from scipy.spatial.distance import cdist
import cv2
from flask_cors import CORS
from scipy.spatial import KDTree
from requests import get

app = Flask(__name__)
ip = get('https://api.ipify.org').content.decode('utf8')
CORS(app, origins=["https://biometric.iteklabs.tech"])
app.config['CORS_HEADERS'] = 'application/json'

# Set up MySQL connection
db_config = {
    'host': "172.105.116.65",
    'user': "philstud_ml",
    'password': "Rk88j;OcQ8f3",
    'database': "philstud_biomentrics",
    'ssl_disabled': True  # Disable SSL if not required
}

def get_db_connection():
    if 'db' not in g:
        g.db = mysql.connector.connect(**db_config)
    else:
        try:
            g.db.ping(reconnect=True, attempts=3, delay=5)
        except mysql.connector.Error:
            g.db = mysql.connector.connect(**db_config)
    return g.db

# Function to fetch fingerprints from the database
def get_fingerprints_from_database(user_id):
    db = get_db_connection()
    cursor = db.cursor()
    query_fingerprint = 'SELECT id, user_id, img_1, img_2, img_3, img_4, img_5 FROM biometrics_data WHERE user_id = %s'
    cursor.execute(query_fingerprint, (user_id,))
    results = cursor.fetchall()
    # print(results)
    if results:
        fingerprints = results[0]
        if fingerprints[0] > 0:  # Checking if the user exists
            return fingerprints
        else:
            raise Exception("User not found")
    else:
        raise Exception("User not found")


def get_user_from_database(pin):
    # cursor = db.cursor()
    db = get_db_connection()
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

def get_locations(pin):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    query = 'SELECT id, name address FROM areas WHERE ip_address = %s'
    cursor.execute(query, (pin,))
    results = cursor.fetchall()
    if results:
        data = results
    return data

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


# ////////////////////////////////////// NEW


def align_minutiae(query, reference):
    """
    Aligns the query minutiae set to the reference set using translation and rotation.
    """
    # Assuming the first minutiae pair are used for alignment

    
    r = reference
    for idx, q in enumerate(query):
        translation = (r['x'] - q['x'], r['y'] - q['y'])
         # Average angles if they are lists
        if isinstance(q['angle'], list):
            q['angle'] = np.mean(q['angle'])  # Average the angles
        if isinstance(r['angle'], list):
            r['angle'] = np.mean(r['angle'])  # Average the angles

        angle_diff = r['angle'] - q['angle']
        # print(translation)
    # q = query[0]
    # r = reference[0]
    
    # # Calculate translation vector
    # translation = (r['x'] - q['x'], r['y'] - q['y'])
    
    # # Calculate rotation angle
    # angle_diff = r['angle'] - q['angle']
    
    # # Apply translation and rotation to all query minutiae
    aligned_query = []
    for m in query:
        # Translate
        x_trans = m['x'] + translation[0]
        y_trans = m['y'] + translation[1]


        
        
        # Rotate around reference minutiae
        x_rot = (x_trans * np.cos(angle_diff)) - (y_trans * np.sin(angle_diff))
        y_rot = (x_trans * np.sin(angle_diff)) + (y_trans * np.cos(angle_diff))
        # print(x_rot)
        aligned_query.append({
            'x': x_rot,
            'y': y_rot,
            'angle': m['angle'] + angle_diff,
            'type': m['type']
        })
    
    return aligned_query

def match_minutiae(query, reference, threshold=10, angle_tolerance=np.radians(10)):
    """
    Matches minutiae points between query and reference sets based on proximity and angle similarity.
    """
    # Convert minutiae to KDTree for fast spatial matching
    query_points = [(m['x'], m['y']) for m in query]
    reference = [reference]
    reference_points = [(m['x'], m['y']) for m in reference]
    reference_tree = KDTree(reference_points)
    # print(type(reference))
    # print(reference_tree)


   
    # print(reference_points)
    matches = []
    for i, q in enumerate(query):
        # Find the nearest neighbor within the threshold
        dist, idx = reference_tree.query((q['x'], q['y']), distance_upper_bound=threshold)
        if dist < threshold:
            # Check angle and type match
            ref = reference[idx]
            angle_diff = abs(q['angle'] - ref['angle']) % (2 * np.pi)
            if angle_diff > np.pi:  # Normalize to [0, π]
                angle_diff = 2 * np.pi - angle_diff
            if angle_diff < angle_tolerance and q['type'] == ref['type']:
                matches.append((i, idx))
    
    return matches


def match_fingerprints(query_minutiae, reference_minutiae):
    """
    Full pipeline for matching fingerprints using minutiae.
    """
    # Align query minutiae to reference
    aligned_query = align_minutiae(query_minutiae, reference_minutiae)
    
    # Match aligned minutiae
    matches = match_minutiae(aligned_query, reference_minutiae)
    
    # Calculate similarity score
    similarity_score = calculate_similarity(matches, aligned_query, reference_minutiae)
    
    return {
        'matches': matches,
        'similarity_score': similarity_score
    }


def calculate_similarity(matches, query, reference):
    """
    Calculates similarity score based on the number of matches and total minutiae.
    """
    return len(matches) / max(len(query), len(reference))


def match_fingerprints_multiple_references(query_minutiae, reference_minutiae_list):
    """
    Matches a query fingerprint against multiple reference fingerprints.
    
    Parameters:
    - query_minutiae: List of minutiae for the query fingerprint.
    - reference_minutiae_list: List of minutiae lists for each reference fingerprint.
    
    Returns:
    - A dictionary containing matches and similarity scores for all references, 
      and the best match.
    """
    results = []
    for idx, reference_minutiae in enumerate(reference_minutiae_list):
        # Align query minutiae to the current reference
        aligned_query = align_minutiae(query_minutiae, reference_minutiae)
       
    #     
        
    #     # Match aligned minutiae
        matches = match_minutiae(aligned_query, reference_minutiae)
        
    #     # Calculate similarity score
        similarity_score = calculate_similarity(matches, aligned_query, reference_minutiae)
        
    #     # Store results for this reference
        results.append({
            "reference_index": idx,
            "matches": matches,
            "similarity_score": similarity_score
        })
    
    # # Find the best match
    best_match = max(results, key=lambda r: r['similarity_score'])
    # print(best_match)
    # print(best_match)
    return {
        # "all_results": results,
        "best_match": best_match
    }


@app.route('/compare', methods=['POST', 'OPTIONS'])
def compare():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "OK"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response, 200
    if request.method == 'POST':
        try:
            # Get the incoming data from the request body
            data = request.get_json()
            user_id = data['user_id']
            biometrics_capture = data['biometrics_capture']
            

            # Get the user's fingerprint data from the database
            fingerprints_data = get_fingerprints_from_database(user_id);

            fingerprint1 = fingerprints_data[2]
            fingerprint2 = fingerprints_data[3]
            fingerprint3 = fingerprints_data[4]
            fingerprint4 = fingerprints_data[5]
            fingerprint5 = fingerprints_data[6]
            # print(fingerprint4)
            base64_strings = [fingerprint1, fingerprint2, fingerprint3, fingerprint4, fingerprint5]


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
            # print(incoming_bio_min)
            # matches = compare_minutiae(db_minutiae_data, incoming_minutiae_data)
            # if match_minutiae(db_minutiae_data, incoming_minutiae_data):
            #     print("Fingerprints match!")
            #     return jsonify({'message': 'Fingerprints match!', 'type': "true" }), 200
            # else:
            #     print("Fingerprints do not match.")
            # data1233 =
            result = match_fingerprints_multiple_references(incoming_minutiae_data, db_minutiae_data)

            print((result['best_match']['similarity_score'] * 100))
            return jsonify({'score': result['best_match']['similarity_score'] * 100 }), 200
        except Exception as e:
            return jsonify({'error': str(e)})
        


@app.route('/get_userinfo', methods=['POST', 'OPTIONS'])
def get_userinfo():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "OK"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response, 200
    if request.method == 'POST':
        try:
            data = request.get_json()
            pin = data['PIN']
            fingerprints_data = get_user_from_database(pin);
            return jsonify(fingerprints_data)
        except Exception as e:
            return jsonify({'error': str(e)})
        

@app.route('/get_all_companies', methods=['POST', 'OPTIONS'])
def get_all_companies():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "OK"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response, 200
    if request.method == 'POST':
        try:
            # print(ip)
            data = request.get_json()
            pin = data['ip_address']
            all_location = get_locations(pin);
            return jsonify(all_location)
        except Exception as e:
            return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5012)
