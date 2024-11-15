from flask import Flask, request, jsonify, g
from flask_cors import CORS
import base64
import mysql.connector
import numpy as np
from scipy.spatial.distance import cdist
import cv2
import matching_fingerprint
import asyncio
app = Flask(__name__)
# CORS(app, supports_credentials=False, max_age=86400)  # 86400 seconds = 1 day
# CORS(app, resources={r"/compare": {"origins": "*", "methods": ["POST"]}})
# CORS(app, resources={r"/get_userinfo": {"origins": "*", "methods": ["POST"]}})
CORS(app, origins=["https://biometric.iteklabs.tech"])
app.config['CORS_HEADERS'] = 'application/json'

# Set up MySQL connection
# db = mysql.connector.connect(
#     host="172.105.116.65",
#     user="philstud_ml",
#     password="Rk88j;OcQ8f3",
#     database="philstud_biomentrics",
#     ssl_disabled=True  # Disable SSL if not required
# )

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

def get_locations():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    query = 'SELECT id, name address FROM areas'
    cursor.execute(query)
    results = cursor.fetchall()
    if results:
        data = results
    return data
@app.route('/compare', methods=['POST', 'OPTIONS'])
async def compare():

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
            match_scores_all = []
            for a in base64_strings:
                # data2 = incoming_minutiae(a)
                match_score = await matching_fingerprint.fingerprints_matching(biometrics_capture, a)
                match_scores_all.append(match_score)
                print((match_score*100))
            total_score = sum(match_scores_all) * 100
            average_score = total_score / len(match_scores_all)

            return jsonify({'total_score_percent': total_score, 'average_percent': average_score }), 200
    

        except Exception as e:
            return jsonify({'error': str(e)}), 500
    


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
    


@app.route('/get_all_companies', methods=['GET'])
def get_all_companies():
    try:
        # data = request.get_json()
        # pin = data['PIN']
        all_location = get_locations();
        return jsonify(all_location)
    except Exception as e:
        return jsonify({'error': str(e)})
    

if __name__ == '__main__':
    app.run(debug=False, port=5012)
