#!/usr/bin/env python3
"""
Build script for LogCollector with targeted fix for pathlib issues.
"""
import os
import sys
import subprocess
import shutil
import platform
import tempfile

def run_command(cmd, check=True, shell=False):
    """Run a command and print output."""
    print(f"Running: {' '.join(cmd) if not shell else cmd}")
    result = subprocess.run(cmd, check=check, shell=shell, 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                          text=True)
    if result.returncode != 0 and check:
        print(f"Command failed with error:\n{result.stderr}")
        sys.exit(1)
    return result

def main():
    """Main function."""
    print("=== LogCollector Build Script (Pathlib Fix) ===\n")
    
    # Set up work directory
    work_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(work_dir)
    
    # Create a basic app_context.py if it doesn't exist
    app_context_path = os.path.join(work_dir, "log_collector", "app_context.py")
    if not os.path.exists(app_context_path):
        print("Creating app_context.py module...")
        with open(app_context_path, "w") as f:
            f.write("""
import os
import sys

class AppContext:
    def __init__(self, is_frozen=None):
        self.is_frozen = getattr(sys, 'frozen', False) if is_frozen is None else is_frozen
        self.base_dir = self._determine_base_dir()
        self.data_dir = os.path.join(self.base_dir, "data")
        self.log_dir = os.path.join(self.base_dir, "logs")
        self.sources_file = os.path.join(self.data_dir, "sources.json")
        self.pid_file = os.path.join(self.data_dir, "service.pid")
        self.log_file = os.path.join(self.log_dir, "service.log")
        self.auth_file = os.path.join(self.data_dir, "auth.json")
        self.policy_file = os.path.join(self.data_dir, "policy.json")
        self.filter_file = os.path.join(self.data_dir, "filters.json")
        self.service_state_file = os.path.join(self.data_dir, "service_state.json")
        
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
    
    def _determine_base_dir(self):
        if self.is_frozen:
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
""")
    
    # Create a simple config.py patch
    config_patch = os.path.join(work_dir, "log_collector", "config_patch.py")
    with open(config_patch, "w") as f:
        f.write("""
# Config patch for PyInstaller compatibility
import os
import sys
import json
import logging

# Import AppContext (avoiding pathlib imports)
from log_collector.app_context import AppContext

# Create application context
app_context = AppContext()

# Application directories
BASE_DIR = app_context.base_dir
DATA_DIR = app_context.data_dir
LOG_DIR = app_context.log_dir

# Configuration files
SOURCES_FILE = app_context.sources_file

# Default settings (unchanged)
DEFAULT_UDP_PROTOCOL = "UDP"
DEFAULT_HEC_BATCH_SIZE = 500
DEFAULT_FOLDER_BATCH_SIZE = 5000
DEFAULT_HEALTH_CHECK_INTERVAL = 60
DEFAULT_QUEUE_LIMIT = 10000
DEFAULT_COMPRESSION_ENABLED = True
DEFAULT_COMPRESSION_LEVEL = 9

# Configure logging
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "log_collector.log"),
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
    if not os.path.exists(SOURCES_FILE):
        return {}
    
    try:
        with open(SOURCES_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error loading sources file: {e}")
        return {}

def save_sources(sources):
    try:
        with open(SOURCES_FILE, "w") as f:
            json.dump(sources, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving sources file: {e}")
        return False

# Provide access to the app context throughout the application
def get_app_context():
    return app_context
""")
    
    # Create a temporary directory to build from
    with tempfile.TemporaryDirectory() as temp_dir:
        # Copy the log_collector package
        log_collector_dir = os.path.join(temp_dir, "log_collector")
        shutil.copytree(
            os.path.join(work_dir, "log_collector"),
            log_collector_dir
        )
        
        # Replace config.py with our patched version
        shutil.copy2(config_patch, os.path.join(log_collector_dir, "config.py"))
        
        # Create PyInstaller spec file
        spec_path = os.path.join(temp_dir, "logcollector.spec")
        with open(spec_path, "w") as f:
            f.write("""# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['log_collector/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'prompt_toolkit.styles.pygments',
        'prompt_toolkit.styles.style_elements',
        'psutil',
        'requests',
        'colorama',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='LogCollector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
""")
        
        # Change to the temp directory for building
        os.chdir(temp_dir)
        
        # Build the executable
        print("Building LogCollector executable...")
        result = run_command(["pyinstaller", "--clean", "logcollector.spec"], check=False)
        
        if result.returncode != 0:
            print(f"Build failed with error:\n{result.stderr}")
            print("\nTrying alternative build method...")
            
            # Try alternative build method directly with PyInstaller
            result = run_command([
                "pyinstaller",
                "--clean",
                "--onefile",
                "--name", "LogCollector",
                "log_collector/main.py"
            ], check=False)
            
            if result.returncode != 0:
                print(f"Alternative build also failed:\n{result.stderr}")
                sys.exit(1)
        
        # Create distribution directory
        dist_dir = os.path.join(work_dir, "dist", "LogCollector")
        if os.path.exists(dist_dir):
            shutil.rmtree(dist_dir)
        os.makedirs(dist_dir, exist_ok=True)
        
        # Copy executable
        print("Creating distribution package...")
        exe_name = "LogCollector.exe" if platform.system() == "Windows" else "LogCollector"
        exe_path = os.path.join(temp_dir, "dist", exe_name)
        if os.path.exists(exe_path):
            shutil.copy2(exe_path, dist_dir)
        else:
            print(f"Error: Executable {exe_path} not found!")
            sys.exit(1)
        
        # Create data directories
        os.makedirs(os.path.join(dist_dir, "data"), exist_ok=True)
        os.makedirs(os.path.join(dist_dir, "logs"), exist_ok=True)
        
        # Create helper scripts
        if platform.system() == "Windows":
            # Windows batch files
            with open(os.path.join(dist_dir, "start_service.bat"), "w") as f:
                f.write("""@echo off
echo Starting LogCollector service...
LogCollector.exe --service start
echo.
echo Service startup initiated. Check logs for details.
pause
""")
            with open(os.path.join(dist_dir, "stop_service.bat"), "w") as f:
                f.write("""@echo off
echo Stopping LogCollector service...
LogCollector.exe --service stop
echo.
echo Service stop command sent. Check logs for details.
pause
""")
        else:
            # Linux shell scripts
            with open(os.path.join(dist_dir, "start_service.sh"), "w") as f:
                f.write("""#!/bin/bash
echo "Starting LogCollector service..."
./LogCollector --service start
echo ""
echo "Service startup initiated. Check logs for details."
read -p "Press Enter to continue..."
""")
            with open(os.path.join(dist_dir, "stop_service.sh"), "w") as f:
                f.write("""#!/bin/bash
echo "Stopping LogCollector service..."
./LogCollector --service stop
echo ""
echo "Service stop command sent. Check logs for details."
read -p "Press Enter to continue..."
""")
            
            # Make scripts executable
            for script in ["start_service.sh", "stop_service.sh"]:
                os.chmod(os.path.join(dist_dir, script), 0o755)
        
        # Create README file
        with open(os.path.join(dist_dir, "README.txt"), "w") as f:
            f.write("""LogCollector Standalone Application
================================

This is a standalone version of the LogCollector application.

Getting Started:
1. Run LogCollector executable to start the application
2. All configuration will be stored in the 'data' directory
3. Logs will be written to the 'logs' directory

Service Management:
""")
            if platform.system() == "Windows":
                f.write("""- Use start_service.bat to start the service
- Use stop_service.bat to stop the service
""")
            else:
                f.write("""- Use ./start_service.sh to start the service
- Use ./stop_service.sh to stop the service
""")
    
    print("\nBuild completed successfully!")
    print(f"Executable and helper files are in: {dist_dir}")

if __name__ == "__main__":
    main()
