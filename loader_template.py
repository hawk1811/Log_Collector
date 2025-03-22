"""
LogCollector Standalone Application Loader
This script is designed to be the entry point for a standalone LogCollector application.
It extracts the bundled Python modules and resources, then launches the application.
"""
import os
import sys
import tempfile
import shutil
import zipfile
import base64
import hashlib
import subprocess
import platform
import time
import signal
import atexit

# Standalone mode flag - will be set to True when running as a standalone executable
STANDALONE_MODE = False

# Current executable path
EXECUTABLE_PATH = os.path.abspath(sys.argv[0])
BASE_DIR = os.path.dirname(EXECUTABLE_PATH)

# Application data directory
# In standalone mode, we create a .logcollector directory in user's home directory
if STANDALONE_MODE:
    USER_HOME = os.path.expanduser("~")
    APP_DATA_DIR = os.path.join(USER_HOME, ".logcollector")
    LOG_DIR = os.path.join(APP_DATA_DIR, "logs")
    PID_FILE = os.path.join(APP_DATA_DIR, "service.pid")
    LOG_FILE = os.path.join(LOG_DIR, "service.log")
else:
    # In development mode, use the current directory
    APP_DATA_DIR = os.path.join(BASE_DIR, "data")
    LOG_DIR = os.path.join(BASE_DIR, "logs")
    PID_FILE = os.path.join(APP_DATA_DIR, "service.pid")
    LOG_FILE = os.path.join(LOG_DIR, "service.log")

# Ensure directories exist
os.makedirs(APP_DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Setup base logging
import logging
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "loader.log"),
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("LogCollector_Loader")

# When running as a standalone executable, we need to extract the bundled application
if STANDALONE_MODE:
    """
    In standalone mode, this section will extract the embedded zip file containing
    all the Python modules and resources. The zipfile is embedded at the end of this
    script in the EMBEDDED_APPLICATION_DATA variable.
    
    The data is a base64-encoded zip file containing all necessary files.
    """
    logger.info("Running in standalone mode")
    
    try:
        # Extract embedded data
        logger.info("Extracting embedded application data")
        
        # Create a temporary directory for extraction
        temp_dir = os.path.join(tempfile.gettempdir(), f"logcollector_{os.getpid()}")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Decode and extract the embedded application data
        data = base64.b64decode(EMBEDDED_APPLICATION_DATA)
        
        # Verify checksum
        calculated_checksum = hashlib.sha256(data).hexdigest()
        if calculated_checksum != EMBEDDED_DATA_CHECKSUM:
            logger.error(f"Checksum verification failed. Expected: {EMBEDDED_DATA_CHECKSUM}, Got: {calculated_checksum}")
            sys.exit(1)
        
        # Write to temporary zip file
        zip_path = os.path.join(temp_dir, "app.zip")
        with open(zip_path, "wb") as f:
            f.write(data)
        
        # Extract zip contents
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Add to Python path so imports work
        sys.path.insert(0, temp_dir)
        
        # Setup cleanup on exit
        def cleanup_temp_dir():
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.error(f"Error cleaning up temporary directory: {e}")
        
        atexit.register(cleanup_temp_dir)
        
        logger.info(f"Application extracted to: {temp_dir}")
    
    except Exception as e:
        logger.error(f"Error extracting application: {e}")
        sys.exit(1)

# Now that we have the application code accessible, import the main module
try:
    # Import the LogCollector application
    from log_collector.config import (
        logger as app_logger,
        DATA_DIR,
        LOG_DIR as APP_LOG_DIR,
    )
    
    # Override the config paths to use our data directory
    import log_collector.config
    log_collector.config.DATA_DIR = APP_DATA_DIR
    log_collector.config.LOG_DIR = LOG_DIR
    log_collector.config.SOURCES_FILE = os.path.join(APP_DATA_DIR, "sources.json")
    
    # Also update default PID and log files
    from log_collector.service_module import DEFAULT_PID_FILE, DEFAULT_LOG_FILE
    log_collector.service_module.DEFAULT_PID_FILE = PID_FILE
    log_collector.service_module.DEFAULT_LOG_FILE = LOG_FILE
    
    # Import the main entry point
    from log_collector.main import main
    
    logger.info("Successfully imported LogCollector application")
    
except ImportError as e:
    logger.error(f"Failed to import LogCollector modules: {e}")
    sys.exit(1)

def handle_service_command():
    """
    Handle service-related commands specifically for the standalone application
    """
    if len(sys.argv) >= 2 and sys.argv[1] == "--service":
        command = sys.argv[2] if len(sys.argv) > 2 else "start"
        
        if command == "start":
            # Handle service start command
            from log_collector.service_module import start_service
            logger.info(f"Starting service with PID file: {PID_FILE}, Log file: {LOG_FILE}")
            result = start_service(False, PID_FILE, LOG_FILE)
            sys.exit(0 if result else 1)
            
        elif command == "stop":
            # Handle service stop command
            from log_collector.service_module import stop_service
            logger.info(f"Stopping service with PID file: {PID_FILE}")
            result = stop_service(PID_FILE)
            sys.exit(0 if result else 1)
            
        elif command == "restart":
            # Handle service restart command
            from log_collector.service_module import restart_service
            logger.info(f"Restarting service with PID file: {PID_FILE}, Log file: {LOG_FILE}")
            result = restart_service(PID_FILE, LOG_FILE)
            sys.exit(0 if result else 1)
            
        elif command == "status":
            # Handle service status command
            from log_collector.service_module import get_service_status
            logger.info(f"Checking service status with PID file: {PID_FILE}")
            result = get_service_status(PID_FILE)
            sys.exit(0 if result else 1)
            
        elif command == "install" and platform.system() == "Windows":
            # Handle Windows service installation
            logger.info("Installing Windows service")
            from log_collector.service_module import register_windows_service
            result = register_windows_service()
            sys.exit(0 if result else 1)

# Check for service-related commands
handle_service_command()

# Pass command-line arguments to the main function, with modified paths
if STANDALONE_MODE:
    # Modify command line arguments to use our data directory
    updated_args = []
    i = 0
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--data-dir":
            # Skip this argument and its value
            i += 2
            continue
        elif arg == "--log-dir":
            # Skip this argument and its value
            i += 2
            continue
        elif arg == "--pid-file":
            # Skip this argument and its value
            i += 2
            continue
        elif arg == "--log-file":
            # Skip this argument and its value
            i += 2
            continue
        else:
            updated_args.append(arg)
        i += 1
    
    # Add our directory paths
    updated_args.extend(["--data-dir", APP_DATA_DIR])
    updated_args.extend(["--log-dir", LOG_DIR])
    updated_args.extend(["--pid-file", PID_FILE])
    updated_args.extend(["--log-file", LOG_FILE])
    
    # Replace sys.argv
    sys.argv = updated_args

# Start the application
logger.info("Starting LogCollector application")
sys.exit(main())

# The following variables will be populated during the build process:
# EMBEDDED_APPLICATION_DATA - base64 encoded zip file containing the application
# EMBEDDED_DATA_CHECKSUM - SHA-256 checksum of the decoded data

EMBEDDED_APPLICATION_DATA = ""
EMBEDDED_DATA_CHECKSUM = ""
