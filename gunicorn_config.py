import os

PORT = int(os.getenv('PORT', 10000))  # Same default as app.py
bind = f"0.0.0.0:{PORT}"
workers = 2 