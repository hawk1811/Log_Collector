"""
Main entry point for Log Collector application.
"""
import sys
import signal
import argparse
import threading
import os
import atexit
import tempfile
from pathlib import Path

from log_collector.config import logger
from log_collector.source_manager import SourceManager
from log_collector.processor import ProcessorManager
from log_collector.listener import LogListener
from log_collector.health_check import HealthCheck
from log_collector.aggregation_manager import AggregationManager
from log_collector.auth import AuthManager
from log_collector import CLI
from log_collector.utils import get_version
from log_collector.filter_manager import FilterManager
from log_collector.updater import restart_application


def signal_handler(signum, frame):
    """Handle termination signals."""
    logger.info("Received termination signal, shutting down...")
    sys.exit(0)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Log Collector")
    parser.add_argument(
        "--version", 
        action="store_true", 
        help="Show version information and exit"
    )
    parser.add_argument(
        "--no-interactive", 
        action="store_true", 
        help="Run in non-interactive mode (for service deployment)"
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as a background daemon (detached from terminal)"
    )
    parser.add_argument(
        "--data-dir",
        help="Path to data directory",
        default=None
    )
    parser.add_argument(
        "--log-dir",
        help="Path to log directory",
        default=None
    )
    parser.add_argument(
        "--pid-file",
        help="Path to PID file when running as daemon",
        default=None
    )
    
    return parser.parse_args()

def daemonize(pid_file=None):
    """Detach from the terminal and run as a daemon process.
    
    Args:
        pid_file: Optional path to write PID file
    """
    # Platform-specific daemon implementation
    if os.name == 'posix':  # Unix/Linux/macOS
        try:
            # First fork
            pid = os.fork()
            if pid > 0:
                # Exit first parent
                sys.exit(0)
        except OSError as e:
            logger.error(f"Fork #1 failed: {e}")
            sys.exit(1)
            
        # Decouple from parent environment
        os.chdir('/')
        os.setsid()
        os.umask(0)
            
        try:
            # Second fork
            pid = os.fork()
            if pid > 0:
                # Exit from second parent
                sys.exit(0)
        except OSError as e:
            logger.error(f"Fork #2 failed: {e}")
            sys.exit(1)
            
        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        
        si = open(os.devnull, 'r')
        so = open(os.devnull, 'a+')
        se = open(os.devnull, 'a+')
        
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
        
        # Write PID file if specified
        if pid_file:
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))
            
            # Remove PID file on exit
            atexit.register(lambda: os.remove(pid_file) if os.path.exists(pid_file) else None)
            
        logger.info(f"Successfully daemonized process. PID: {os.getpid()}")
            
    elif os.name == 'nt':  # Windows
        try:
            # On Windows, we use the subprocess module to create a detached process
            # Check if we're already detached
            if not os.environ.get('LOG_COLLECTOR_DETACHED'):
                import subprocess
                
                # Get the current executable path
                python_exe = sys.executable
                
                # Get the main script path
                if getattr(sys, 'frozen', False):
                    # Running as compiled executable
                    script_path = sys.executable
                    args = sys.argv[1:]
                else:
                    # Running as script
                    script_path = sys.argv[0]
                    args = sys.argv[1:]
                
                # Remove --daemon from args to prevent infinite loop
                if '--daemon' in args:
                    args.remove('--daemon')
                
                # Add the --no-interactive flag if not already present
                if '--no-interactive' not in args:
                    args.append('--no-interactive')
                
                # Create a complete command list
                if script_path.endswith('.py'):
                    # If it's a Python script, use the Python executable
                    cmd = [python_exe, script_path] + args
                else:
                    # If it's an executable, call it directly
                    cmd = [script_path] + args
                
                # Set environment variables for the child process
                env = os.environ.copy()
                env['LOG_COLLECTOR_DETACHED'] = '1'
                
                # Create a detached process with no window
                DETACHED_PROCESS = 0x00000008
                CREATE_NO_WINDOW = 0x08000000
                
                logger.info(f"Launching detached process with command: {' '.join(cmd)}")
                
                # Start the detached process
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
                    close_fds=True,
                    shell=False
                )
                
                # Log the PID for reference
                logger.info(f"Detached process started with PID: {process.pid}")
                
                # Write PID file if specified
                if pid_file:
                    with open(pid_file, 'w') as f:
                        f.write(str(process.pid))
                
                # Exit the parent
                sys.exit(0)
            
            # If we're here, we're the child process
            logger.info(f"Running as detached process. PID: {os.getpid()}")
            
            # Write PID file if specified and not already written by the parent
            if pid_file and not os.path.exists(pid_file):
                with open(pid_file, 'w') as f:
                    f.write(str(os.getpid()))
                
                # Remove PID file on exit
                atexit.register(lambda: os.remove(pid_file) if os.path.exists(pid_file) else None)
            
        except Exception as e:
            logger.error(f"Failed to daemonize on Windows: {e}")
            sys.exit(1)
    else:
        logger.error(f"Unsupported operating system: {os.name}")
        sys.exit(1)

