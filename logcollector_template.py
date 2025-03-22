#!/usr/bin/env python3
"""
LogCollector Standalone Application

This is a self-contained version of LogCollector that:
1. Extracts the embedded application code
2. Sets up the correct data directories
3. Launches the application

The application data is stored in ~/.logcollector/ by default.
"""
import os
import sys
import base64
import zipfile
import hashlib
import tempfile
import shutil
import platform
import logging
import signal
import atexit
from pathlib import Path

# ==== Configuration ====

# Get user's home directory
HOME_DIR = str(Path.home())

# Application data directory
APP_DATA_DIR = os.path.join(HOME_DIR, ".logcollector")
LOG_DIR = os.path.join(APP_DATA_DIR, "logs")
DEFAULT_PID_FILE = os.path.join(APP_DATA_DIR, "service.pid")
DEFAULT_LOG_FILE = os.path.join(LOG_DIR, "service.log")

# Create directories if they don't exist
os.makedirs(APP_DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "standalone.log"),
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("LogCollector")

# Add console logging
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ==== Extraction Code ====

def extract_application():
    """Extract the embedded application to a temporary directory."""
    logger.info("Extracting embedded application...")
    
    # Base64-encoded application data (will be replaced during build)
    EMBEDDED_DATA = "##EMBEDDED_DATA##"
    DATA_CHECKSUM = "##DATA_CHECKSUM##"
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix="logcollector_")
    
    try:
        # Decode the embedded data
        zip_data = base64.b64decode(EMBEDDED_DATA)
        
        # Verify checksum
        calculated_checksum = hashlib.sha256(zip_data).hexdigest()
        if calculated_checksum != DATA_CHECKSUM:
            logger.error(f"Checksum verification failed! Expected: {DATA_CHECKSUM}, Got: {calculated_checksum}")
            return None
        
        # Extract to temporary location
        zip_path = os.path.join(temp_dir, "app.zip")
        with open(zip_path, "wb") as f:
            f.write(zip_data)
        
        # Extract ZIP file
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Register cleanup
        def cleanup_temp():
            try:
                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.error(f"Error cleaning up: {e}")
        
        atexit.register(cleanup_temp)
        
        # Add to Python path
        sys.path.insert(0, temp_dir)
        
        logger.info(f"Application extracted to: {temp_dir}")
        return temp_dir
    
    except Exception as e:
        logger.error(f"Error extracting application: {e}")
        shutil.rmtree(temp_dir)
        return None

# ==== Main Application ====

