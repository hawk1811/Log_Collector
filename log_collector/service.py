"""
Log Collector Service.
Runs the entire Log Collector application as a system service.
"""
import os
import sys
import time
import signal
import logging
import argparse
import platform
import subprocess
from pathlib import Path

from log_collector.config import logger, DATA_DIR, LOG_DIR, load_sources
from log_collector.source_manager import SourceManager
from log_collector.processor import ProcessorManager
from log_collector.listener import LogListener
from log_collector.health_check import HealthCheck
from log_collector.utils import get_version

# Global variables for service components
source_manager = None
processor_manager = None
listener_manager = None
health_check = None
running = True

def signal_handler(signum, frame):
    """Handle termination signals."""
    global running
    logger.info(f"Log Collector Service: Received signal {signum}, shutting down...")
    running = False

def cleanup():
    """Clean up resources before exiting."""
    global processor_manager, listener_manager, health_check
    
    logger.info("Log Collector Service: Cleaning up resources...")
    
    # Stop health check if running
    if health_check is not None and hasattr(health_check, 'running') and health_check.running:
        logger.info("- Stopping health check...")
        health_check.stop()
    
    # Stop processor manager
    if processor_manager is not None:
        logger.info("- Stopping processors...")
        processor_manager.stop()
    
    # Stop listener manager
    if listener_manager is not None:
        logger.info("- Stopping listeners...")
        listener_manager.stop()
    
    logger.info("Log Collector Service: Cleanup completed")

def write_status_file():
    """Write service status to file for CLI to read."""
    try:
        status_file = DATA_DIR / "service_status.json"
        
        import json
        status = {
            "timestamp": int(time.time()),
            "running": running,
            "version": get_version(),
            "sources_count": len(source_manager.get_sources()) if source_manager else 0,
            "processor_running": processor_manager.running if processor_manager else False,
            "listener_running": listener_manager.running if listener_manager else False,
            "health_check_running": health_check.running if (health_check and hasattr(health_check, 'running')) else False,
            "pid": os.getpid()
        }
        
        with open(status_file, "w") as f:
            json.dump(status, f, indent=2)
    
    except Exception as e:
        logger.error(f"Error writing status file: {e}")

def run_service():
    """Run the Log Collector service."""
    global running, source_manager, processor_manager, listener_manager, health_check
    
    logger.info("Log Collector Service: Starting")
    
    # Initialize components
    source_manager = SourceManager()
    processor_manager = ProcessorManager(source_manager)
    listener_manager = LogListener(source_manager, processor_manager)
    health_check = HealthCheck(source_manager, processor_manager)
    
    # Start components
    sources = source_manager.get_sources()
    if sources:
        logger.info(f"Starting with {len(sources)} configured sources")
        processor_manager.start()
        listener_manager.start()
    else:
        logger.warning("No sources configured. Log Collector is running but not processing logs.")
    
    # Try to load health check configuration and start if configured
    try:
        # Look for health check config file
        health_check_config_file = DATA_DIR / "health_check.json"
        if health_check_config_file.exists():
            import json
            with open(health_check_config_file, "r") as f:
                health_config = json.load(f)
                
            if health_config.get("enabled", False):
                hec_url = health_config.get("hec_url")
                hec_token = health_config.get("hec_token")
                interval = health_config.get("interval", 60)
                
                if hec_url and hec_token:
                    if health_check.configure(hec_url, hec_token, interval):
                        if health_check.start():
                            logger.info("Health check monitoring started automatically")
    except Exception as e:
        logger.error(f"Error starting health check: {e}")
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create PID file
    pid_file = DATA_DIR / "logcollector.pid"
    try:
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.error(f"Error writing PID file: {e}")
    
    # Main service loop
    config_check_interval = 30  # seconds
    status_update_interval = 10  # seconds
    last_config_check = 0
    last_status_update = 0
    
    logger.info("Log Collector Service: Running")
    
    try:
        while running:
            current_time = time.time()
            
            # Periodically check for configuration changes
            if current_time - last_config_check > config_check_interval:
                last_config_check = current_time
                
                # Check for source updates
                new_sources = load_sources()
                if new_sources != sources:
                    logger.info("Log Collector Service: Source configuration changed, reloading...")
                    
                    # Stop current components
                    listener_manager.stop()
                    processor_manager.stop()
                    
                    # Update sources
                    sources = new_sources
                    
                    # Restart components with new configuration
                    if sources:
                        processor_manager.start()
                        listener_manager.start()
            
            # Update status file
            if current_time - last_status_update > status_update_interval:
                last_status_update = current_time
                write_status_file()
            
            # Sleep to avoid high CPU usage
            time.sleep(1)
    
    except Exception as e:
        logger.error(f"Log Collector Service: Error in main loop: {e}", exc_info=True)
    
    finally:
        # Clean up
        cleanup()
        
        # Remove PID file
        try:
            if pid_file.exists():
                pid_file.unlink()
        except Exception as e:
            logger.error(f"Error removing PID file: {e}")
    
    logger.info("Log Collector Service: Stopped")

