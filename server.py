import logging
from waitress import serve
from app3 import app

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

    # Run Waitress with logging enabled
    serve(
        app,
        host="0.0.0.0",
        port=5012,
        _quiet=False  # Enables request logging
    )
