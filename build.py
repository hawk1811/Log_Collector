# build_with_pyinstaller.py
import os
import platform
import shutil
import sys

# Determine the platform
is_windows = platform.system() == "Windows"

# Create data folder to bundle with the executable
data_dir = os.path.join("build", "data")
os.makedirs(data_dir, exist_ok=True)

# Create a simple README in the data directory
with open(os.path.join(data_dir, "README.txt"), "w") as f:
    f.write("Log Collector Data Directory\n")
    f.write("This folder will store logs and configuration files.\n")

# Create a hook file to handle path resolution
hook_file = "hook-log_collector.py"
with open(hook_file, "w") as f:
    f.write("""
# This is a PyInstaller hook file
from PyInstaller.utils.hooks import collect_data_files

# Tell PyInstaller to include our data files
datas = collect_data_files('log_collector')

# Add our data directory
datas.append(('build/data', 'data'))
""")

# Create a runtime hook to fix paths
runtime_hook = "runtime_hook.py"
with open(runtime_hook, "w") as f:
    f.write("""
import os
import sys
import tempfile

# Fix for frozen environment
def get_data_dir():
    # Get the directory where the executable is located
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_dir = os.path.dirname(sys.executable)
        # Create data directory if it doesn't exist
        data_dir = os.path.join(base_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    else:
        # Running as script
        from log_collector.config import DATA_DIR
        return DATA_DIR

# Patch the DATA_DIR in config.py
import log_collector.config
log_collector.config.DATA_DIR = get_data_dir()
# Also patch LOG_DIR
log_collector.config.LOG_DIR = os.path.join(get_data_dir(), 'logs')
os.makedirs(log_collector.config.LOG_DIR, exist_ok=True)

# Set default locations for service files
log_collector.config.DEFAULT_PID_FILE = os.path.join(get_data_dir(), 'service.pid')
log_collector.config.DEFAULT_LOG_FILE = os.path.join(get_data_dir(), 'service.log')

# Add a patch for the service module
def patch_service_module():
    try:
        import log_collector.service_module
        # Patch the handle_service_command function to handle the PyInstaller environment
        original_handle = log_collector.service_module.handle_service_command
        
        def patched_handle_service_command(command, pid_file=None, log_file=None, interactive=False):
            # Use default paths if not provided
            if pid_file is None:
                pid_file = log_collector.config.DEFAULT_PID_FILE
            if log_file is None:
                log_file = log_collector.config.DEFAULT_LOG_FILE
                
            # Special handling for 'start' command
            if command == 'start':
                # Create a batch file to start the service correctly
                batch_file = os.path.join(tempfile.gettempdir(), 'start_log_collector_service.bat')
                with open(batch_file, 'w') as f:
                    exe_path = sys.executable
                    f.write(f'@echo off\\n')
                    f.write(f'echo Starting Log Collector service...\\n')
                    f.write(f'"{exe_path}" --no-interactive --daemon ')
                    f.write(f'--pid-file="{pid_file}" --log-file="{log_file}"\\n')
                
                # Run the batch file
                import subprocess
                subprocess.Popen(['start', 'cmd', '/c', batch_file], shell=True)
                return True
                
            # For other commands, use the original function
            return original_handle(command, pid_file, log_file, interactive)
            
        # Replace the original function with our patched version
        log_collector.service_module.handle_service_command = patched_handle_service_command
    except Exception as e:
        print(f"Warning: Could not patch service module: {e}")

# Apply the patch
patch_service_module()
""")

# Main executable with improved options
main_cmd = "pyinstaller log_collector/main.py"
main_cmd += " --name LogCollector"  # Executable name
main_cmd += " --onefile"            # Create a single file
main_cmd += " --console"            # Console application
main_cmd += f" --add-data=build/data{os.pathsep}data"  # Add data directory
main_cmd += f" --runtime-hook={runtime_hook}"  # Add runtime hook
main_cmd += f" --additional-hooks-dir=."  # Add hook directory
main_cmd += " --hidden-import=log_collector.config"  # Ensure config is included
main_cmd += " --hidden-import=log_collector.source_manager"
main_cmd += " --hidden-import=log_collector.processor"
main_cmd += " --hidden-import=log_collector.listener"
main_cmd += " --hidden-import=log_collector.health_check"
main_cmd += " --hidden-import=log_collector.aggregation_manager"
main_cmd += " --hidden-import=log_collector.filter_manager"
main_cmd += " --hidden-import=log_collector.auth"
main_cmd += " --hidden-import=log_collector.cli_main"
main_cmd += " --hidden-import=log_collector.service_module"
main_cmd += " --clean"              # Clean PyInstaller cache

# If on Windows, add pywin32 hidden imports
if is_windows:
    try:
        import win32service
        main_cmd += " --hidden-import=win32service"
        main_cmd += " --hidden-import=win32serviceutil"
        main_cmd += " --hidden-import=win32event"
        main_cmd += " --hidden-import=servicemanager"
        main_cmd += " --hidden-import=win32api"
        main_cmd += " --hidden-import=win32con"
    except ImportError:
        print("Warning: pywin32 modules not found. Windows service functionality may be limited.")

# Execute the command
print(f"Running: {main_cmd}")
os.system(main_cmd)

# Create a service installer batch file
if is_windows:
    service_batch = os.path.join("dist", "InstallService.bat")
    with open(service_batch, "w") as f:
        f.write("@echo off\n")
        f.write("echo Installing Log Collector as a Windows service...\n")
        f.write("cd %~dp0\n")  # Change to batch file directory
        f.write("LogCollector.exe --service install\n")
        f.write("echo.\n")
        f.write("echo Service installation completed.\n")
        f.write("pause\n")
    
    service_uninstall = os.path.join("dist", "UninstallService.bat")
    with open(service_uninstall, "w") as f:
        f.write("@echo off\n")
        f.write("echo Uninstalling Log Collector service...\n")
        f.write("cd %~dp0\n")  # Change to batch file directory
        f.write("LogCollector.exe --service stop\n")
        f.write("sc delete LogCollectorService\n")
        f.write("echo.\n")
        f.write("echo Service uninstallation completed.\n")
        f.write("pause\n")

print("\nBuild completed. Executable and supporting files are in the 'dist' directory.")