def main():
    """Main entry point."""
    # Parse command line arguments
    args = parse_args()
    
    # Show version and exit if requested
    if args.version:
        print(f"Log Collector version {get_version()}")
        return 0
    
    # Daemonize if requested
    if args.daemon:
        logger.info("Daemonizing process...")
        daemonize(args.pid_file)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # TODO: Handle custom data and log directories
    
    try:
        # Initialize components
        logger.info("Initializing Log Collector...")
        auth_manager = AuthManager()
        source_manager = SourceManager()
        aggregation_manager = AggregationManager()
        filter_manager = FilterManager()  
        
        # Initialize processor manager with the aggregation manager for automatic template creation
        processor_manager = ProcessorManager(source_manager, aggregation_manager, filter_manager)
        listener_manager = LogListener(source_manager, processor_manager)
        health_check = HealthCheck(source_manager, processor_manager)
        
        # Start CLI in interactive mode
        if not args.no_interactive:
            cli = CLI(source_manager, processor_manager, listener_manager, health_check, aggregation_manager, auth_manager, filter_manager)
            cli.start()
        else:
            # Non-interactive mode for service deployment
            logger.info("Running in non-interactive mode...")
            
            # Start all services
            processor_manager.start()
            listener_manager.start()
            
            # Load health check configuration and start if available
            if hasattr(health_check, 'config') and health_check.config is not None:
                if health_check.start():
                    logger.info("Health check monitoring started automatically")
                else:
                    logger.warning("Health check is configured but failed to start")
            
            # Keep the main thread running
            main_thread = threading.current_thread()
            
            # Log the PID for reference
            logger.info(f"Log Collector running with PID: {os.getpid()}")
            
            # Write PID to file for service management
            pid_file = os.environ.get('LOG_COLLECTOR_PID_FILE')
            if pid_file:
                try:
                    with open(pid_file, 'w') as f:
                        f.write(str(os.getpid()))
                    # Register cleanup on exit
                    atexit.register(lambda: os.remove(pid_file) if os.path.exists(pid_file) else None)
                    logger.info(f"PID written to file: {pid_file}")
                except Exception as e:
                    logger.error(f"Error writing PID file: {e}")
            
            # Instead of joining threads, use an infinite loop with sleep
            # This approach is more reliable for daemon processes
            try:
                while True:
                    # Sleep to avoid CPU usage
                    # Use a reasonable interval that allows for clean shutdown
                    threading.Event().wait(60)  # Wait for 60 seconds
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down...")
            except SystemExit:
                logger.info("System exit requested, shutting down...")
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                
            # Clean shutdown
            logger.info("Shutting down...")
            if health_check.running:
                health_check.stop()
            processor_manager.stop()
            listener_manager.stop()
            logger.info("Shutdown complete")
                    
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
