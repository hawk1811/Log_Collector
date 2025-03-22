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
    parser.add_argument("--onefile", action="store_true",
                        help="Create a single executable file instead of a directory")
    
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
        package_windows(root_dir, args.method, args.onefile)
    elif system == "Linux":
        package_linux(root_dir, args.method, args.onefile)
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

def package_windows(root_dir, method, onefile):
    """Package the application for Windows."""
    print(f"Packaging for Windows using {method}...")
    
    if method == "pyinstaller":
        package_windows_pyinstaller(root_dir, onefile)
    elif method == "cx_freeze":
        package_windows_cx_freeze(root_dir)

def package_linux(root_dir, method, onefile):
    """Package the application for Linux."""
    print(f"Packaging for Linux using {method}...")
    
    if method == "pyinstaller":
        package_linux_pyinstaller(root_dir, onefile)
    elif method == "cx_freeze":
        package_linux_cx_freeze(root_dir)

def package_windows_pyinstaller(root_dir, onefile):
    """Package for Windows using PyInstaller."""
    print("Building with PyInstaller...")
    
    # Build main application
    build_pyinstaller_app(root_dir, "startup.py", "Log_Collector", onefile)
    
    # Also build the service executable separately
    build_pyinstaller_service(root_dir, "log_collector_service.py", "log_collector_service", onefile)
    
    # Set up additional files
    dist_dir = root_dir / "dist"
    if onefile:
        service_exe = dist_dir / "log_collector_service.exe"
        app_exe = dist_dir / "Log_Collector.exe"
        data_dir = dist_dir / "data"
        logs_dir = dist_dir / "logs"
    else:
        # When building as a directory, PyInstaller creates a subdirectory
        service_exe = dist_dir / "log_collector_service" / "log_collector_service.exe"
        app_exe = dist_dir / "Log_Collector" / "Log_Collector.exe"
        
        # Make sure service executable is in the main app directory
        if service_exe.exists() and app_exe.exists():
            shutil.copy(service_exe, app_exe.parent)
            print(f"Copied service executable to main app directory")
            
        data_dir = dist_dir / "Log_Collector" / "data"
        logs_dir = dist_dir / "Log_Collector" / "logs"
    
    # Create necessary directories
    data_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    
    # Create README file
    with open(data_dir.parent / "README.txt", "w") as f:
        f.write("Log Collector Standalone Application\n")
        f.write("==================================\n\n")
        f.write("Run Log_Collector.exe to start the application.\n\n")
        f.write("To run as a service:\n")
        f.write("log_collector_service.exe start\n\n")
        f.write("To stop the service:\n")
        f.write("log_collector_service.exe stop\n\n")
        f.write("All data files are stored in the 'data' directory.\n")
    
    print("Windows packaging with PyInstaller complete.")

def package_linux_pyinstaller(root_dir, onefile):
    """Package for Linux using PyInstaller."""
    print("Building with PyInstaller...")
    
    # Build main application
    build_pyinstaller_app(root_dir, "startup.py", "log_collector", onefile)
    
    # Also build the service executable separately
    build_pyinstaller_service(root_dir, "log_collector_service.py", "log_collector_service", onefile)
    
    # Set up additional files
    dist_dir = root_dir / "dist"
    if onefile:
        service_exe = dist_dir / "log_collector_service"
        app_exe = dist_dir / "log_collector"
        data_dir = dist_dir / "data"
        logs_dir = dist_dir / "logs"
    else:
        # When building as a directory, PyInstaller creates a subdirectory
        service_exe = dist_dir / "log_collector_service" / "log_collector_service"
        app_exe = dist_dir / "log_collector" / "log_collector"
        
        # Make sure service executable is in the main app directory
        if service_exe.exists() and app_exe.exists():
            shutil.copy(service_exe, app_exe.parent)
            print(f"Copied service executable to main app directory")
            
        data_dir = dist_dir / "log_collector" / "data"
        logs_dir = dist_dir / "log_collector" / "logs"
    
    # Create necessary directories
    data_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    
    # Make executables executable
    if not onefile:
        os.chmod(dist_dir / "log_collector" / "log_collector", 0o755)
        os.chmod(dist_dir / "log_collector" / "log_collector_service", 0o755)
    else:
        os.chmod(dist_dir / "log_collector", 0o755)
        os.chmod(dist_dir / "log_collector_service", 0o755)
    
    # Create startup script
    start_script = data_dir.parent / "start.sh"
    with open(start_script, "w") as f:
        f.write("#!/bin/bash\n")
        f.write('SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n')
        f.write('cd "$SCRIPT_DIR"\n')
        f.write('./log_collector "$@"\n')
    
    os.chmod(start_script, 0o755)
    
    # Create README file
    with open(data_dir.parent / "README.txt", "w") as f:
        f.write("Log Collector Standalone Application\n")
        f.write("==================================\n\n")
        f.write("Run ./log_collector or ./start.sh to start the application.\n\n")
        f.write("To run as a service:\n")
        f.write("./log_collector_service start\n\n")
        f.write("To stop the service:\n")
        f.write("./log_collector_service stop\n\n")
        f.write("All data files are stored in the 'data' directory.\n")
    
    print("Linux packaging with PyInstaller complete.")

