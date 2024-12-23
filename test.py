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
import ctypes
from PIL import Image
import io
import platform
arch = platform.architecture()[0]
print(arch)
# import settings

if platform.system() == "Windows":
    dpfj_dll = ctypes.CDLL("dpfj.dll")  # Windows Lib
    dpfj_dll.dpfj_create_fmd_from_raw.restype = ctypes.c_int
    dpfj_dll.dpfj_create_fmd_from_raw.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte),  # Image data pointer
        ctypes.c_uint,                   # Image size
        ctypes.c_uint,                   # Image width
        ctypes.c_uint,                   # Image height
        ctypes.c_uint,                   # Image DPI
        ctypes.c_int,                    # Finger position (1 = right thumb)
        ctypes.c_uint,                   # CBEFF ID (usually 0)
        ctypes.c_int,                    # FMD type (e.g., 2 for ANSI 378-2004)
        ctypes.POINTER(ctypes.c_ubyte),  # FMD output buffer
        ctypes.POINTER(ctypes.c_uint)    # FMD size
    ]
else:
    dpfj_dll = ctypes.CDLL("libdpfj.so")  # Linux Lib
    dpfj_dll.dpfj_create_fmd_from_raw.restype = ctypes.c_int
    dpfj_dll.dpfj_create_fmd_from_raw.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte),  # Image data pointer
        ctypes.c_uint,                   # Image size
        ctypes.c_uint,                   # Image width
        ctypes.c_uint,                   # Image height
        ctypes.c_uint,                   # Image DPI
        ctypes.c_int,                    # Finger position (1 = right thumb)
        ctypes.c_uint,                   # CBEFF ID (usually 0)
        ctypes.c_int,                    # FMD type (e.g., 2 for ANSI 378-2004)
        ctypes.POINTER(ctypes.c_ubyte),  # FMD output buffer
        ctypes.POINTER(ctypes.c_uint)    # FMD size
    ]

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

# def base64_to_raw(base64_data):
#     # Decode Base64 string
#     base64_str = base64_data.split(",")[1]
#     image_data = base64.b64decode(base64_str)
    
#     # Convert PNG to grayscale raw data
#     image = Image.open(io.BytesIO(image_data)).convert("L")  # "L" for grayscale
#     raw_data = np.asarray(image, dtype=np.uint8).tobytes()
#     return raw_data, image.size  # Returns raw data and dimensions (width, height


def base64_to_raw(base64_data, resize_width=None, resize_height=None, dpi=500):
    """
    Convert a Base64-encoded PNG image to raw grayscale data with optional resizing and DPI adjustment.

    Args:
        base64_data (str): Base64-encoded PNG image.
        resize_width (int): Optional. Target width for resizing. If None, original width is used.
        resize_height (int): Optional. Target height for resizing. If None, original height is used.
        dpi (int): Optional. Target DPI for the processed image. Default is 500.

    Returns:
        tuple: (raw_data, (width, height)) where raw_data is the grayscale byte array
               and (width, height) are the dimensions of the processed image.
    """
    base64_str = base64_data.split(",")[1]
    image_data = base64.b64decode(base64_str)
    
    # Open the image and convert it to grayscale
    image = Image.open(io.BytesIO(image_data)).convert("L")
    
    # Resize the image if dimensions are provided
    if resize_width and resize_height:
        image = image.resize((resize_width, resize_height), Image.LANCZOS)

    # Save the image with adjusted DPI
    raw_array = np.asarray(image, dtype=np.uint8)
    raw_data = raw_array.tobytes()
    return raw_data, image.size



def get_error_message(code):
        error_messages = {
            0: "API call succeeded.",
            96075786: "API call is not implemented.",
            96075787: "Reason for the failure is unknown or cannot be specified.",
            96075788: "No data is available.",
            96075789: "The memory allocated by the application is not big enough for the data which is expected.",
            96075796: "One or more parameters passed to the API call are invalid.",
            96075797: "Reader handle is not valid.",
            96075806: "The API call cannot be completed because another call is in progress.",
            96075807: "The reader is not working properly.",
            96075877: "FID is invalid.",
            96075878: "Image is too small.",
            96075977: "FMD is invalid.",
            96076077: "Enrollment operation is in progress.",
            96076078: "Enrollment operation has not begun.",
            96076079: "Not enough in the pool of FMDs to create enrollment FMD.",
            96076080: "Unable to create enrollment FMD with the collected set of FMDs."
        }

        # Default error message
        return error_messages.get(
            code, f"Unknown error, code: 0x{code:x}"
        )


