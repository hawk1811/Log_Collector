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
    
    # Handle specific submodules that need explicit inclusion
    "includedeps": True,
    
    # More modules that might be missed in automatic detection
    # These are modules imported at runtime or via __import__
    "excludes": ["tkinter", "test", "pydoc_data"],
    
    # Include files needed at runtime
    "include_files": [
        # README and documentation
        ("README.md", "README.md"),
        ("requirements.txt", "requirements.txt"),
    ],
    
    # Path where to put frozen files
    "build_exe": "build/exe",
    
    # Optimize Python bytecode to level 2
    "optimize": 2,
    
    # Compress the library archive
    "compressed": True,
    
    # Skip these modules - detect automatically
    "bin_excludes": [],
    
    # Path to search for modules
    "path": sys.path + ["log_collector"],
    
    # Add hooks to handle special cases
    "zip_includes": [],
    
    # Silent mode (reduce console output)
    "silent": False,
    
    # For better error checking during development, set to False in production
    "includes_testing": False,
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
        
        # Copyright information
        copyright="K.G - The Hawk © 2025",
        
        # Icon for Windows executable
        icon=icon_path if is_windows and icon_path else None,
        
        # For Windows: Add shortcut to the desktop
        shortcut_name="Log Collector",
        shortcut_dir="DesktopFolder" if is_windows else None,
    )
]

# On Windows, add a service installer executable
if is_windows:
    executables.append(
        Executable(
            # Script for service installation
            script="log_collector/main.py",
            
            # Target name for the executable
            target_name="LogCollectorService.exe",
            
            # Base to use
            base=base,
            
            # Copyright information
            copyright="K.G - The Hawk © 2025",
            
            # Icon for Windows executable
            icon=icon_path if icon_path else None,
            
            # Command line arguments for service installation
            cmd_args=["--service", "install"],
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
