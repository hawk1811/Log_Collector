"""
Configuration module for Log Collector application.
Handles global settings and constants.
"""
import os
import json
import logging
from pathlib import Path

# Application directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Source configuration file
SOURCES_FILE = DATA_DIR / "sources.json"

# Default settings
DEFAULT_UDP_PROTOCOL = "UDP"
DEFAULT_HEC_BATCH_SIZE = 500
DEFAULT_FOLDER_BATCH_SIZE = 5000
DEFAULT_HEALTH_CHECK_INTERVAL = 60  # seconds
DEFAULT_QUEUE_LIMIT = 10000  # logs per queue before spawning new thread

# Configure logging
logging.basicConfig(
    filename=LOG_DIR / "log_collector.log",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("log_collector")

# Stream handler for console output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

def load_sources():
    """Load source configurations from JSON file."""
    if not SOURCES_FILE.exists():
        return {}
    
    try:
        with open(SOURCES_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error loading sources file: {e}")
        return {}

def save_sources(sources):
    """Save source configurations to JSON file."""
    try:
        with open(SOURCES_FILE, "w") as f:
            json.dump(sources, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving sources file: {e}")
        return False