def build_pyinstaller_app(root_dir, script_name, output_name, onefile):
    """Build an application using PyInstaller.
    
    Args:
        root_dir: Root directory of the project
        script_name: Script to build
        output_name: Output name for the executable
        onefile: Whether to build a single file
    """
    # Check for spec file
    spec_file = root_dir / f"{output_name}.spec"
    
    # Base PyInstaller options
    pyinstaller_cmd = [
        "pyinstaller",
        "--name=" + output_name,
        "--add-data=log_collector;log_collector"
    ]
    
    # Add hidden imports
    pyinstaller_cmd.extend([
        "--hidden-import=win32timezone",
        "--hidden-import=prompt_toolkit",
        "--hidden-import=colorama",
        "--hidden-import=psutil",
        "--hidden-import=requests"
    ])
    
    # Set single file or directory mode
    if onefile:
        pyinstaller_cmd.append("--onefile")
    else:
        pyinstaller_cmd.append("--onedir")
    
    # Always use console mode for better debugging
    pyinstaller_cmd.append("--console")
    
    # Add the script to build
    pyinstaller_cmd.append(script_name)
    
    # Run PyInstaller
    if spec_file.exists():
        # Run PyInstaller with spec file
        subprocess.run(["pyinstaller", str(spec_file)], check=True)
    else:
        # Run PyInstaller with command line options
        subprocess.run(pyinstaller_cmd, check=True)

def build_pyinstaller_service(root_dir, script_name, output_name, onefile):
    """Build the service executable using PyInstaller.
    
    Args:
        root_dir: Root directory of the project
        script_name: Script to build
        output_name: Output name for the executable
        onefile: Whether to build a single file
    """
    # Base PyInstaller options
    pyinstaller_cmd = [
        "pyinstaller",
        "--name=" + output_name,
        "--add-data=log_collector;log_collector"
    ]
    
    # Add hidden imports
    pyinstaller_cmd.extend([
        "--hidden-import=win32timezone",
        "--hidden-import=prompt_toolkit",
        "--hidden-import=colorama",
        "--hidden-import=psutil",
        "--hidden-import=requests"
    ])
    
    # Set single file or directory mode
    if onefile:
        pyinstaller_cmd.append("--onefile")
    else:
        pyinstaller_cmd.append("--onedir")
    
    # Always use console mode for better debugging
    pyinstaller_cmd.append("--console")
    
    # Add the script to build
    pyinstaller_cmd.append(script_name)
    
    # Run PyInstaller
    subprocess.run(pyinstaller_cmd, check=True)

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
        ),
        Executable(
            "log_collector_service.py",
            base=base,
            target_name="log_collector_service.exe",
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
        f.write("log_collector_service.exe start\n\n")
        f.write("To stop the service:\n")
        f.write("log_collector_service.exe stop\n\n")
        f.write("All data files are stored in the 'data' directory.\n")
    
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
        ),
        Executable(
            "log_collector_service.py",
            target_name="log_collector_service",
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
    os.chmod(dist_dir / "log_collector_service", 0o755)
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
        f.write("Run ./log_collector or ./start.sh to start the application.\n\n")
        f.write("To run as a service:\n")
        f.write("./log_collector_service start\n\n")
        f.write("To stop the service:\n")
        f.write("./log_collector_service stop\n\n")
        f.write("All data files are stored in the 'data' directory.\n")
    
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
    
    # Check if we're dealing with onefile builds
    onefile_check = (root_dir / "dist" / "Log_Collector.exe").exists() or (root_dir / "dist" / "log_collector").exists()
    
    if onefile_check:
        # For onefile, zip everything in dist
        dist_dir = root_dir / "dist"
        if system == "Windows":
            zip_file = root_dir / "dist" / "Log_Collector-Windows-onefile.zip"
        else:
            zip_file = root_dir / "dist" / "Log_Collector-Linux-onefile.zip"
    
    # Create ZIP archive
    with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(dist_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, dist_dir.parent if not onefile_check else dist_dir)
                zipf.write(file_path, arcname)
    
    print(f"ZIP archive created: {zip_file}")

if __name__ == "__main__":
    sys.exit(main())
