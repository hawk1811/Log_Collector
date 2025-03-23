"""
Main entry point for Log Collector application.
"""
import sys
import signal
import argparse
import threading
import os
import atexit
import platform
from pathlib import Path

from log_collector.config import logger
from log_collector.app_context import get_app_context
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
from log_collector.service_module import handle_service_command

# Get app context
app_context = get_app_context()

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
        default=str(app_context.pid_file)
    )
    parser.add_argument(
        "--log-file",
        help="Path to service log file",
        default=str(app_context.log_file)
    )
    
    # Add service command group
    service_group = parser.add_argument_group("Service commands")
    service_group.add_argument(
        "--service",
        choices=["start", "stop", "restart", "status", "install"],
        help="Manage the Log Collector service"
    )
    service_group.add_argument(
        "--interactive",
        action="store_true",
        help="Run service in interactive/foreground mode"
    )
    
    return parser.parse_args()

def main():
    """Main entry point."""
    # Parse command line arguments
    args = parse_args()
    
    # Show version and exit if requested
    if args.version:
        print(f"Log Collector version {get_version()}")
        return 0
    
    # If a service command was specified, handle it and exit
    if args.service:
        pid_file = Path(args.pid_file)
        log_file = Path(args.log_file)
        
        # Special handling for Windows service installation
        if args.service == "install" and platform.system() == "Windows":
            # Import and use the service_module directly
            from log_collector.service_module import register_windows_service
            result = register_windows_service()
            return 0 if result else 1
        
        # Handle other service commands
        from log_collector.service_module import handle_service_command
        result = handle_service_command(args.service, pid_file, log_file, args.interactive)
        return 0 if result else 1
    
    # Daemonize if requested
    if args.daemon:
        logger.info("Daemonizing process...")
        from log_collector.service_module import daemonize
        daemonize(args.pid_file)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Handle custom data and log directories if specified
    if args.data_dir:
        # We can't modify app_context directly, so we'll log this but won't use it
        logger.warning("Custom data directory specified but not implemented in this version")
    
    if args.log_dir:
        # We can't modify app_context directly, so we'll log this but won't use it
        logger.warning("Custom log directory specified but not implemented in this version")
    
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
            pid_file = args.pid_file
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
            if hasattr(health_check, 'running') and health_check.running:
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
