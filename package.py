#!/usr/bin/env python3
"""
Package script for Log Collector.
Creates standalone executables for offline deployment.
"""
import os
import sys
import platform
import shutil
import subprocess
import argparse
from pathlib import Path

def main():
    """Main entry point for packaging script."""
    parser = argparse.ArgumentParser(description="Package Log Collector for offline deployment")
    parser.add_argument("--method", choices=["pyinstaller", "cx_freeze"], default="pyinstaller",
                        help="Packaging method to use (default: pyinstaller)")
    parser.add_argument("--clean", action="store_true", 
                        help="Clean previous builds before packaging")
    parser.add_argument("--zip", action="store_true",
                        help="Create a ZIP archive of the packaged application")
    
    args = parser.parse_args()
    
    # Get the root directory
    root_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    
    # Clean previous builds if requested
    if args.clean:
        clean_builds(root_dir)
    
    # Create directories for output
    dist_dir = root_dir / "dist"
    dist_dir.mkdir(exist_ok=True)
    
    # Detect platform
    system = platform.system()
    if system == "Windows":
        package_windows(root_dir, args.method)
    elif system == "Linux":
        package_linux(root_dir, args.method)
    else:
        print(f"Unsupported platform: {system}")
        return 1
    
    # Create ZIP archive if requested
    if args.zip:
        create_zip_archive(root_dir, system)
    
    print("Packaging complete!")
    return 0

def clean_builds(root_dir):
    """Clean previous build artifacts."""
    print("Cleaning previous builds...")
    
    build_dir = root_dir / "build"
    dist_dir = root_dir / "dist"
    
    # Remove directories if they exist
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    
    # Remove PyInstaller spec files
    for spec_file in root_dir.glob("*.spec"):
        os.remove(spec_file)
    
    print("Cleaning complete.")

def package_windows(root_dir, method):
    """Package the application for Windows."""
    print(f"Packaging for Windows using {method}...")
    
    if method == "pyinstaller":
        package_windows_pyinstaller(root_dir)
    elif method == "cx_freeze":
        package_windows_cx_freeze(root_dir)

def package_linux(root_dir, method):
    """Package the application for Linux."""
    print(f"Packaging for Linux using {method}...")
    
    if method == "pyinstaller":
        package_linux_pyinstaller(root_dir)
    elif method == "cx_freeze":
        package_linux_cx_freeze(root_dir)

def package_windows_pyinstaller(root_dir):
    """Package for Windows using PyInstaller."""
    print("Building with PyInstaller...")
    
    # Check for spec file
    spec_file = root_dir / "log_collector.spec"
    if spec_file.exists():
        # Run PyInstaller with spec file
        subprocess.run(["pyinstaller", str(spec_file)], check=True)
    else:
        # Run PyInstaller with command line options
        subprocess.run([
            "pyinstaller",
            "--name=Log_Collector",
            "--add-data=log_collector;log_collector",
            "--add-data=log_collector_service.py;.",
            "--hidden-import=win32timezone",
            "--hidden-import=prompt_toolkit",
            "--hidden-import=colorama",
            "--hidden-import=psutil",
            "--hidden-import=requests",
            "--onedir",
            "--console",
            "startup.py"
        ], check=True)
    
    # Set up additional files
    dist_dir = root_dir / "dist" / "Log_Collector"
    data_dir = dist_dir / "data"
    logs_dir = dist_dir / "logs"
    
    data_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    
    # Create README file
    with open(dist_dir / "README.txt", "w") as f:
        f.write("Log Collector Standalone Application\n")
        f.write("==================================\n\n")
        f.write("Run Log_Collector.exe to start the application.\n\n")
        f.write("To run as a service:\n")
        f.write("Log_Collector.exe --service start\n")
    
    print("Windows packaging with PyInstaller complete.")

def package_linux_pyinstaller(root_dir):
    """Package for Linux using PyInstaller."""
    print("Building with PyInstaller...")
    
    # Check for spec file
    spec_file = root_dir / "log_collector.spec"
    if spec_file.exists():
        # Run PyInstaller with spec file
        subprocess.run(["pyinstaller", str(spec_file)], check=True)
    else:
        # Run PyInstaller with command line options
        subprocess.run([
            "pyinstaller",
            "--name=log_collector",
            "--add-data=log_collector:log_collector",
            "--add-data=log_collector_service.py:.",
            "--hidden-import=prompt_toolkit",
            "--hidden-import=colorama",
            "--hidden-import=psutil",
            "--hidden-import=requests",
            "--onedir",
            "--console",
            "startup.py"
        ], check=True)
    
    # Set up additional files
    dist_dir = root_dir / "dist" / "log_collector"
    data_dir = dist_dir / "data"
    logs_dir = dist_dir / "logs"
    
    data_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    
    # Copy service script
    shutil.copy(root_dir / "log_collector_service.sh", dist_dir)
    os.chmod(dist_dir / "log_collector_service.sh", 0o755)
    
    # Create startup script
    with open(dist_dir / "start.sh", "w") as f:
        f.write("#!/bin/bash\n")
        f.write('SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n')
        f.write('cd "$SCRIPT_DIR"\n')
        f.write('./log_collector "$@"\n')
    
    os.chmod(dist_dir / "start.sh", 0o755)
    
    # Create README file
    with open(dist_dir / "README.txt", "w") as f:
        f.write("Log Collector Standalone Application\n")
        f.write("==================================\n\n")
        f.write("Run ./start.sh to start the application.\n\n")
        f.write("To run as a service:\n")
        f.write("./log_collector_service.sh start\n")
    
    print("Linux packaging with PyInstaller complete.")