def main():
    """Main entry point for the standalone application."""
    
    logger.info("Starting LogCollector standalone application")
    
    # Extract the application
    app_dir = extract_application()
    if not app_dir:
        logger.critical("Failed to extract application. Exiting.")
        return 1
    
    try:
        # Now we can import the actual LogCollector code
        # First, patch the configuration to use our data directory
        import log_collector.config
        
        # Instead of replacing Path objects with strings, patch the Path methods
        # This ensures compatibility with both string operations and Path methods
        class PatchedPath(str):
            def __new__(cls, path_str):
                return super(PatchedPath, cls).__new__(cls, path_str)
            
            def exists(self):
                return os.path.exists(self)
            
            def resolve(self):
                return PatchedPath(os.path.abspath(self))
            
            def parent(self):
                return PatchedPath(os.path.dirname(self))
            
            @property
            def parents(self):
                # Simple implementation that returns list of parent directories
                parts = self.split(os.sep)
                result = []
                for i in range(len(parts)-1, 0, -1):
                    result.append(PatchedPath(os.sep.join(parts[:i])))
                return result
            
            def mkdir(self, parents=False, exist_ok=False):
                if parents:
                    os.makedirs(self, exist_ok=exist_ok)
                else:
                    try:
                        os.mkdir(self)
                    except FileExistsError:
                        if not exist_ok:
                            raise
            
            def __truediv__(self, other):
                return PatchedPath(os.path.join(self, other))
            
            def __rtruediv__(self, other):
                return PatchedPath(os.path.join(other, self))
        
        # Override config paths with our patched versions
        log_collector.config.DATA_DIR = PatchedPath(APP_DATA_DIR)
        log_collector.config.LOG_DIR = PatchedPath(LOG_DIR)
        log_collector.config.SOURCES_FILE = PatchedPath(os.path.join(APP_DATA_DIR, "sources.json"))
        
        # Patch service module paths
        try:
            import log_collector.service_module
            log_collector.service_module.DEFAULT_PID_FILE = PatchedPath(DEFAULT_PID_FILE)
            log_collector.service_module.DEFAULT_LOG_FILE = PatchedPath(DEFAULT_LOG_FILE)
        except ImportError:
            logger.warning("Could not patch service module paths")
        
        # Patch Path methods in other modules that might use them
        try:
            # Monkey-patch Path constructor to use our PatchedPath
            original_path = Path
            
            def patched_path_constructor(*args, **kwargs):
                result = original_path(*args, **kwargs)
                return PatchedPath(str(result))
            
            # Replace Path in specific modules
            sys.modules['pathlib'].Path = patched_path_constructor
            
            # Also patch Path objects in config modules directly
            for module_name in list(sys.modules.keys()):
                if module_name.startswith('log_collector.'):
                    module = sys.modules[module_name]
                    for attr_name in dir(module):
                        try:
                            attr = getattr(module, attr_name)
                            if isinstance(attr, original_path):
                                setattr(module, attr_name, PatchedPath(str(attr)))
                        except (AttributeError, TypeError):
                            pass
        except Exception as e:
            logger.warning(f"Error patching Path objects: {e}")
        
        # Process command-line arguments for service operations
        if len(sys.argv) > 1 and sys.argv[1] == "--service":
            service_cmd = sys.argv[2] if len(sys.argv) > 2 else "start"
            
            try:
                from log_collector.service_module import (
                    start_service,
                    stop_service,
                    restart_service,
                    get_service_status
                )
                
                if service_cmd == "start":
                    logger.info(f"Starting service with PID file: {DEFAULT_PID_FILE}")
                    success = start_service(False, DEFAULT_PID_FILE, DEFAULT_LOG_FILE)
                    return 0 if success else 1
                
                elif service_cmd == "stop":
                    logger.info(f"Stopping service with PID file: {DEFAULT_PID_FILE}")
                    success = stop_service(DEFAULT_PID_FILE)
                    return 0 if success else 1
                
                elif service_cmd == "restart":
                    logger.info(f"Restarting service")
                    success = restart_service(DEFAULT_PID_FILE, DEFAULT_LOG_FILE)
                    return 0 if success else 1
                
                elif service_cmd == "status":
                    logger.info(f"Checking service status")
                    success = get_service_status(DEFAULT_PID_FILE)
                    return 0 if success else 1
                
                elif service_cmd == "install" and platform.system() == "Windows":
                    logger.info(f"Installing Windows service")
                    # Import here to prevent errors on non-Windows platforms
                    from log_collector.service_module import register_windows_service
                    success = register_windows_service()
                    return 0 if success else 1
                
                else:
                    logger.error(f"Unknown service command: {service_cmd}")
                    return 1
                    
            except ImportError as e:
                logger.error(f"Service module could not be imported: {e}")
                return 1
        
        # Import main function
        from log_collector.main import main as lc_main
        
        # Replace sys.argv with our modified version
        old_argv = sys.argv.copy()
        
        # Build new arguments
        new_args = [old_argv[0]]  # Keep the original executable name
        
        # Add data directory arguments explicitly
        new_args.extend(["--data-dir", APP_DATA_DIR])
        new_args.extend(["--log-dir", LOG_DIR])
        new_args.extend(["--pid-file", DEFAULT_PID_FILE])
        new_args.extend(["--log-file", DEFAULT_LOG_FILE])
        
        # Add any other arguments that aren't related to paths
        for arg in old_argv[1:]:
            if arg not in ["--data-dir", "--log-dir", "--pid-file", "--log-file"] and not arg.startswith("--data-dir=") and not arg.startswith("--log-dir=") and not arg.startswith("--pid-file=") and not arg.startswith("--log-file="):
                new_args.append(arg)
        
        # Replace sys.argv
        sys.argv = new_args
        
        # Run the main application
        logger.info("Starting LogCollector main application")
        return lc_main()
    
    except Exception as e:
        logger.exception(f"Error running LogCollector: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
