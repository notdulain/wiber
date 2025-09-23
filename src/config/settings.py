import os
from pathlib import Path

# Project base directory (repo root)
BASE_DIR = Path(__file__).resolve().parents[2]

# Where to store message logs per topic
DATA_DIR = os.getenv("WIBER_DATA_DIR", str(BASE_DIR / "data"))

# Network settings
HOST = os.getenv("WIBER_HOST", "127.0.0.1")
PORT = int(os.getenv("WIBER_PORT", "8888"))