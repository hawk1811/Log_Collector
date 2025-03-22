#!/usr/bin/env python3
"""
LogCollector Single-File Builder

This script packages the entire LogCollector application into a single executable.
It works by:
1. Creating a zip file with all Python modules and resources
2. Embedding this zip as base64 in the loader script
3. Using PyInstaller to create a standalone executable
"""
import os
import sys
import shutil
import zipfile
import base64
import hashlib
import tempfile
import subprocess
import platform
import argparse
from pathlib import Path

# Parse arguments
parser = argparse.ArgumentParser(description='Build LogCollector as a single file')
parser.add_argument('--clean', action='store_true', help='Clean build files before starting')
parser.add_argument('--no-pyinstaller', action='store_true', help='Skip PyInstaller step (for testing)')
args = parser.parse_args()

# Constants
BUILD_DIR = "build"
DIST_DIR = "dist"
TEMP_DIR = os.path.join(BUILD_DIR, "temp")
OUTPUT_LOADER_PATH = os.path.join(TEMP_DIR, "standalone_loader.py")
PACKAGE_PATH = "log_collector"
LOADER_SCRIPT = "loader_template.py"  # The template loader script

# Determine platform
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MACOS = platform.system() == "Darwin"

# Clean build directory if requested
if args.clean and os.path.exists(BUILD_DIR):
    print(f"Cleaning build directory: {BUILD_DIR}")
    shutil.rmtree(BUILD_DIR)

# Create build directories
for directory in [BUILD_DIR, DIST_DIR, TEMP_DIR]:
    os.makedirs(directory, exist_ok=True)

# Step 1: Copy the loader template
with open(LOADER_SCRIPT, "r") as f:
    loader_template = f.read()

# Modify the template for standalone mode
loader_template = loader_template.replace("STANDALONE_MODE = False", "STANDALONE_MODE = True")

# Step 2: Create a zip file with all application files
print("Creating application zip file...")
app_zip_path = os.path.join(TEMP_DIR, "app.zip")

with zipfile.ZipFile(app_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
    # Add all Python files from the package
    for root, dirs, files in os.walk(PACKAGE_PATH):
        for file in files:
            if file.endswith(".py") or file.endswith(".json"):
                file_path = os.path.join(root, file)
                arcname = file_path  # Preserve directory structure
                zipf.write(file_path, arcname)
    
    # Add README and other important files
    for extra_file in ["README.md", "requirements.txt"]:
        if os.path.exists(extra_file):
            zipf.write(extra_file, extra_file)
    
    # Create empty data and logs directories
    zipf.writestr("data/.keep", "")
    zipf.writestr("logs/.keep", "")

# Step 3: Encode zip file as base64
print("Encoding application as base64...")
with open(app_zip_path, "rb") as f:
    app_data = f.read()

# Calculate SHA-256 checksum
checksum = hashlib.sha256(app_data).hexdigest()
encoded_data = base64.b64encode(app_data).decode("utf-8")

# Step 4: Update loader script with embedded data
print("Updating loader script with embedded application...")
loader_template = loader_template.replace('EMBEDDED_APPLICATION_DATA = ""', f'EMBEDDED_APPLICATION_DATA = """{encoded_data}"""')
loader_template = loader_template.replace('EMBEDDED_DATA_CHECKSUM = ""', f'EMBEDDED_DATA_CHECKSUM = "{checksum}"')

# Write the updated loader script
with open(OUTPUT_LOADER_PATH, "w") as f:
    f.write(loader_template)

print(f"Loader script written to: {OUTPUT_LOADER_PATH}")

# Step 5: Use PyInstaller to create a standalone executable
if not args.no_pyinstaller:
    print("Building standalone executable with PyInstaller...")
    
    # Determine executable name
    exe_name = "LogCollector.exe" if IS_WINDOWS else "LogCollector"
    
    # Build PyInstaller command
    pyinstaller_cmd = [
        "pyinstaller",
        "--onefile",
        "--name", exe_name,
        "--clean",
        "--noconfirm",
        OUTPUT_LOADER_PATH
    ]
    
    # Add icon if available
    icon_path = "resources/icon.ico" if IS_WINDOWS else "resources/icon.icns" if IS_MACOS else None
    if icon_path and os.path.exists(icon_path):
        pyinstaller_cmd.extend(["--icon", icon_path])
    
    # Run PyInstaller
    print(f"Running: {' '.join(pyinstaller_cmd)}")
    subprocess.run(pyinstaller_cmd)
    
    # Check if executable was created
    final_executable = os.path.join("dist", exe_name)
    if os.path.exists(final_executable):
        print(f"\nBuild successful! Standalone executable: {final_executable}")
        
        # For Windows, create service installer batch files
        if IS_WINDOWS:
            # Create service installer
            install_batch = os.path.join("dist", "InstallService.bat")
            with open(install_batch, "w") as f:
                f.write("@echo off\n")
                f.write("echo Installing Log Collector as a service...\n")
                f.write("cd %~dp0\n")
                f.write(f"{exe_name} --service install\n")
                f.write("echo.\n")
                f.write("echo Service installation completed\n")
                f.write("pause\n")
            
            # Create service uninstaller
            uninstall_batch = os.path.join("dist", "UninstallService.bat")
            with open(uninstall_batch, "w") as f:
                f.write("@echo off\n")
                f.write("echo Uninstalling Log Collector service...\n")
                f.write("cd %~dp0\n")
                f.write(f"{exe_name} --service stop\n")
                f.write("sc delete LogCollectorService\n")
                f.write("echo.\n")
                f.write("echo Service uninstallation completed\n")
                f.write("pause\n")
        
        # Create start and stop scripts for Linux/Mac
        if IS_LINUX or IS_MACOS:
            # Start script
            start_script = os.path.join("dist", "start_service.sh")
            with open(start_script, "w") as f:
                f.write("#!/bin/bash\n")
                f.write("echo Starting Log Collector service...\n")
                f.write("cd \"$(dirname \"$0\")\"\n")
                f.write("./LogCollector --service start\n")
            os.chmod(start_script, 0o755)
            
            # Stop script
            stop_script = os.path.join("dist", "stop_service.sh")
            with open(stop_script, "w") as f:
                f.write("#!/bin/bash\n")
                f.write("echo Stopping Log Collector service...\n")
                f.write("cd \"$(dirname \"$0\")\"\n")
                f.write("./LogCollector --service stop\n")
            os.chmod(stop_script, 0o755)
    else:
        print(f"Error: Executable not found: {final_executable}")

print("\nBuild process completed.")