def package_windows_cx_freeze(root_dir):
    """Package for Windows using cx_Freeze."""
    print("Building with cx_Freeze...")
    
    # Create setup.py for cx_Freeze
    setup_py = root_dir / "setup_freeze.py"
    with open(setup_py, "w") as f:
        f.write("""
import sys
from cx_Freeze import setup, Executable

# Dependencies
build_exe_options = {
    "packages": [
        "os", "sys", "logging", "time", "datetime", "json", "pathlib", 
        "threading", "queue", "signal", "subprocess", "re", "hashlib",
        "socket", "colorama", "prompt_toolkit", "psutil", "requests"
    ],
    "excludes": ["tkinter", "unittest", "email", "html", "http", "urllib", "xml"],
    "include_files": [
        ("log_collector", "log_collector"),
        ("log_collector_service.py", "log_collector_service.py"),
    ],
    "include_msvcr": True,
}

# Windows specific options
base = None
if sys.platform == "win32":
    base = None  # Use console for command-line window

setup(
    name="Log_Collector",
    version="1.0.0",
    description="High-performance log collection and processing system",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "startup.py",
            base=base,
            target_name="Log_Collector.exe",
        )
    ]
)
""")
    
    # Run setup.py
    subprocess.run([sys.executable, str(setup_py), "build"], check=True)
    
    # Copy build to dist
    build_dir = next((root_dir / "build").glob("exe.*"))
    dist_dir = root_dir / "dist" / "Log_Collector"
    
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    
    shutil.copytree(build_dir, dist_dir)
    
    # Create necessary directories
    data_dir = dist_dir / "data"
    logs_dir = dist_dir / "logs"
    
    data_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    
    # Create README file
    with open(dist_dir / "README.txt", "w") as f:
        f.write("Log Collector Standalone Application\n")
        f.write("==================================\n\n")
        f.write("Run Log_Collector.exe to start the application.\n\n")
        f.write("To run as a service:\n")
        f.write("Log_Collector.exe --service start\n")
    
    print("Windows packaging with cx_Freeze complete.")

def package_linux_cx_freeze(root_dir):
    """Package for Linux using cx_Freeze."""
    print("Building with cx_Freeze...")
    
    # Create setup.py for cx_Freeze
    setup_py = root_dir / "setup_freeze.py"
    with open(setup_py, "w") as f:
        f.write("""
import sys
from cx_Freeze import setup, Executable

# Dependencies
build_exe_options = {
    "packages": [
        "os", "sys", "logging", "time", "datetime", "json", "pathlib", 
        "threading", "queue", "signal", "subprocess", "re", "hashlib",
        "socket", "colorama", "prompt_toolkit", "psutil", "requests"
    ],
    "excludes": ["tkinter", "unittest", "email", "html", "http", "urllib", "xml"],
    "include_files": [
        ("log_collector", "log_collector"),
        ("log_collector_service.py", "log_collector_service.py"),
        ("log_collector_service.sh", "log_collector_service.sh"),
    ],
}

setup(
    name="log_collector",
    version="1.0.0",
    description="High-performance log collection and processing system",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "startup.py",
            target_name="log_collector",
        )
    ]
)
""")
    
    # Run setup.py
    subprocess.run([sys.executable, str(setup_py), "build"], check=True)
    
    # Copy build to dist
    build_dir = next((root_dir / "build").glob("exe.*"))
    dist_dir = root_dir / "dist" / "log_collector"
    
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    
    shutil.copytree(build_dir, dist_dir)
    
    # Create necessary directories
    data_dir = dist_dir / "data"
    logs_dir = dist_dir / "logs"
    
    data_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    
    # Make scripts executable
    os.chmod(dist_dir / "log_collector", 0o755)
    os.chmod(dist_dir / "log_collector_service.sh", 0o755)
    
    # Create startup script
    with open(dist_dir / "start.sh", "w") as f:
        f.write("#!/bin/bash\n")
        f.write('SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n')
        f.write('cd "$SCRIPT_DIR"\n')
        f.write('./log_collector "$@"\n')
    
    os.chmod(dist_dir / "start.sh", 0o755)
    
    # Create README file
    with open(dist_dir / "README.txt", "w") as f:
        f.write("Log Collector Standalone Application\n")
        f.write("==================================\n\n")
        f.write("Run ./start.sh to start the application.\n\n")
        f.write("To run as a service:\n")
        f.write("./log_collector_service.sh start\n")
    
    print("Linux packaging with cx_Freeze complete.")

def create_zip_archive(root_dir, system):
    """Create a ZIP archive of the packaged application."""
    print("Creating ZIP archive...")
    
    import zipfile
    
    # Determine source and target paths
    if system == "Windows":
        dist_dir = root_dir / "dist" / "Log_Collector"
        zip_file = root_dir / "dist" / "Log_Collector-Windows.zip"
    else:
        dist_dir = root_dir / "dist" / "log_collector"
        zip_file = root_dir / "dist" / "Log_Collector-Linux.zip"
    
    # Create ZIP archive
    with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(dist_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, dist_dir.parent)
                zipf.write(file_path, arcname)
    
    print(f"ZIP archive created: {zip_file}")

if __name__ == "__main__":
    sys.exit(main())