DPFJ_E_MORE_DATA = 96075789
def extract_fmd_from_base64(base64_image):
    try:
        dpi = 500  # Use a standard DPI value
        raw_data, (width, height) = base64_to_raw(base64_image, 320, 360, dpi)

        # print(f"Raw data size: {len(raw_data)}, Image dimensions: {width}x{height}, DPI: {dpi}")

        # First, allocate memory for FMD with MAX_FMD_SIZE
        buffer_size = 10000  # Initial size for FMD
        fmd = (ctypes.c_ubyte * buffer_size)()
        fmd_size = ctypes.c_uint(0)

        # Call dpfj_create_fmd_from_raw to process the image and extract features
        result = dpfj_dll.dpfj_create_fmd_from_raw(
            ctypes.cast(raw_data, ctypes.POINTER(ctypes.c_ubyte)),
            len(raw_data),
            width,
            height,
            dpi,
            1,  # DPFJ_POSITION_RTHUMB (right thumb)
            0,  # CBEFF ID (typically 0)
            0x001B0001,  # FMD Type (custom type, e.g., 0x001B0001)
            fmd, ctypes.byref(fmd_size)
        )

        # print(f"Result: {result}, FMD size required: {fmd_size.value}, Raw data size: {len(raw_data)}")

        if result == DPFJ_E_MORE_DATA:
            # If memory is insufficient, allocate more memory based on the required size
            # print(f"Insufficient memory. Reallocating memory with size {fmd_size.value} bytes.")
            fmd = (ctypes.c_ubyte * fmd_size.value)()  # Reallocate buffer with the correct size

            # Try again with the reallocated memory
            result = dpfj_dll.dpfj_create_fmd_from_raw(
                ctypes.cast(raw_data, ctypes.POINTER(ctypes.c_ubyte)),
                len(raw_data),
                width,
                height,
                dpi,
                1,  # DPFJ_POSITION_RTHUMB
                0,  # CBEFF ID
                0x001B0001,  # FMD Type (custom type)
                fmd, ctypes.byref(fmd_size)
            )

        # Handle the result of the operation
        if result != 0:
            # print(get_error_message(result))
            raise Exception(f"Error extracting FMD (Code: {result})")

        # Return the FMD as bytes
        return bytes(fmd[:fmd_size.value])

    except Exception as e:
        raise Exception(f"Error in FMD extraction: {str(e)}")

def compare_templates(template1, template2):
    """
    Compare two fingerprint templates using the Digital Persona SDK.

    Args:
        template1 (str): Base64-encoded PNG of the first fingerprint.
        template2 (str): Base64-encoded PNG of the second fingerprint.

    Returns:
        bool: True if the fingerprints match, False otherwise.
    """
    # Load the Digital Persona SDK library
    dpfj_dll = ctypes.CDLL("dpfj.dll")  # Windows Library
    # Ensure dpfj_compare is properly defined
    dpfj_compare = dpfj_dll.dpfj_compare
    dpfj_compare.restype = ctypes.c_int
    dpfj_compare.argtypes = [
        ctypes.c_int,                   # fmd1_type
        ctypes.POINTER(ctypes.c_ubyte), # fmd1
        ctypes.c_uint,                  # fmd1_size
        ctypes.c_uint,                  # fmd1_view_idx
        ctypes.c_int,                   # fmd2_type
        ctypes.POINTER(ctypes.c_ubyte), # fmd2
        ctypes.c_uint,                  # fmd2_size
        ctypes.c_uint,                  # fmd2_view_idx
        ctypes.POINTER(ctypes.c_uint),  # score
    ]

    # Extract FMDs from Base64 templates
    fmd1 = extract_fmd_from_base64(template1)
    fmd2 = extract_fmd_from_base64(template2)

    # Define FMD properties
    fmd_type = 0x001B0001  # ANSI 378-2004
    fmd1_size = len(fmd1)
    fmd2_size = len(fmd2)
    score = ctypes.c_uint(0)

    # Call the dpfj_compare function
    result = dpfj_compare(
        fmd_type,
        ctypes.cast(fmd1, ctypes.POINTER(ctypes.c_ubyte)),
        fmd1_size,
        0,  # View index for FMD1
        fmd_type,
        ctypes.cast(fmd2, ctypes.POINTER(ctypes.c_ubyte)),
        fmd2_size,
        0,  # View index for FMD2
        ctypes.byref(score),
    )

    # print(get_error_message(result))

    # Check the result and the score
    accepted_score = 21474  # Threshold based on PROBABILITY_ONE / 100000
    print(f"Result: {result}, Score: {score.value}")

    if result != 0:
        raise Exception(f"Error in comparison: {result}")
    
    return score.value < accepted_score


def finger_print_verify(template, db_templates):
    # imc_temp = template.split(",")[1];

    # mc_temp_bytes = base64.b64decode(imc_temp) 
    for db_template in db_templates:
        is_valid = compare_templates(template, db_template)
        if is_valid:
            break

    return is_valid


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

            theresult = finger_print_verify(biometrics_capture, base64_strings)
            # print(theresult)
            if(theresult):
                return jsonify({'valid': theresult, 'message': "Fingerprint Match" }), 200
            else:
                return jsonify({'valid': theresult , 'message': "Fingerprint Not Match" }), 200
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
