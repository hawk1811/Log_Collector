#!/usr/bin/env python3
"""
Build a standalone executable for Log Collector.

This script:
1. Ensures all dependencies are installed
2. Builds the standalone executable using PyInstaller
3. Creates helper scripts for service management
4. Packages everything into a distributable directory
"""
import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

def run_command(cmd, check=True):
    """Run a command and return its output."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=check, capture_output=True, text=True)
    return result

def ensure_dependencies():
    """Ensure all required dependencies are installed."""
    print("Checking dependencies...")
    
    # Check PyInstaller
    try:
        import PyInstaller
        print("PyInstaller is installed.")
    except ImportError:
        print("Installing PyInstaller...")
        run_command([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Check other dependencies from requirements.txt
    if os.path.exists("requirements.txt"):
        print("Installing dependencies from requirements.txt...")
        run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def build_executable():
    """Build the standalone executable."""
    print("\nBuilding standalone executable...")
    
    # Determine the spec file
    spec_file = "logcollector.spec"
    if not os.path.exists(spec_file):
        print(f"Error: Spec file {spec_file} not found!")
        sys.exit(1)
    
    # Build with PyInstaller
    result = run_command(["pyinstaller", spec_file], check=False)
    
    if result.returncode != 0:
        print(f"Error building executable:\n{result.stderr}")
        sys.exit(1)
    
    print("Executable built successfully.")

def create_distribution():
    """Create the distribution package."""
    print("\nCreating distribution package...")
    
    # Determine platform
    is_windows = platform.system() == "Windows"
    
    # Create distribution directory
    dist_dir = Path("dist") / "LogCollector"
    os.makedirs(dist_dir, exist_ok=True)
    
    # Copy executable
    exe_name = "LogCollector.exe" if is_windows else "LogCollector"
    exe_path = Path("dist") / exe_name
    if not exe_path.exists():
        print(f"Error: Executable {exe_path} not found!")
        sys.exit(1)
    
    shutil.copy2(exe_path, dist_dir)
    
    # Copy helper scripts
    if is_windows:
        for script in ["start_service.bat", "stop_service.bat", "service_status.bat"]:
            if os.path.exists(script):
                shutil.copy2(script, dist_dir)
    else:
        for script in ["start_service.sh", "stop_service.sh", "service_status.sh"]:
            if os.path.exists(script):
                script_path = dist_dir / script
                shutil.copy2(script, script_path)
                os.chmod(script_path, 0o755)  # Make executable
    
    # Create empty data directory structure
    data_dir = dist_dir / "data"
    logs_dir = dist_dir / "logs"
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    
    # Create README
    with open(dist_dir / "README.txt", "w") as f:
        f.write("LogCollector Standalone Application\n")
        f.write("================================\n\n")
        f.write("This is a standalone version of the LogCollector application.\n\n")
        f.write("Getting Started:\n")
        f.write("1. Run LogCollector executable to start the application\n")
        if is_windows:
            f.write("2. Use start_service.bat to start the service\n")
            f.write("3. Use stop_service.bat to stop the service\n")
            f.write("4. Use service_status.bat to check service status\n")
        else:
            f.write("2. Use ./start_service.sh to start the service\n")
            f.write("3. Use ./stop_service.sh to stop the service\n")
            f.write("4. Use ./service_status.sh to check service status\n")
        f.write("\nData and logs are stored in the data/ and logs/ directories.\n")
    
    # Create ZIP archive
    archive_name = f"LogCollector-{platform.system().lower()}"
    shutil.make_archive(archive_name, "zip", "dist", "LogCollector")
    
    print(f"Distribution package created: {archive_name}.zip")

def main():
    """Main function."""
    print("=== LogCollector Standalone Build Script ===\n")
    
    # Ensure dependencies
    ensure_dependencies()
    
    # Build executable
    build_executable()
    
    # Create distribution package
    create_distribution()
    
    print("\nBuild completed successfully!")

if __name__ == "__main__":
    main()
