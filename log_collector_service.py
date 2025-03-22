#!/usr/bin/env python3
"""
Cross-platform service implementation for Log Collector.
Supports Windows service and Linux daemon modes.
"""
import os
import sys
import time
import argparse
import logging
import platform
from pathlib import Path

# Import Log Collector components
from log_collector.source_manager import SourceManager
from log_collector.processor import ProcessorManager
from log_collector.listener import LogListener
from log_collector.health_check import HealthCheck
from log_collector.aggregation_manager import AggregationManager
from log_collector.filter_manager import FilterManager
from log_collector.config import logger

# Setup logger for the service
def setup_logging(log_file):
    """Setup logging for the service"""
    service_logger = logging.getLogger('LogCollectorService')
    service_logger.setLevel(logging.INFO)
    
    # Create log directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Configure file handler
    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    service_logger.addHandler(handler)
    
    # Also add a console handler for better debugging
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    service_logger.addHandler(console_handler)
    
    return service_logger
    
# Helper function to get data directory
def get_data_dir():
    """Get the data directory path - simply ./data relative to script location"""
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create data path within this directory
    data_dir = os.path.join(script_dir, "data")
    print(f"Script directory: {script_dir}")
    print(f"Using data directory: {data_dir}")
    
    # Ensure the directory exists
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        print(f"Created data directory: {data_dir}")
    
    return data_dir
    
# Service components shared between platforms
class LogCollectorService:
    """
    Core functionality for the Log Collector service,
    shared between Windows and Linux implementations.
    """
    def __init__(self, logger):
        self.logger = logger
        self.is_running = False
        
        # Initialize components
        self.source_manager = None
        self.aggregation_manager = None
        self.filter_manager = None
        self.processor_manager = None
        self.listener_manager = None
        self.health_check = None
    
    def initialize(self):
        """Initialize Log Collector components"""
        self.logger.info("Initializing Log Collector components...")
        
        try:
            self.source_manager = SourceManager()
            self.aggregation_manager = AggregationManager()
            self.filter_manager = FilterManager()
            
            self.processor_manager = ProcessorManager(
                self.source_manager, 
                self.aggregation_manager, 
                self.filter_manager
            )
            
            self.listener_manager = LogListener(
                self.source_manager, 
                self.processor_manager
            )
            
            self.health_check = HealthCheck(
                self.source_manager, 
                self.processor_manager
            )
            
            self.logger.info("Components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing components: {e}", exc_info=True)
            return False
    
    def start(self):
        """Start the Log Collector service"""
        self.logger.info("Starting Log Collector service...")
        
        if not self.initialize():
            return False
        
        try:
            # Start components
            self.processor_manager.start()
            self.logger.info("Processor manager started")
            
            self.listener_manager.start()
            self.logger.info("Listener manager started")
            
            # Start health check if configured
            if hasattr(self.health_check, 'config') and self.health_check.config is not None:
                if self.health_check.start():
                    self.logger.info("Health check monitoring started")
                else:
                    self.logger.warning("Health check failed to start")
            
            self.is_running = True
            self.logger.info("Log Collector service started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting service: {e}", exc_info=True)
            self.stop()  # Try to clean up any started components
            return False
    
    def stop(self):
        """Stop the Log Collector service"""
        self.logger.info("Stopping Log Collector service...")
        
        try:
            # Stop components in reverse order
            if hasattr(self, 'health_check') and hasattr(self.health_check, 'running') and self.health_check.running:
                self.health_check.stop()
                self.logger.info("Health check stopped")
            
            if hasattr(self, 'processor_manager'):
                self.processor_manager.stop()
                self.logger.info("Processor manager stopped")
            
            if hasattr(self, 'listener_manager'):
                self.listener_manager.stop()
                self.logger.info("Listener manager stopped")
            
            self.is_running = False
            self.logger.info("Log Collector service stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping service: {e}", exc_info=True)
            return False


