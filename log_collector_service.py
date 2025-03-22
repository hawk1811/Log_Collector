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
    
    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    service_logger.addHandler(handler)
    
    return service_logger

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
                
                # Get log file path from environment if available, otherwise use default
                if "LOG_COLLECTOR_LOG_FILE" in os.environ:
                    log_file = os.environ["LOG_COLLECTOR_LOG_FILE"]
                else:
                    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'service.log')
                
                # Ensure log directory exists
                log_dir = os.path.dirname(log_file)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir, exist_ok=True)
                
                self.logger = setup_logging(log_file)
                self.logger.info(f"Windows service initialized with log file: {log_file}")
                
                # Register PID file location for cleanup
                if "LOG_COLLECTOR_PID_FILE" in os.environ:
                    pid_file = os.environ["LOG_COLLECTOR_PID_FILE"]
                else:
                    # Default PID file location
                    pid_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'service.pid')
                    
                # Ensure PID directory exists
                pid_dir = os.path.dirname(pid_file)
                if pid_dir and not os.path.exists(pid_dir):
                    os.makedirs(pid_dir, exist_ok=True)
                    
                # Write PID file
                try:
                    with open(pid_file, 'w') as f:
                        f.write(str(os.getpid()))
                    self.logger.info(f"Wrote PID file to {pid_file}")
                    
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
            if len(sys.argv) == 1:
                servicemanager.Initialize()
                servicemanager.PrepareToHostSingle(WindowsService)
                servicemanager.StartServiceCtrlDispatcher()
            else:
                win32serviceutil.HandleCommandLine(WindowsService)

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
        parser.add_argument("--pid-file", default="/var/run/log_collector.pid",
                          help="Path to PID file")
        parser.add_argument("--log-file", default="/var/log/log_collector/service.log",
                          help="Path to log file")
        
        args = parser.parse_args()
        
        # Setup logging
        logger = setup_logging(args.log_file)
        
        # Handle requested action
        if args.action == "status":
            sys.exit(0 if status(args.pid_file, logger) else 1)
        
        elif args.action == "stop":
            pid = get_pid(args.pid_file)
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
                        if os.path.exists(args.pid_file):
                            os.remove(args.pid_file)
                        print("Log Collector stopped")
                        sys.exit(0)
                
                # Force kill if it didn't terminate
                print("Forcing termination...")
                os.kill(pid, signal.SIGKILL)
                if os.path.exists(args.pid_file):
                    os.remove(args.pid_file)
                print("Log Collector stopped (forced)")
                sys.exit(0)
                
            except OSError as e:
                print(f"Error stopping Log Collector: {e}")
                sys.exit(1)
        
        elif args.action == "restart":
            # Stop if running
            pid = get_pid(args.pid_file)
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
                    
                    if os.path.exists(args.pid_file):
                        os.remove(args.pid_file)
                    
                    print("Log Collector stopped")
                    time.sleep(2)  # Wait before restarting
                
                except OSError as e:
                    print(f"Error stopping Log Collector: {e}")
            
            # Fall through to start action
        
        if args.action in ["start", "restart"]:
            # Check if already running
            if get_pid(args.pid_file) is not None:
                print("Log Collector is already running")
                sys.exit(1)
            
            print("Starting Log Collector...")
            
            # Daemonize the process
            daemonize(args.pid_file)
            
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
            
            # Pass the PID file location to the child process
            os.environ['LOG_COLLECTOR_PID_FILE'] = args.pid_file
            
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
    
    # Detect platform and run appropriate implementation
    if platform.system() == 'Windows':
        # Windows Service Implementation
        run_windows_service()
    else:
        # Linux/Unix Daemon Implementation
        run_linux_daemon()
        
    return 0

# Main entry point
if __name__ == "__main__":
    sys.exit(main())