def daemonize():
    """Daemonize the process (Unix only)."""
    # Skip on Windows - use Windows Service
    if platform.system() == "Windows":
        return
    
    try:
        # First fork
        pid = os.fork()
        if pid > 0:
            # Exit first parent
            sys.exit(0)
    except OSError as e:
        logger.error(f"Fork #1 failed: {e.errno} ({e.strerror})")
        sys.exit(1)
    
    # Decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)
    
    # Second fork
    try:
        pid = os.fork()
        if pid > 0:
            # Exit from second parent
            sys.exit(0)
    except OSError as e:
        logger.error(f"Fork #2 failed: {e.errno} ({e.strerror})")
        sys.exit(1)
    
    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    
    with open(os.devnull, "r") as null_in:
        os.dup2(null_in.fileno(), sys.stdin.fileno())
    
    with open(os.devnull, "w") as null_out:
        os.dup2(null_out.fileno(), sys.stdout.fileno())
        os.dup2(null_out.fileno(), sys.stderr.fileno())

def create_systemd_service():
    """Create systemd service file."""
    logger.info("Creating systemd service file...")
    
    service_content = f"""[Unit]
Description=Log Collector Service
After=network.target

[Service]
Type=simple
ExecStart={sys.executable} -m log_collector.service
Restart=on-failure
RestartSec=5s
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=logcollector

[Install]
WantedBy=multi-user.target
"""
    
    try:
        service_path = "/etc/systemd/system/logcollector.service"
        with open(service_path, "w") as f:
            f.write(service_content)
        
        os.chmod(service_path, 0o644)
        
        # Enable the service
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "enable", "logcollector"], check=True)
        
        logger.info("Systemd service created and enabled")
        return True
    
    except Exception as e:
        logger.error(f"Error creating systemd service: {e}")
        return False

def create_windows_service():
    """Create Windows service."""
    logger.info("Creating Windows service...")
    
    try:
        # Check if pywin32 is installed
        import win32serviceutil
        import win32service
        import win32event
        import servicemanager
    except ImportError:
        logger.error("pywin32 is required to create Windows service. Please install with: pip install pywin32")
        return False
    
    # Create wrapper script
    wrapper_path = DATA_DIR / "win_service_wrapper.py"
    
    wrapper_content = """
import os
import sys
import time
import servicemanager
import win32serviceutil
import win32service
import win32event

class LogCollectorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "LogCollector"
    _svc_display_name_ = "Log Collector Service"
    _svc_description_ = "High-performance log collection and processing system"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process = None
    
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        
        # Stop Log Collector service
        import subprocess
        subprocess.run(["python", "-m", "log_collector.service", "stop"], check=False)
        
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
    
    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        # Start Log Collector service
        import subprocess
        self.process = subprocess.Popen(
            ["python", "-m", "log_collector.service", "run"],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Wait for stop event
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(LogCollectorService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(LogCollectorService)
"""
    
    try:
        with open(wrapper_path, "w") as f:
            f.write(wrapper_content)
        
        # Install the service
        subprocess.run([sys.executable, str(wrapper_path), "install"], check=True)
        
        logger.info("Windows service created")
        return True
    
    except Exception as e:
        logger.error(f"Error creating Windows service: {e}")
        return False

def remove_systemd_service():
    """Remove systemd service."""
    logger.info("Removing systemd service...")
    
    try:
        # Stop and disable the service
        subprocess.run(["systemctl", "stop", "logcollector"], check=False)
        subprocess.run(["systemctl", "disable", "logcollector"], check=True)
        
        # Remove service file
        service_path = "/etc/systemd/system/logcollector.service"
        if os.path.exists(service_path):
            os.remove(service_path)
        
        # Reload systemd
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        
        logger.info("Systemd service removed")
        return True
    
    except Exception as e:
        logger.error(f"Error removing systemd service: {e}")
        return False