# Platform-specific implementations
if platform.system() == 'Windows':
    # Windows Service Implementation
    try:
        import win32service
        import win32serviceutil
        import win32event
        import servicemanager
        import socket

        class WindowsService(win32serviceutil.ServiceFramework):
            _svc_name_ = "LogCollector"
            _svc_display_name_ = "Log Collector Service"
            _svc_description_ = "High-performance log collection and processing system"
            
            def __init__(self, args):
                win32serviceutil.ServiceFramework.__init__(self, args)
                self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
                socket.setdefaulttimeout(60)
                
                # Get the data directory
                data_dir = get_data_dir()
                
                # Get log file path from environment if available, otherwise use default in data dir
                if "LOG_COLLECTOR_LOG_FILE" in os.environ:
                    log_file = os.environ["LOG_COLLECTOR_LOG_FILE"]
                else:
                    log_file = os.path.join(data_dir, 'service.log')
                
                # Get pid file path from environment if available, otherwise use default in data dir
                if "LOG_COLLECTOR_PID_FILE" in os.environ:
                    pid_file = os.environ["LOG_COLLECTOR_PID_FILE"]
                else:
                    pid_file = os.path.join(data_dir, 'service.pid')
                
                # Setup logging
                self.logger = setup_logging(log_file)
                self.logger.info(f"Windows service initialized with log file: {log_file}")
                self.logger.info(f"Using PID file: {pid_file}")
                
                # Write PID file
                try:
                    with open(pid_file, 'w') as f:
                        f.write(str(os.getpid()))
                    self.logger.info(f"Wrote PID file to {pid_file}")
                    
                    # Store the path for reference in other methods
                    self.pid_file = pid_file
                    
                    # Register cleanup function
                    def remove_pid_file():
                        try:
                            if os.path.exists(pid_file):
                                os.remove(pid_file)
                                self.logger.info(f"Removed PID file {pid_file}")
                        except Exception as e:
                            self.logger.error(f"Failed to remove PID file: {e}")
                    
                    import atexit
                    atexit.register(remove_pid_file)
                    
                except Exception as e:
                    self.logger.error(f"Failed to write PID file: {e}")
                
                # Create service instance
                self.service = LogCollectorService(self.logger)
            
            def SvcStop(self):
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                win32event.SetEvent(self.hWaitStop)
                
                # Stop the service
                self.service.stop()
                
                # Clean up PID file
                try:
                    if hasattr(self, 'pid_file') and os.path.exists(self.pid_file):
                        os.remove(self.pid_file)
                        self.logger.info(f"Removed PID file {self.pid_file} during stop")
                except Exception as e:
                    self.logger.error(f"Failed to remove PID file during stop: {e}")
            
            def SvcDoRun(self):
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STARTED,
                    (self._svc_name_, '')
                )
                
                # Start the service
                if not self.service.start():
                    self.logger.error("Failed to start service")
                    self.SvcStop()
                    return
                
                # Main service loop
                while True:
                    # Check if stop signal received
                    if win32event.WaitForSingleObject(self.hWaitStop, 5000) == win32event.WAIT_OBJECT_0:
                        break
        
        def run_windows_service():
            # Check if first argument is a service command
            if len(sys.argv) > 1 and sys.argv[1] in ['install', 'update', 'remove', '--startup', '-h', '--help']:
                # Handle service management commands
                win32serviceutil.HandleCommandLine(WindowsService)
                return
            
            # Special handling for start command - use the Windows service controller
            if len(sys.argv) > 1 and sys.argv[1] == "start":
                try:
                    # Try to start the Windows service if installed
                    import subprocess
                    result = subprocess.run(
                        ["sc", "query", "LogCollector"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    
                    if result.returncode == 0:
                        # Service exists, start it
                        print("Starting LogCollector Windows service...")
                        result = subprocess.run(
                            ["sc", "start", "LogCollector"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False
                        )
                        
                        if result.returncode == 0:
                            print("LogCollector service started successfully")
                            return
                        else:
                            print(f"Failed to start LogCollector service: {result.stderr}")
                            # Fall through to manual execution if service start fails
                    else:
                        print("LogCollector service is not installed. Starting in foreground mode.")
                        # Fall through to manual execution
                        
                except Exception as e:
                    print(f"Error starting service: {e}")
                    # Fall through to manual execution
            
            # Special handling for stop command - use the Windows service controller
            if len(sys.argv) > 1 and sys.argv[1] == "stop":
                try:
                    # Try to stop the Windows service if installed
                    import subprocess
                    result = subprocess.run(
                        ["sc", "query", "LogCollector"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    
                    if result.returncode == 0:
                        # Service exists, stop it
                        print("Stopping LogCollector Windows service...")
                        result = subprocess.run(
                            ["sc", "stop", "LogCollector"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False
                        )
                        
                        if result.returncode == 0:
                            print("LogCollector service stopped successfully")
                            return
                        else:
                            print(f"Failed to stop LogCollector service: {result.stderr}")
                            # Fall through to manual execution if service stop fails
                    else:
                        print("LogCollector service is not installed.")
                        # Fall through to manual PID file handling
                        
                except Exception as e:
                    print(f"Error stopping service: {e}")
                    # Fall through to manual execution
            
            # Check if we're running directly or as a service
            if len(sys.argv) == 1:
                try:
                    # Try to run as a Windows service
                    servicemanager.Initialize()
                    servicemanager.PrepareToHostSingle(WindowsService)
                    servicemanager.StartServiceCtrlDispatcher()
                    return
                except Exception as e:
                    print(f"Not running as a service: {e}")
                    # Fall through to run manually
            
            # If we reach here, we're running manually
            # Handle commands directly
            if len(sys.argv) > 1:
                command = sys.argv[1]
                
                # Get the data directory
                data_dir = get_data_dir()
                
                # Set default file paths
                default_pid_file = os.path.join(data_dir, 'service.pid')
                default_log_file = os.path.join(data_dir, 'service.log')
                
                # Parse arguments for custom paths
                pid_file = default_pid_file
                log_file = default_log_file
                
                for i in range(2, len(sys.argv)):
                    if sys.argv[i] == "--pid-file" and i+1 < len(sys.argv):
                        pid_file = sys.argv[i+1]
                    elif sys.argv[i] == "--log-file" and i+1 < len(sys.argv):
                        log_file = sys.argv[i+1]
                
                print(f"Using PID file: {pid_file}")
                print(f"Using log file: {log_file}")
                
                if command == "start":
                    # Run service manually
                    print("Starting Log Collector service in foreground mode")
                    
                    # Setup logging
                    service_logger = setup_logging(log_file)
                    service_logger.info("Starting in foreground mode")
                    
                    # Write PID file
                    try:
                        with open(pid_file, 'w') as f:
                            f.write(str(os.getpid()))
                        service_logger.info(f"Wrote PID file to {pid_file}")
                    except Exception as e:
                        service_logger.error(f"Failed to write PID file: {e}")
                        return
                    
                    # Start service
                    service = LogCollectorService(service_logger)
                    
                    # Register cleanup
                    def cleanup():
                        service.stop()
                        try:
                            if os.path.exists(pid_file):
                                os.remove(pid_file)
                                service_logger.info(f"Removed PID file {pid_file}")
                        except Exception as e:
                            service_logger.error(f"Error removing PID file: {e}")
                    
                    import atexit
                    atexit.register(cleanup)
                    
                    if service.start():
                        service_logger.info("Service started in foreground mode")
                        print("Service started (press Ctrl+C to stop)")
                        
                        # Main loop
                        try:
                            while service.is_running:
                                time.sleep(1)
                        except KeyboardInterrupt:
                            service_logger.info("Keyboard interrupt received, stopping service")
                            cleanup()
                            print("Service stopped")
                    else:
                        service_logger.error("Failed to start service")
                        print("Failed to start service")
                
                elif command == "stop":
                    # Check if service is running
                    if os.path.exists(pid_file):
                        try:
                            with open(pid_file, 'r') as f:
                                pid = int(f.read().strip())
                            
                            # Try to send a signal
                            import signal
                            try:
                                if platform.system() == 'Windows':
                                    import ctypes
                                    kernel32 = ctypes.windll.kernel32
                                    PROCESS_TERMINATE = 1
                                    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
                                    if handle:
                                        kernel32.TerminateProcess(handle, 0)
                                        kernel32.CloseHandle(handle)
                                        print(f"Service with PID {pid} terminated")
                                    else:
                                        print(f"Process with PID {pid} not found")
                                else:
                                    os.kill(pid, signal.SIGTERM)
                                    print(f"Stop signal sent to PID {pid}")
                                
                                # Remove PID file
                                os.remove(pid_file)
                                print("PID file removed")
                            except Exception as e:
                                print(f"Error terminating process: {e}")
                                # Remove stale PID file
                                if os.path.exists(pid_file):
                                    os.remove(pid_file)
                                    print("Removed stale PID file")
                        except Exception as e:
                            print(f"Error reading PID file: {e}")
                    else:
                        print("Service is not running (PID file not found)")
                
                elif command == "status":
                    # Check if service is running
                    # First check Windows service
                    try:
                        import subprocess
                        result = subprocess.run(
                            ["sc", "query", "LogCollector"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False
                        )
                        
                        if result.returncode == 0 and "RUNNING" in result.stdout:
                            print("LogCollector service is running")
                            return
                        elif result.returncode == 0 and "STOPPED" in result.stdout:
                            print("LogCollector service is installed but not running")
                            return
                    except Exception:
                        # Fall through to PID file check
                        pass
                        
                    # Check PID file as fallback
                    if os.path.exists(pid_file):
                        try:
                            with open(pid_file, 'r') as f:
                                pid = int(f.read().strip())
                            
                            # Check if process exists
                            import signal
                            try:
                                if platform.system() == 'Windows':
                                    import ctypes
                                    kernel32 = ctypes.windll.kernel32
                                    PROCESS_QUERY_INFORMATION = 0x0400
                                    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
                                    if handle:
                                        kernel32.CloseHandle(handle)
                                        print(f"Service is running (PID: {pid})")
                                    else:
                                        print("Service is not running (stale PID file)")
                                        os.remove(pid_file)
                                else:
                                    os.kill(pid, 0)  # Signal 0 tests if process exists
                                    print(f"Service is running (PID: {pid})")
                            except:
                                print("Service is not running (stale PID file)")
                                if os.path.exists(pid_file):
                                    os.remove(pid_file)
                        except Exception as e:
                            print(f"Error checking service status: {e}")
                    else:
                        print("Service is not running (PID file not found)")
                else:
                    print("Usage: python log_collector_service.py [start|stop|status|install|remove]")
            else:
                print("Usage: python log_collector_service.py [start|stop|status|install|remove]")

    except ImportError:
        def run_windows_service():
            print("Error: pywin32 package is not installed.")
            print("Install it with: pip install pywin32")
            sys.exit(1)

else:
    # Linux Daemon Implementation
    import signal
    import atexit
    
    def daemonize(pid_file):
        """Create a daemon process"""
        # Check if we're already a daemon
        if os.getppid() == 1:
            return
        
        # Create directory for PID file if it doesn't exist
        pid_dir = os.path.dirname(pid_file)
        if pid_dir and not os.path.exists(pid_dir):
            os.makedirs(pid_dir, exist_ok=True)
        
        # First fork
        try:
            pid = os.fork()
            if pid > 0:
                # Exit first parent
                sys.exit(0)
        except OSError as e:
            print(f"Error: Fork #1 failed: {e}")
            sys.exit(1)
        
        # Decouple from parent environment
        os.chdir('/')
        os.setsid()
        os.umask(0)
        
        # Second fork
        try:
            pid = os.fork()
            if pid > 0:
                # Exit from second parent
                sys.exit(0)
        except OSError as e:
            print(f"Error: Fork #2 failed: {e}")
            sys.exit(1)
        
        # Redirect standard file descriptors to /dev/null
        sys.stdout.flush()
        sys.stderr.flush()
        
        with open('/dev/null', 'r') as f:
            os.dup2(f.fileno(), sys.stdin.fileno())
        with open('/dev/null', 'a+') as f:
            os.dup2(f.fileno(), sys.stdout.fileno())
            os.dup2(f.fileno(), sys.stderr.fileno())
        
        # Write PID file
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
        
        # Register function to remove PID file on exit
        atexit.register(lambda: os.remove(pid_file) if os.path.exists(pid_file) else None)
    
    def get_pid(pid_file):
        """Get PID from file"""
        try:
            with open(pid_file, 'r') as f:
                return int(f.read().strip())
        except (IOError, ValueError):
            return None
    
    def status(pid_file, logger):
        """Check if daemon is running"""
        pid = get_pid(pid_file)
        if pid is None:
            print("Log Collector is not running")
            return False
        
        try:
            os.kill(pid, 0)  # Signal 0 tests if process exists
            print(f"Log Collector is running (PID: {pid})")
            return True
        except OSError:
            print("Log Collector is not running (stale PID file)")
            if os.path.exists(pid_file):
                os.remove(pid_file)
            return False
    
    def run_linux_daemon():
        parser = argparse.ArgumentParser(description="Log Collector Service")
        parser.add_argument("action", choices=["start", "stop", "restart", "status"],
                          help="Action to perform")
        
        # Get the data directory
        data_dir = get_data_dir()
        
        # Use data directory for default paths
        default_pid_file = os.path.join(data_dir, "service.pid")
        default_log_file = os.path.join(data_dir, "service.log")
        
        parser.add_argument("--pid-file", default=default_pid_file,
                          help="Path to PID file")
        parser.add_argument("--log-file", default=default_log_file,
                          help="Path to log file")
        
        args = parser.parse_args()
        
        # Use environment variables if set, otherwise use args
        pid_file = os.environ.get("LOG_COLLECTOR_PID_FILE", args.pid_file)
        log_file = os.environ.get("LOG_COLLECTOR_LOG_FILE", args.log_file)
        
        # Print paths for debugging
        print(f"PID file: {pid_file}")
        print(f"Log file: {log_file}")
        
        # Setup logging
        logger = setup_logging(log_file)
        logger.info(f"Using PID file: {pid_file}")
        logger.info(f"Using log file: {log_file}")
        
        # Handle requested action
        if args.action == "status":
            sys.exit(0 if status(pid_file, logger) else 1)
        
        elif args.action == "stop":
            pid = get_pid(pid_file)
            if pid is None:
                print("Log Collector is not running")
                sys.exit(0)
            
            print(f"Stopping Log Collector (PID: {pid})...")
            
            try:
                os.kill(pid, signal.SIGTERM)
                
                # Wait for process to terminate
                for _ in range(30):  # Wait up to 30 seconds
                    time.sleep(1)
                    try:
                        os.kill(pid, 0)
                    except OSError:
                        # Process has terminated
                        if os.path.exists(pid_file):
                            os.remove(pid_file)
                        print("Log Collector stopped")
                        sys.exit(0)
                
                # Force kill if it didn't terminate
                print("Forcing termination...")
                os.kill(pid, signal.SIGKILL)
                if os.path.exists(pid_file):
                    os.remove(pid_file)
                print("Log Collector stopped (forced)")
                sys.exit(0)
                
            except OSError as e:
                print(f"Error stopping Log Collector: {e}")
                sys.exit(1)
        
        elif args.action == "restart":
            # Stop if running
            pid = get_pid(pid_file)
            if pid is not None:
                try:
                    os.kill(pid, signal.SIGTERM)
                    
                    # Wait for process to terminate
                    for _ in range(30):
                        time.sleep(1)
                        try:
                            os.kill(pid, 0)
                        except OSError:
                            break
                    else:
                        # Force kill if it didn't terminate
                        os.kill(pid, signal.SIGKILL)
                    
                    if os.path.exists(pid_file):
                        os.remove(pid_file)
                    
                    print("Log Collector stopped")
                    time.sleep(2)  # Wait before restarting
                
                except OSError as e:
                    print(f"Error stopping Log Collector: {e}")
            
            # Fall through to start action
        
        if args.action in ["start", "restart"]:
            # Check if already running
            if get_pid(pid_file) is not None:
                print("Log Collector is already running")
                sys.exit(1)
            
            print("Starting Log Collector...")
            
            # Check if interactive mode was requested
            if "--interactive" in sys.argv:
                # Run in foreground mode
                print("Starting in foreground mode")
                
                # Write PID file
                try:
                    with open(pid_file, 'w') as f:
                        f.write(str(os.getpid()))
                    logger.info(f"Wrote PID file: {pid_file}")
                except Exception as e:
                    logger.error(f"Failed to write PID file: {e}")
                    sys.exit(1)
                
                # Start service
                service = LogCollectorService(logger)
                
                # Handle signals
                def cleanup(signum, frame):
                    logger.info(f"Received signal {signum}, stopping")
                    service.stop()
                    try:
                        if os.path.exists(pid_file):
                            os.remove(pid_file)
                    except:
                        pass
                    sys.exit(0)
                
                signal.signal(signal.SIGTERM, cleanup)
                signal.signal(signal.SIGINT, cleanup)
                
                # Start the service
                if service.start():
                    logger.info("Service started")
                    print("Service running in foreground (press Ctrl+C to stop)")
                    
                    # Main loop
                    try:
                        while service.is_running:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        cleanup(signal.SIGINT, None)
                else:
                    logger.error("Failed to start service")
                    print("Failed to start service")
                    sys.exit(1)
            else:
                # Daemonize
                daemonize(pid_file)
                
                # Create and start the service
                service = LogCollectorService(logger)
                
                # Set up signal handlers
                def sigterm_handler(signum, frame):
                    service.stop()
                    sys.exit(0)
                
                signal.signal(signal.SIGTERM, sigterm_handler)
                signal.signal(signal.SIGINT, sigterm_handler)
                
                # Start the service
                if not service.start():
                    logger.error("Failed to start Log Collector service")
                    sys.exit(1)
                
                # Main service loop
                try:
                    while service.is_running:
                        time.sleep(60)  # Sleep to avoid busy waiting
                except Exception as e:
                    logger.error(f"Error in main loop: {e}", exc_info=True)
                    service.stop()
                    sys.exit(1)
                
                sys.exit(0)

# Main function to run the appropriate platform implementation
def main():
    """Main entry point for the cross-platform service"""
    # Handle version and help commands before platform detection
    if len(sys.argv) > 1 and sys.argv[1] in ['--version', '-v']:
        from log_collector.utils import get_version
        print(f"Log Collector version {get_version()}")
        return 0
    
    # Get the data directory 
    data_dir = get_data_dir()
    
    # Default file paths in data directory
    default_pid_file = os.path.join(data_dir, "service.pid")
    default_log_file = os.path.join(data_dir, "service.log")
    
    # Print default paths for debugging
    print(f"Default PID file: {default_pid_file}")
    print(f"Default log file: {default_log_file}")
    
    # Set environment variables for child processes
    if "LOG_COLLECTOR_PID_FILE" not in os.environ:
        os.environ["LOG_COLLECTOR_PID_FILE"] = default_pid_file
    
    if "LOG_COLLECTOR_LOG_FILE" not in os.environ:
        os.environ["LOG_COLLECTOR_LOG_FILE"] = default_log_file
    
    # Detect platform and run appropriate implementation
    if platform.system() == 'Windows':
        # Windows Service Implementation
        run_windows_service()
    else:
        # Linux/Unix Daemon Implementation
        run_linux_daemon()
        
    return 0

# Entry point when run directly
if __name__ == "__main__":
    sys.exit(main())
