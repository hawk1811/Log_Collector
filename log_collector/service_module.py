"""
Service module for Log Collector.
Handles service implementation for Windows and Linux platforms.
"""
import os
import sys
import time
import signal
import platform
import logging
from pathlib import Path

# Import Log Collector components
from log_collector.source_manager import SourceManager
from log_collector.processor import ProcessorManager
from log_collector.listener import LogListener
from log_collector.health_check import HealthCheck
from log_collector.aggregation_manager import AggregationManager
from log_collector.filter_manager import FilterManager
from log_collector.config import (
    logger,
    DATA_DIR,
)

# Constants
DEFAULT_PID_FILE = DATA_DIR / "service.pid"
DEFAULT_LOG_FILE = DATA_DIR / "service.log"

def setup_service_logging(log_file):
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

# Windows Service Implementation
if platform.system() == 'Windows':
    try:
        import win32service
        import win32serviceutil
        import win32event
        import servicemanager
        import socket

        class WindowsService(win32serviceutil.ServiceFramework):
            _svc_name_ = "LogCollectorService"  # Service name
            _svc_display_name_ = "Log Collector Service"  # Display name shown in services.msc
            _svc_description_ = "High-performance log collection and processing system"
            
            def __init__(self, args):
                win32serviceutil.ServiceFramework.__init__(self, args)
                self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
                socket.setdefaulttimeout(60)
                
                # Setup PID and log files
                self.pid_file = DEFAULT_PID_FILE
                self.log_file = DEFAULT_LOG_FILE
                
                # Setup logging
                self.logger = setup_service_logging(self.log_file)
                self.logger.info(f"Windows service initialized with log file: {self.log_file}")
                self.logger.info(f"Using PID file: {self.pid_file}")
                
                # Write PID file
                try:
                    with open(self.pid_file, 'w') as f:
                        f.write(str(os.getpid()))
                    self.logger.info(f"Wrote PID file to {self.pid_file}")
                    
                    # Register cleanup function
                    import atexit
                    atexit.register(lambda: os.remove(self.pid_file) if os.path.exists(self.pid_file) else None)
                    
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
                    if os.path.exists(self.pid_file):
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
                        
        def register_windows_service():
            """Register the Log Collector as a Windows service"""
            # We can add custom options for installation
            if len(sys.argv) > 2 and sys.argv[2] == "--startup":
                # Allows specifying startup type: auto, manual, disabled
                win32serviceutil.HandleCommandLine(WindowsService)
            else:
                # Set default startup mode to auto
                sys.argv.extend(["--startup", "auto"])
                win32serviceutil.HandleCommandLine(WindowsService)
            
        def start_windows_service(interactive=False, pid_file=DEFAULT_PID_FILE, log_file=DEFAULT_LOG_FILE):
            """Start the Log Collector service on Windows"""
            if interactive:
                # Run in foreground mode
                service_logger = setup_service_logging(log_file)
                service_logger.info("Starting in foreground mode")
                
                # Write PID file
                try:
                    with open(pid_file, 'w') as f:
                        f.write(str(os.getpid()))
                    service_logger.info(f"Wrote PID file to {pid_file}")
                except Exception as e:
                    service_logger.error(f"Failed to write PID file: {e}")
                    return False
                
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
                        return True
                    return True
                else:
                    service_logger.error("Failed to start service")
                    print("Failed to start service")
                    return False
            else:
                # Try to run as a Windows service
                try:
                    # First check if the service is installed
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
                            return True
                        else:
                            print(f"Failed to start LogCollector service: {result.stderr}")
                            # Fall through to manual execution
                    else:
                        # Service not installed, write a marker to the PID file
                        try:
                            os.makedirs(os.path.dirname(pid_file), exist_ok=True)
                            with open(pid_file, 'w') as f:
                                f.write("starting")
                        except Exception:
                            pass
                        
                        # Start in foreground mode
                        return start_windows_service(True, pid_file, log_file)
                        
                except Exception as e:
                    print(f"Error starting Windows service: {e}")
                    # Fall through to manual execution
                    return start_windows_service(True, pid_file, log_file)
                    
            return False
        
        def stop_windows_service(pid_file=DEFAULT_PID_FILE):
            """Stop the Log Collector service on Windows"""
            # First try to stop using Windows service commands
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
                    # Service exists and is running, stop it
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
                        return True
                    else:
                        print(f"Failed to stop LogCollector service: {result.stderr}")
                        # Fall through to process termination
                elif result.returncode == 0:
                    # Service exists but is not running
                    print("LogCollector service is not running")
                    return True
            except Exception:
                # Fall through to process termination
                pass
                
            # Fall back to process termination using PID file
            if os.path.exists(pid_file):
                try:
                    with open(pid_file, 'r') as f:
                        content = f.read().strip()
                        
                    if content == "starting":
                        print("Service is still starting up, cannot stop yet")
                        return False
                        
                    pid = int(content)
                    
                    # Try to terminate the process
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    PROCESS_TERMINATE = 1
                    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
                    if handle:
                        result = kernel32.TerminateProcess(handle, 0)
                        kernel32.CloseHandle(handle)
                        
                        if result:
                            print(f"Process with PID {pid} terminated")
                            # Remove PID file
                            os.remove(pid_file)
                            return True
                        else:
                            print(f"Failed to terminate process with PID {pid}")
                            return False
                    else:
                        print(f"Process with PID {pid} not found or cannot be accessed")
                        # Remove stale PID file
                        os.remove(pid_file)
                        return True
                except Exception as e:
                    print(f"Error stopping service: {e}")
                    # Try to remove stale PID file
                    try:
                        os.remove(pid_file)
                    except:
                        pass
                    return False
            else:
                print("Service is not running (PID file not found)")
                return True
    
    except ImportError:
        # Fallback if pywin32 is not available
        def register_windows_service():
            print("Error: pywin32 package is not installed.")
            print("Install it with: pip install pywin32")
            return False
            
        def start_windows_service(interactive=False, pid_file=DEFAULT_PID_FILE, log_file=DEFAULT_LOG_FILE):
            print("Error: pywin32 package is not installed.")
            print("Install it with: pip install pywin32")
            return False
            
        def stop_windows_service(pid_file=DEFAULT_PID_FILE):
            print("Error: pywin32 package is not installed.")
            print("Install it with: pip install pywin32")
            return False

