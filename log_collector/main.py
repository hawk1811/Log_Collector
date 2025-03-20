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
            # On Windows, we use a different approach
            # We'll use the pythonw.exe interpreter if available 
            # or create a detached process
            
            # Check if we're already detached
            if not os.environ.get('LOG_COLLECTOR_DETACHED'):
                # First, find pythonw.exe (windowless Python)
                python_path = sys.executable
                pythonw_path = python_path.replace('python.exe', 'pythonw.exe')
                
                if not os.path.exists(pythonw_path):
                    # Fall back to regular python with CREATE_NO_WINDOW
                    pythonw_path = python_path
                
                # Build the command line, adding a flag to prevent infinite recursion
                script_path = os.path.abspath(sys.argv[0])
                args = sys.argv[1:]  # Original args
                
                # Remove --daemon from args to prevent infinite loop
                if '--daemon' in args:
                    args.remove('--daemon')
                
                # Add flag to indicate we're already detached
                os.environ['LOG_COLLECTOR_DETACHED'] = '1'
                
                # Create temporary batch file to run the command
                # This approach helps with detaching completely from command prompt
                with tempfile.NamedTemporaryFile(suffix='.bat', delete=False) as batch_file:
                    batch_path = batch_file.name
                    
                    # Write batch commands
                    batch_commands = [
                        '@echo off\n',
                        'setlocal\n',
                        f'set LOG_COLLECTOR_DETACHED=1\n',
                        f'start "" /B "{pythonw_path}" "{script_path}" {" ".join(args)}\n'
                    ]
                    batch_file.write(''.join(batch_commands).encode('utf-8'))
                
                # Execute the batch file and exit
                os.system(f'start "" /B "{batch_path}" && ping -n 2 127.0.0.1 > nul && del "{batch_path}"')
                sys.exit(0)
            
            # We're already in the detached process, continue with execution
            # Write PID file if specified
            if pid_file:
                with open(pid_file, 'w') as f:
                    f.write(str(os.getpid()))
                
                # Remove PID file on exit
                atexit.register(lambda: os.remove(pid_file) if os.path.exists(pid_file) else None)
                
            logger.info(f"Successfully detached process. PID: {os.getpid()}")
            
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