def remove_windows_service():
    """Remove Windows service."""
    logger.info("Removing Windows service...")
    
    try:
        # Check if pywin32 is installed
        import win32serviceutil
    except ImportError:
        logger.error("pywin32 is required to remove Windows service. Please install with: pip install pywin32")
        return False
    
    # Get wrapper script path
    wrapper_path = DATA_DIR / "win_service_wrapper.py"
    
    if not wrapper_path.exists():
        # Create a temporary wrapper just for removal
        with open(wrapper_path, "w") as f:
            f.write("""
import win32serviceutil

class LogCollectorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "LogCollector"
    _svc_display_name_ = "Log Collector Service"

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(LogCollectorService)
""")
    
    try:
        # Remove the service
        subprocess.run([sys.executable, str(wrapper_path), "remove"], check=True)
        
        logger.info("Windows service removed")
        return True
    
    except Exception as e:
        logger.error(f"Error removing Windows service: {e}")
        return False
    
    finally:
        # Clean up temporary wrapper
        try:
            if wrapper_path.exists():
                os.remove(wrapper_path)
        except:
            pass

def is_service_running():
    """Check if the service is already running."""
    pid_file = DATA_DIR / "logcollector.pid"
    
    if not pid_file.exists():
        return False
    
    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
        
        # Check if process is running
        os.kill(pid, 0)  # This raises an exception if process doesn't exist
        return True
    
    except (OSError, ValueError):
        # Process not running or PID file invalid
        return False

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Log Collector Service")
    parser.add_argument(
        "command", 
        choices=["run", "stop", "status", "install", "uninstall"],
        help="Command to execute"
    )
    parser.add_argument(
        "--daemon", 
        action="store_true", 
        help="Run as daemon process (Unix only)"
    )
    
    return parser.parse_args()

def main():
    """Main entry point."""
    # Create directories if they don't exist
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # Parse command line arguments
    args = parse_args()
    
    if args.command == "run":
        # Check if already running
        if is_service_running():
            logger.error("Log Collector Service is already running")
            return 1
        
        # Run as daemon if requested
        if args.daemon:
            daemonize()
        
        # Run the service
        run_service()
    
    elif args.command == "stop":
        # Check if running
        if not is_service_running():
            logger.error("Log Collector Service is not running")
            return 1
        
        # Get PID
        pid_file = DATA_DIR / "logcollector.pid"
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            
            # Send termination signal
            os.kill(pid, signal.SIGTERM)
            
            # Wait for service to stop
            for _ in range(10):  # Wait up to 10 seconds
                time.sleep(1)
                try:
                    os.kill(pid, 0)  # Check if process exists
                except OSError:
                    # Process has stopped
                    logger.info("Log Collector Service stopped")
                    return 0
            
            # Service didn't stop, try force kill
            logger.warning("Service didn't stop gracefully, using SIGKILL")
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        
        except (ValueError, OSError, IOError) as e:
            logger.error(f"Error stopping service: {e}")
            return 1
    
    elif args.command == "status":
        # Check if running
        if is_service_running():
            # Read status file if available
            status_file = DATA_DIR / "service_status.json"
            if status_file.exists():
                try:
                    import json
                    with open(status_file, "r") as f:
                        status = json.load(f)
                    
                    print("Log Collector Service is running")
                    print(f"PID: {status.get('pid', 'Unknown')}")
                    print(f"Version: {status.get('version', 'Unknown')}")
                    print(f"Sources: {status.get('sources_count', 0)}")
                    print(f"Processor running: {status.get('processor_running', False)}")
                    print(f"Listener running: {status.get('listener_running', False)}")
                    print(f"Health check running: {status.get('health_check_running', False)}")
                    print(f"Last update: {time.ctime(status.get('timestamp', 0))}")
                
                except Exception as e:
                    print("Log Collector Service is running, but status details are unavailable")
            else:
                print("Log Collector Service is running")
        else:
            print("Log Collector Service is not running")
    
    elif args.command == "install":
        # Install as system service
        if platform.system() == "Linux":
            if create_systemd_service():
                print("Log Collector Service installed as systemd service")
                print("You can start it with: sudo systemctl start logcollector")
            else:
                print("Failed to install systemd service")
                return 1
        
        elif platform.system() == "Windows":
            if create_windows_service():
                print("Log Collector Service installed as Windows service")
                print("You can start it from Services control panel or with: sc start LogCollector")
            else:
                print("Failed to install Windows service")
                return 1
        
        else:
            print(f"Service installation not supported on {platform.system()}")
            return 1
    
    elif args.command == "uninstall":
        # Uninstall system service
        if platform.system() == "Linux":
            if remove_systemd_service():
                print("Log Collector Service removed")
            else:
                print("Failed to remove systemd service")
                return 1
        
        elif platform.system() == "Windows":
            if remove_windows_service():
                print("Log Collector Service removed")
            else:
                print("Failed to remove Windows service")
                return 1
        
        else:
            print(f"Service uninstallation not supported on {platform.system()}")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
