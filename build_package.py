# build_package.py
import sys
import os
import platform
from cx_Freeze import setup, Executable

# Determine the base for the executable
# For GUI applications on Windows, use "Win32GUI"
# For console applications, use "Console"
base = None
if platform.system() == "Windows":
    base = "Console"

# Get the current platform
is_windows = platform.system() == "Windows"
is_linux = platform.system() == "Linux"
is_macos = platform.system() == "Darwin"

# Common build options
build_exe_options = {
    # Include packages that might not be detected automatically
    "packages": [
        "os", "sys", "json", "time", "signal", "logging", "threading", 
        "queue", "re", "hashlib", "secrets", "datetime", "socket",
        "pathlib", "uuid", "gzip", "atexit", "tempfile", "subprocess"
    ],
    
    # Specify packages to include (with all sub-modules)
    "includes": [
        "log_collector",
        "requests",
        "psutil",
        "prompt_toolkit",
        "colorama",
        "bcrypt", 
        "cryptography"
    ],
    
    # More modules that might be missed in automatic detection
    # These are modules imported at runtime or via __import__
    "excludes": ["tkinter", "test", "pydoc_data"],
    
    # Include files needed at runtime
    "include_files": [
        # README and documentation
        ("README.md", "README.md"),
        ("requirements.txt", "requirements.txt"),
    ],
    
    # Optimize Python bytecode
    "optimize": 2,
    
    # Path to search for modules
    "path": sys.path + ["log_collector"],
}

# Add platform-specific dependencies
if is_windows:
    # Add Windows-specific packages
    build_exe_options["packages"].extend(["win32service", "win32serviceutil", "win32event", "servicemanager", "socket"])
    
    # Ensure pywin32 is included on Windows
    if "win32" not in build_exe_options["includes"]:
        build_exe_options["includes"].append("win32api")
        build_exe_options["includes"].append("win32con")
        build_exe_options["includes"].append("win32serviceutil")
        
    # Add icon for Windows
    icon_path = None  # Add path to icon file if available

# Define executables
executables = [
    Executable(
        # Main script
        script="log_collector/main.py",
        
        # Target name for the executable
        target_name="LogCollector.exe" if is_windows else "LogCollector",
        
        # Base to use
        base=base,
        
        # Icon for Windows executable
        icon=icon_path if is_windows and icon_path else None,
    )
]

# On Windows, add a service installer executable
if is_windows:
    # Create a service installer script
    with open("log_collector/service_installer.py", "w") as f:
        f.write("""
import sys
import os

# Add the arguments needed for service installation
sys.argv.extend(["--service", "install"])

# Import and run the main function
from log_collector.main import main
main()
""")
    
    # Then add it to the executables
    executables.append(
        Executable(
            # Script for service installation
            script="log_collector/service_installer.py",
            
            # Target name for the executable
            target_name="LogCollectorService.exe",
            
            # Base to use
            base=base,
            
            # Icon for Windows executable
            icon=icon_path if icon_path else None,
        )
    )

# Setup
setup(
    name="LogCollector",
    version="1.0.0",
    description="High-performance log collection and processing system",
    author="K.G - The Hawk",
    author_email="the.hawk1811@gmail.com",
    options={"build_exe": build_exe_options},
    executables=executables,
)
