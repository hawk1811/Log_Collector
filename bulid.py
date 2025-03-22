#!/usr/bin/env python3
"""
Build script for creating standalone executables of Log Collector.
"""
import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

def main():
    """Main build function."""
    # Get the root directory
    root_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    
    print(f"Building Log Collector from {root_dir}")
    
    # Ensure empty data and logs directories exist
    data_dir = root_dir / "data"
    logs_dir = root_dir / "logs"
    data_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    
    # Detect platform
    is_windows = platform.system() == "Windows"
    is_linux = platform.system() == "Linux"
    is_macos = platform.system() == "Darwin"
    
    print(f"Detected platform: {platform.system()}")
    
    # Build main application executable
    build_main_executable(root_dir, is_windows, is_linux, is_macos)
    
    # Build service executable if on Windows
    if is_windows:
        build_service_executable(root_dir)
    
    # Create readme file in dist directory
    create_readme(root_dir, is_windows)
    
    print("Build completed successfully!")

def build_main_executable(root_dir, is_windows, is_linux, is_macos):
    """Build the main application executable."""
    print("Building main Log Collector executable...")
    
    # Basic PyInstaller command
    cmd = [
        "pyinstaller",
        "--name=Log_Collector",
        "--onefile",
        "--clean",
        "--noconfirm",
        f"--add-data=log_collector{os.pathsep}log_collector",
        f"--add-data=log_collector_service.py{os.pathsep}.",
        f"--add-data=data{os.pathsep}data",
        f"--add-data=logs{os.pathsep}logs",
    ]
    
    # Add hidden imports for all platforms
    hidden_imports = [
        "log_collector.cli.cli_main",
        "log_collector.cli.cli_utils",
        "log_collector.cli.cli_sources",
        "log_collector.cli.cli_status",
        "log_collector.cli.cli_health",
        "log_collector.cli.cli_auth",
        "log_collector.cli.cli_service",
        "log_collector.cli.cli_aggregation",
        "log_collector.cli.cli_filters",
        "prompt_toolkit",
        "colorama",
        "psutil",
        "requests",
        "json",
        "csv",
        "threading",
        "queue",
        "socket",
        "ssl",
        "logging",
        "multiprocessing",
    ]
    
    # Add Windows-specific hidden imports
    if is_windows:
        hidden_imports.extend([
            "win32api",
            "win32timezone",
            "win32service",
            "win32serviceutil",
            "win32event",
            "servicemanager",
            "winreg",
        ])
    
    # Add Linux-specific hidden imports
    if is_linux:
        hidden_imports.append("pwd")
    
    # Add all hidden imports to the command
    for hidden_import in hidden_imports:
        cmd.append(f"--hidden-import={hidden_import}")
    
    # Add the main script
    cmd.append(str(root_dir / "log_collector" / "main.py"))
    
    # Run PyInstaller
    print(f"Running command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def build_service_executable(root_dir):
    """Build the service executable (Windows only)."""
    print("Building Log Collector service executable...")
    
    cmd = [
        "pyinstaller",
        "--name=log_collector_service",
        "--onefile",
        "--clean",
        "--noconfirm",
        f"--add-data=log_collector{os.pathsep}log_collector",
        f"--add-data=data{os.pathsep}data",
        f"--add-data=logs{os.pathsep}logs",
        "--hidden-import=prompt_toolkit",
        "--hidden-import=colorama",
        "--hidden-import=psutil",
        "--hidden-import=requests",
        "--hidden-import=win32api",
        "--hidden-import=win32timezone",
        "--hidden-import=win32service",
        "--hidden-import=win32serviceutil",
        "--hidden-import=win32event",
        "--hidden-import=servicemanager",
        "--hidden-import=winreg",
        str(root_dir / "log_collector_service.py")
    ]
    
    # Run PyInstaller
    print(f"Running command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def create_readme(root_dir, is_windows):
    """Create a readme file in the dist directory."""
    dist_dir = root_dir / "dist"
    readme_path = dist_dir / "README.txt"
    
    readme_content = """Log Collector Standalone Application
==================================

This is a standalone executable version of Log Collector that includes all required dependencies.

"""
    
    if is_windows:
        readme_content += """Usage:
1. Run Log_Collector.exe to start the application with the CLI interface.
2. To run as a Windows service:
   - Install: log_collector_service.exe install
   - Start: log_collector_service.exe start
   - Stop: log_collector_service.exe stop
   - Remove: log_collector_service.exe remove

"""
    else:
        readme_content += """Usage:
1. Run ./Log_Collector to start the application with the CLI interface.
2. To run as a daemon service:
   - Start: ./Log_Collector --service start
   - Stop: ./Log_Collector --service stop
   - Status: ./Log_Collector --service status

"""
    
    readme_content += """Data Storage:
- Configuration and log templates are stored in the 'data' directory.
- Application logs are stored in the 'logs' directory.
- Both directories will be created automatically if they don't exist.

Troubleshooting:
- If you encounter issues with missing libraries, try running in console mode.
- Check logs in the 'logs' directory for detailed error information.
"""
    
    with open(readme_path, "w") as f:
        f.write(readme_content)
    
    print(f"Created readme file: {readme_path}")

if __name__ == "__main__":
    main()
