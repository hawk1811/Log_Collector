#!/usr/bin/env python3
"""
Build a standalone executable for LogCollector

This script:
1. Runs embed_app.py to create the embedded application
2. Builds the executable with PyInstaller

Usage:
    python build_exe.py
"""
import os
import sys
import subprocess
import platform
import shutil

# Set working directory to script location
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Determine platform
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

# Create build directory
os.makedirs("build", exist_ok=True)
os.makedirs("dist", exist_ok=True)

# Step 1: Run the embed app script to create the embedded application
print("Step 1: Creating embedded application...")
result = subprocess.run([sys.executable, "embed_app.py"])
if result.returncode != 0:
    print("Error: Failed to create embedded application")
    sys.exit(1)

# Check if the embedded file was created
if not os.path.exists("logcollector_embedded.py"):
    print("Error: Embedded application file was not created")
    sys.exit(1)

# Step 2: Build the executable with PyInstaller
print("\nStep 2: Building executable with PyInstaller...")

# Determine output file name
output_name = "LogCollector.exe" if IS_WINDOWS else "LogCollector"

# Build the PyInstaller command
pyinstaller_cmd = [
    "pyinstaller",
    "--onefile",
    "--clean",
    "--name", output_name,
    "logcollector_embedded.py"
]

# Add icon if available
icon_path = None
if IS_WINDOWS and os.path.exists("icon.ico"):
    icon_path = "icon.ico"
elif IS_MACOS and os.path.exists("icon.icns"):
    icon_path = "icon.icns"

if icon_path:
    pyinstaller_cmd.extend(["--icon", icon_path])

# Run PyInstaller
print(f"Running: {' '.join(pyinstaller_cmd)}")
result = subprocess.run(pyinstaller_cmd)

if result.returncode != 0:
    print("Error: PyInstaller failed to build the executable")
    sys.exit(1)

# Check if executable was created
exe_path = os.path.join("dist", output_name)
if not os.path.exists(exe_path):
    print(f"Error: Executable was not created at {exe_path}")
    sys.exit(1)

# Step 3: Create helper scripts and README
print("\nStep 3: Creating helper scripts...")

# Windows batch files
if IS_WINDOWS:
    # Service installer
    with open(os.path.join("dist", "InstallService.bat"), "w") as f:
        f.write("@echo off\n")
        f.write("echo Installing LogCollector service...\n")
        f.write("cd %~dp0\n")
        f.write(f"{output_name} --service install\n")
        f.write("echo Service installation completed.\n")
        f.write("pause\n")
    
    # Service starter
    with open(os.path.join("dist", "StartService.bat"), "w") as f:
        f.write("@echo off\n")
        f.write("echo Starting LogCollector service...\n")
        f.write("cd %~dp0\n")
        f.write(f"{output_name} --service start\n")
        f.write("echo Service started.\n")
        f.write("pause\n")
    
    # Service stopper
    with open(os.path.join("dist", "StopService.bat"), "w") as f:
        f.write("@echo off\n")
        f.write("echo Stopping LogCollector service...\n")
        f.write("cd %~dp0\n")
        f.write(f"{output_name} --service stop\n")
        f.write("echo Service stopped.\n")
        f.write("pause\n")
    
    # Service status
    with open(os.path.join("dist", "ServiceStatus.bat"), "w") as f:
        f.write("@echo off\n")
        f.write("echo Checking LogCollector service status...\n")
        f.write("cd %~dp0\n")
        f.write(f"{output_name} --service status\n")
        f.write("pause\n")

# Linux/macOS shell scripts
if IS_LINUX or IS_MACOS:
    # Service starter
    with open(os.path.join("dist", "start_service.sh"), "w") as f:
        f.write("#!/bin/bash\n")
        f.write("echo Starting LogCollector service...\n")
        f.write("cd \"$(dirname \"$0\")\"\n")
        f.write(f"./LogCollector --service start\n")
    os.chmod(os.path.join("dist", "start_service.sh"), 0o755)
    
    # Service stopper
    with open(os.path.join("dist", "stop_service.sh"), "w") as f:
        f.write("#!/bin/bash\n")
        f.write("echo Stopping LogCollector service...\n")
        f.write("cd \"$(dirname \"$0\")\"\n")
        f.write(f"./LogCollector --service stop\n")
    os.chmod(os.path.join("dist", "stop_service.sh"), 0o755)
    
    # Service status
    with open(os.path.join("dist", "service_status.sh"), "w") as f:
        f.write("#!/bin/bash\n")
        f.write("echo Checking LogCollector service status...\n")
        f.write("cd \"$(dirname \"$0\")\"\n")
        f.write(f"./LogCollector --service status\n")
    os.chmod(os.path.join("dist", "service_status.sh"), 0o755)

# Create README
with open(os.path.join("dist", "README.txt"), "w") as f:
    f.write("LogCollector Standalone\n")
    f.write("======================\n\n")
    f.write("This is a standalone version of LogCollector that doesn't require Python installation.\n\n")
    f.write("Usage:\n")
    
    if IS_WINDOWS:
        f.write("1. Double-click LogCollector.exe to start the application with UI\n")
        f.write("2. Run InstallService.bat to install as a Windows service\n")
        f.write("3. Run StartService.bat to start the service\n")
        f.write("4. Run StopService.bat to stop the service\n")
        f.write("5. Run ServiceStatus.bat to check service status\n")
    else:
        f.write("1. Run ./LogCollector to start the application with UI\n")
        f.write("2. Run ./start_service.sh to start the background service\n")
        f.write("3. Run ./stop_service.sh to stop the service\n")
        f.write("4. Run ./service_status.sh to check service status\n")
    
    f.write("\nAll configuration files and logs are stored in ~/.logcollector/\n")

print("\nBuild completed successfully!")
print(f"Executable: dist/{output_name}")
print("Helper scripts and README are also in the dist directory.")