# Linux Implementation
def daemonize(pid_file=DEFAULT_PID_FILE):
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
    import atexit
    atexit.register(lambda: os.remove(pid_file) if os.path.exists(pid_file) else None)

def get_pid_from_file(pid_file=DEFAULT_PID_FILE):
    """Get PID from file"""
    try:
        with open(pid_file, 'r') as f:
            content = f.read().strip()
            if content == "starting":
                return None
            return int(content)
    except (IOError, ValueError):
        return None

def is_process_running(pid):
    """Check if a process is running by PID"""
    if pid is None:
        return False
        
    try:
        os.kill(pid, 0)  # Signal 0 tests if process exists
        return True
    except OSError:
        return False

def check_service_status(pid_file=DEFAULT_PID_FILE):
    """Check if service is running"""
    pid = get_pid_from_file(pid_file)
    if pid is None:
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    if f.read().strip() == "starting":
                        print("Service is starting up")
                        return None
            except:
                pass
        print("Service is not running")
        return False
    
    if is_process_running(pid):
        print(f"Service is running (PID: {pid})")
        return True
    else:
        print("Service is not running (stale PID file)")
        if os.path.exists(pid_file):
            os.remove(pid_file)
        return False

def start_linux_service(interactive=False, pid_file=DEFAULT_PID_FILE, log_file=DEFAULT_LOG_FILE):
    """Start the Log Collector service on Linux"""
    # Check if already running
    status = check_service_status(pid_file)
    if status is True:
        print("Service is already running")
        return True
    
    # Write starting marker to PID file
    try:
        os.makedirs(os.path.dirname(pid_file), exist_ok=True)
        with open(pid_file, 'w') as f:
            f.write("starting")
    except Exception as e:
        print(f"Error writing PID file: {e}")
        
    if interactive:
        # Run in foreground mode
        service_logger = setup_service_logging(log_file)
        service_logger.info("Starting in foreground mode")
        
        # Update PID file with actual PID
        try:
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))
            service_logger.info(f"Wrote PID file to {pid_file}")
        except Exception as e:
            service_logger.error(f"Failed to write PID file: {e}")
            return False
        
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
        
        # Handle signals
        def signal_handler(signum, frame):
            service_logger.info(f"Received signal {signum}, stopping service")
            cleanup()
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
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
                return True
                
            return True
        else:
            service_logger.error("Failed to start service")
            print("Failed to start service")
            return False
    else:
        # Daemonize
        try:
            daemonize(pid_file)
            
            # Setup logger
            service_logger = setup_service_logging(log_file)
            service_logger.info("Starting as daemon")
            
            # Create service instance
            service = LogCollectorService(service_logger)
            
            # Set up signal handlers
            def sigterm_handler(signum, frame):
                service.stop()
                sys.exit(0)
            
            signal.signal(signal.SIGTERM, sigterm_handler)
            signal.signal(signal.SIGINT, sigterm_handler)
            
            # Start the service
            if not service.start():
                service_logger.error("Failed to start Log Collector service")
                sys.exit(1)
            
            # Main service loop
            try:
                while service.is_running:
                    time.sleep(60)  # Sleep to avoid busy waiting
            except Exception as e:
                service_logger.error(f"Error in main loop: {e}", exc_info=True)
                service.stop()
                sys.exit(1)
                
            return True
        except Exception as e:
            print(f"Error starting daemon: {e}")
            return False

