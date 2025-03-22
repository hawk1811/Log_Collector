#!/usr/bin/env python3
"""
Embeds the LogCollector application into a single Python file.

This script will:
1. Package the entire application into a ZIP file
2. Base64 encode the ZIP file
3. Create a new Python file with the embedded data
4. The resulting file can be built with PyInstaller

Usage:
    python embed_app.py
"""

import os
import sys
import zipfile
import base64
import hashlib
import tempfile
import shutil
from pathlib import Path

# Define paths
PACKAGE_DIR = "log_collector"
OUTPUT_FILE = "logcollector_embedded.py"
TEMPLATE_FILE = "logcollector_template.py"

print(f"Packaging {PACKAGE_DIR} directory...")

# Create temporary directory
with tempfile.TemporaryDirectory() as temp_dir:
    zip_path = os.path.join(temp_dir, "logcollector.zip")
    
    # Create ZIP file with the application
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add all Python files from the package
        for root, dirs, files in os.walk(PACKAGE_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = file_path  # Keep the structure
                zipf.write(file_path, arcname)
        
        # Add README and requirements files if they exist
        for extra_file in ["README.md", "requirements.txt"]:
            if os.path.exists(extra_file):
                zipf.write(extra_file, extra_file)
    
    # Read the ZIP file and encode it as base64
    with open(zip_path, 'rb') as f:
        zip_data = f.read()
    
    encoded_data = base64.b64encode(zip_data).decode('utf-8')
    checksum = hashlib.sha256(zip_data).hexdigest()
    
    print(f"Application packaged and encoded. Size: {len(encoded_data):,} bytes")
    print(f"Checksum: {checksum}")
    
    # Read the template file
    if not os.path.exists(TEMPLATE_FILE):
        print(f"Error: Template file '{TEMPLATE_FILE}' not found!")
        sys.exit(1)
    
    with open(TEMPLATE_FILE, 'r') as f:
        template = f.read()
    
    # Replace placeholders with actual data
    output_content = template.replace('##EMBEDDED_DATA##', encoded_data)
    output_content = output_content.replace('##DATA_CHECKSUM##', checksum)
    
    # Write the output file
    with open(OUTPUT_FILE, 'w') as f:
        f.write(output_content)
    
    print(f"Created embedded application file: {OUTPUT_FILE}")
    print("This file can now be compiled with PyInstaller.")
