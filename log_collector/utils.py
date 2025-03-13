"""
Utility functions for Log Collector.
"""
import os
import sys
import time
import json
import socket
import hashlib
from datetime import datetime
from pathlib import Path

from log_collector.config import logger

def get_version():
    """Get application version."""
    return "1.0.0"

def is_port_available(port, host="0.0.0.0"):
    """Check if a port is available for binding.
    
    Args:
        port: Port number to check
        host: Host to bind to (default: 0.0.0.0)
        
    Returns:
        bool: True if port is available, False otherwise
    """
    try:
        # Try to create a socket and bind to it
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.close()
        return True
    except:
        return False

def format_timestamp(timestamp=None):
    """Format timestamp for filenames.
    
    Args:
        timestamp: Unix timestamp or None for current time
        
    Returns:
        str: Formatted timestamp (YYYY-MM-DD-HH-MM-SS)
    """
    if timestamp is None:
        timestamp = time.time()
    
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d-%H-%M-%S")

def get_file_hash(file_path):
    """Calculate SHA256 hash of a file.
    
    Args:
        file_path: Path to file
        
    Returns:
        str: SHA256 hash hexdigest or None if error
    """
    try:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                sha256.update(block)
        return sha256.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating file hash: {e}")
        return None

def safe_json_loads(json_str, default=None):
    """Safely parse JSON string.
    
    Args:
        json_str: JSON string to parse
        default: Default value to return if parsing fails
        
    Returns:
        Parsed JSON object or default value
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}

def human_readable_size(size_bytes):
    """Convert size in bytes to human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        str: Human-readable size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"

def create_dir_if_not_exists(directory):
    """Create directory if it doesn't exist.
    
    Args:
        directory: Directory path to create
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating directory {directory}: {e}")
        return False