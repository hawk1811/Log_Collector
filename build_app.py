#!/usr/bin/env python3
"""
Build a standalone executable for Log Collector with fix for pathlib issue.
"""
import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path

def run_command(cmd, check=True, shell=False):
    """Run a command and return its output."""
    print(f"Running: {' '.join(cmd) if not shell else cmd}")
    result = subprocess.run(
        cmd, 
        check=check, 
        capture_output=True, 
        text=True, 
        shell=shell
    )
    if result.returncode != 0 and check:
        print(f"Command failed with error:\n{result.stderr}")
        sys.exit(1)
    return result

def main():
    """Main function."""
    print("=== LogCollector Standalone Build Script (Fixed) ===\n")
    
    # Set up work directory
    work_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(work_dir)
    
    # Create a clean virtual environment for building
    print("Creating a clean virtual environment...")
    venv_dir = os.path.join(work_dir, ".build_venv")
    
    # Remove old venv if it exists
    if os.path.exists(venv_dir):
        print("Removing old virtual environment...")
        shutil.rmtree(venv_dir)
    
    # Create new venv
    run_command([sys.executable, "-m", "venv", venv_dir])
    
    # Determine paths
    if platform.system() == "Windows":
        python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
        pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe")
    else:
        python_exe = os.path.join(venv_dir, "bin", "python")
        pip_exe = os.path.join(venv_dir, "bin", "pip")
    
    # Upgrade pip
    run_command([python_exe, "-m", "pip", "install", "--upgrade", "pip"])
    
    # Install PyInstaller
    print("Installing PyInstaller...")
    run_command([pip_exe, "install", "pyinstaller"])
    
    # Install dependencies
    print("Installing dependencies...")
    if os.path.exists("requirements.txt"):
        run_command([pip_exe, "install", "-r", "requirements.txt"])
    
    # Make sure pathlib backport is not installed
    print("Ensuring pathlib backport is not installed...")
    run_command([pip_exe, "uninstall", "-y", "pathlib"], check=False)
    
    # Copy source files to a temporary directory
    temp_dir = os.path.join(work_dir, ".build_temp")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    
    # Copy the log_collector package
    shutil.copytree(
        os.path.join(work_dir, "log_collector"),
        os.path.join(temp_dir, "log_collector")
    )
    
    # Create app context module if it doesn't exist yet
    app_context_path = os.path.join(temp_dir, "log_collector", "app_context.py")
    if not os.path.exists(app_context_path):
        print("Creating app_context.py module...")
        with open(app_context_path, "w") as f:
            f.write("""\"\"\"
Application context module for Log Collector.
Provides consistent access to paths and resources regardless of deployment method.
\"\"\"
import os
import sys
import platform
from pathlib import Path

class AppContext:
    \"\"\"Manages application paths and environment regardless of deployment method.\"\"\"
    
    def __init__(self, is_frozen=None):
        # Auto-detect if running as frozen executable if not specified
        if is_frozen is None:
            self.is_frozen = getattr(sys, 'frozen', False)
        else:
            self.is_frozen = is_frozen
            
        # Initialize paths
        self.base_dir = self._determine_base_dir()
        self.data_dir = self._get_data_dir()
        self.log_dir = self._get_log_dir()
        self.sources_file = self._get_sources_file()
        self.pid_file = self._get_pid_file()
        self.log_file = self._get_log_file()
        self.auth_file = self._get_auth_file()
        self.policy_file = self._get_policy_file()
        self.filter_file = self._get_filter_file()
        self.service_state_file = self._get_service_state_file()
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _determine_base_dir(self):
        \"\"\"Determine the base directory regardless of deployment method.\"\"\"
        if self.is_frozen:
            # For frozen executables (PyInstaller)
            return os.path.dirname(sys.executable)
        else:
            # For module-based deployment
            return str(Path(__file__).resolve().parent.parent)
    
    def _get_data_dir(self):
        \"\"\"Get the data directory path.\"\"\"
        if self.is_frozen:
            # For frozen executables, use a subdirectory in the executable directory
            return os.path.join(self.base_dir, "data")
        else:
            # For module version, use the standard location
            return os.path.join(self.base_dir, "data")
    
    def _get_log_dir(self):
        \"\"\"Get the log directory path.\"\"\"
        if self.is_frozen:
            return os.path.join(self.base_dir, "logs")
        else:
            return os.path.join(self.base_dir, "logs")
    
    def _get_sources_file(self):
        \"\"\"Get the sources configuration file path.\"\"\"
        return os.path.join(self.data_dir, "sources.json")
    
    def _get_pid_file(self):
        \"\"\"Get the PID file path.\"\"\"
        return os.path.join(self.data_dir, "service.pid")
    
    def _get_log_file(self):
        \"\"\"Get the service log file path.\"\"\"
        return os.path.join(self.log_dir, "service.log")
    
    def _get_auth_file(self):
        \"\"\"Get the authentication file path.\"\"\"
        return os.path.join(self.data_dir, "auth.json")
    
    def _get_policy_file(self):
        \"\"\"Get the aggregation policy file path.\"\"\"
        return os.path.join(self.data_dir, "policy.json")
    
    def _get_filter_file(self):
        \"\"\"Get the filter configuration file path.\"\"\"
        return os.path.join(self.data_dir, "filters.json")
    
    def _get_service_state_file(self):
        \"\"\"Get the service state file path.\"\"\"
        return os.path.join(self.data_dir, "service_state.json")
    
    def _ensure_directories(self):
        \"\"\"Ensure all required directories exist.\"\"\"
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        
    def get_resource_path(self, relative_path):
        \"\"\"Get the absolute path to a resource file.\"\"\"
        if self.is_frozen:
            # Running as compiled executable
            if hasattr(sys, '_MEIPASS'):
                # PyInstaller creates a temp folder and stores path in _MEIPASS
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(sys.executable)
        else:
            # Running as a normal Python script/module
            base_path = self.base_dir
            
        return os.path.join(base_path, relative_path)
""")
    
    # Create a simple spec file
    spec_path = os.path.join(temp_dir, "logcollector.spec")
    print("Creating PyInstaller spec file...")
    with open(spec_path, "w") as f:
        f.write("""# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(SPECPATH))

# Define data files to include
data_files = []
if os.path.exists(os.path.join(current_dir, '..', 'data')):
    data_files.append(('data', 'data'))

a = Analysis(
    ['log_collector/main.py'],
    pathex=[current_dir],
    binaries=[],
    datas=data_files,
    hiddenimports=[
        'prompt_toolkit.styles.pygments',
        'prompt_toolkit.styles.style_elements',
        'psutil',
        'requests',
        'colorama',
        'log_collector.app_context',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pathlib'],
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
    icon='icon.ico' if os.path.exists(os.path.join(current_dir, '..', 'icon.ico')) else None,
)
""")
    
    # Create helper scripts
    is_windows = platform.system() == "Windows"
    print("Creating helper scripts...")
    
    # Windows batch files
    if is_windows:
        with open(os.path.join(temp_dir, "start_service.bat"), "w") as f:
            f.write("""@echo off
echo Starting LogCollector service...
LogCollector.exe --service start
echo.
echo Service startup initiated. Check logs for details.
pause
""")
        
        with open(os.path.join(temp_dir, "stop_service.bat"), "w") as f:
            f.write("""@echo off
echo Stopping LogCollector service...
LogCollector.exe --service stop
echo.
echo Service stop command sent. Check logs for details.
pause
""")
        
        with open(os.path.join(temp_dir, "service_status.bat"), "w") as f:
            f.write("""@echo off
echo Checking LogCollector service status...
LogCollector.exe --service status
echo.
pause
""")
    else:
        # Linux scripts
        with open(os.path.join(temp_dir, "start_service.sh"), "w") as f:
            f.write("""#!/bin/bash
echo "Starting LogCollector service..."
./LogCollector --service start
echo ""
echo "Service startup initiated. Check logs for details."
read -p "Press Enter to continue..."
""")
        
        with open(os.path.join(temp_dir, "stop_service.sh"), "w") as f:
            f.write("""#!/bin/bash
echo "Stopping LogCollector service..."
./LogCollector --service stop
echo ""
echo "Service stop command sent. Check logs for details."
read -p "Press Enter to continue..."
""")
        
        with open(os.path.join(temp_dir, "service_status.sh"), "w") as f:
            f.write("""#!/bin/bash
echo "Checking LogCollector service status..."
./LogCollector --service status
echo ""
read -p "Press Enter to continue..."
""")
        
        # Make scripts executable
        for script in ["start_service.sh", "stop_service.sh", "service_status.sh"]:
            os.chmod(os.path.join(temp_dir, script), 0o755)
    
    # Create a README file
    with open(os.path.join(temp_dir, "README.txt"), "w") as f:
        f.write("""LogCollector Standalone Application
================================

This is a standalone version of the LogCollector application.

Getting Started:
1. Run LogCollector executable to start the application
""")
        if is_windows:
            f.write("""2. Use start_service.bat to start the service
3. Use stop_service.bat to stop the service
4. Use service_status.bat to check service status
""")
        else:
            f.write("""2. Use ./start_service.sh to start the service
3. Use ./stop_service.sh to stop the service
4. Use ./service_status.sh to check service status
""")
        f.write("""
Data and logs are stored in the data/ and logs/ directories.
""")
    
    # Change to the temp directory to build the executable
    os.chdir(temp_dir)
    
    # Build the executable
    print("Building the executable...")
    run_command([python_exe, "-m", "PyInstaller", "logcollector.spec"])
    
    # Create distribution directory
    dist_dir = os.path.join(work_dir, "dist", "LogCollector")
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.makedirs(dist_dir, exist_ok=True)
    
    # Copy executable
    print("Copying files to distribution directory...")
    exe_name = "LogCollector.exe" if is_windows else "LogCollector"
    exe_path = os.path.join(temp_dir, "dist", exe_name)
    if not os.path.exists(exe_path):
        print(f"Error: Executable {exe_path} not found!")
        sys.exit(1)
    
    shutil.copy2(exe_path, dist_dir)
    
    # Copy helper scripts
    if is_windows:
        for script in ["start_service.bat", "stop_service.bat", "service_status.bat", "README.txt"]:
            shutil.copy2(os.path.join(temp_dir, script), dist_dir)
    else:
        for script in ["start_service.sh", "stop_service.sh", "service_status.sh", "README.txt"]:
            script_path = os.path.join(dist_dir, script)
            shutil.copy2(os.path.join(temp_dir, script), script_path)
            if script.endswith(".sh"):
                os.chmod(script_path, 0o755)
    
    # Create empty directories
    print("Creating empty data directories...")
    os.makedirs(os.path.join(dist_dir, "data"), exist_ok=True)
    os.makedirs(os.path.join(dist_dir, "logs"), exist_ok=True)
    
    # Create ZIP file
    print("Creating distribution archive...")
    os.chdir(work_dir)
    archive_name = f"LogCollector-{platform.system().lower()}"
    shutil.make_archive(archive_name, "zip", os.path.join(work_dir, "dist"), "LogCollector")
    
    print(f"\nBuild completed successfully!")
    print(f"Distribution archive: {archive_name}.zip")
    print(f"Distribution directory: {dist_dir}")

if __name__ == "__main__":
    main()