def stop_linux_service(pid_file=DEFAULT_PID_FILE):
    """Stop the Log Collector service on Linux"""
    pid = get_pid_from_file(pid_file)
    if pid is None:
        print("Service is not running")
        # Clean up any stale PID file
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    if f.read().strip() == "starting":
                        print("Service is still starting, cannot stop yet")
                        return False
            except:
                pass
            os.remove(pid_file)
        return True
    
    print(f"Stopping service (PID: {pid})...")
    
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
                print("Service stopped")
                return True
        
        # Force kill if it didn't terminate
        print("Forcing termination...")
        os.kill(pid, signal.SIGKILL)
        if os.path.exists(pid_file):
            os.remove(pid_file)
        print("Service stopped (forced)")
        return True
        
    except OSError as e:
        print(f"Error stopping service: {e}")
        # Try to clean up PID file anyway
        if os.path.exists(pid_file):
            os.remove(pid_file)
        return False

# Cross-platform functions
def start_service(interactive=False, pid_file=DEFAULT_PID_FILE, log_file=DEFAULT_LOG_FILE):
    """Start the Log Collector service (cross-platform)"""
    # Ensure directories exist
    os.makedirs(os.path.dirname(pid_file), exist_ok=True)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # For non-interactive mode, always use subprocess to start in background
    if not interactive:
        try:
            # Write starting marker to PID file
            with open(pid_file, 'w') as f:
                f.write("starting")
                
            # Prepare command to start the service
            # Instead of using "python -m log_collector", use the main script directly
            # Get the path to the main.py script
            main_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "log_collector", "main.py")
            
            cmd = [sys.executable, main_script, "--service", "start", "--interactive",
                   "--pid-file", str(pid_file), "--log-file", str(log_file)]
            
            # Start the process
            if platform.system() == 'Windows':
                import subprocess
                
                # Use CREATE_NO_WINDOW to hide the console window
                CREATE_NO_WINDOW = 0x08000000
                
                # Use DETACHED_PROCESS to detach from parent
                DETACHED_PROCESS = 0x00000008
                
                process = subprocess.Popen(
                    cmd,
                    creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
                    close_fds=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            else:
                # For Unix systems
                import subprocess
                
                # Start detached process
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True  # Detaches from parent session
                )
                
            # Give the process a moment to start
            time.sleep(2)
            
            # Check if the process is running
            if process.poll() is None:
                # Still running, which is good
                return True
            else:
                # Process exited too quickly, there might be an error
                stdout, stderr = process.communicate()
                print(f"Error starting service: {stderr.decode('utf-8', errors='ignore')}")
                return False
                
        except Exception as e:
            print(f"Error launching service process: {e}")
            # Clean up PID file
            if os.path.exists(pid_file):
                os.remove(pid_file)
            return False
    
    # Interactive mode (used by the subprocess created above)
    if platform.system() == 'Windows':
        return start_windows_service(True, pid_file, log_file)
    else:
        return start_linux_service(True, pid_file, log_file)

def stop_service(pid_file=DEFAULT_PID_FILE):
    """Stop the Log Collector service (cross-platform)"""
    if platform.system() == 'Windows':
        return stop_windows_service(pid_file)
    else:
        return stop_linux_service(pid_file)

def restart_service(pid_file=DEFAULT_PID_FILE, log_file=DEFAULT_LOG_FILE):
    """Restart the Log Collector service (cross-platform)"""
    # Stop the service
    stop_service(pid_file)
    
    # Give it a moment to fully stop
    time.sleep(2)
    
    # Start the service
    return start_service(False, pid_file, log_file)

def get_service_status(pid_file=DEFAULT_PID_FILE):
    """Get service status (cross-platform)"""
    if platform.system() == 'Windows':
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
                return True
            elif result.returncode == 0 and "STOPPED" in result.stdout:
                print("LogCollector service is installed but not running")
                return False
        except Exception:
            # Fall through to PID file check
            pass
    
    # Use PID file for Linux or as fallback for Windows
    pid = get_pid_from_file(pid_file)
    if pid is None:
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    if f.read().strip() == "starting":
                        print("Service is starting up")
                        return None
            except:
                pass
        print("Service is not running")
        return False
    
    if is_process_running(pid):
        print(f"Service is running (PID: {pid})")
        return True
    else:
        print("Service is not running (stale PID file)")
        if os.path.exists(pid_file):
            os.remove(pid_file)
        return False

def handle_service_command(command, pid_file=DEFAULT_PID_FILE, log_file=DEFAULT_LOG_FILE, interactive=False):
    """Handle service commands"""
    if command == "start":
        return start_service(interactive, pid_file, log_file)
    elif command == "stop":
        return stop_service(pid_file)
    elif command == "restart":
        return restart_service(pid_file, log_file)
    elif command == "status":
        return get_service_status(pid_file)
    elif command == "install" and platform.system() == 'Windows':
        register_windows_service()
        return True
    else:
        print(f"Unknown service command: {command}")
        return False
