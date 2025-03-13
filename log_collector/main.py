"""
Main entry point for Log Collector application.
"""
import sys
import signal
import argparse
import threading
from pathlib import Path

from log_collector.config import logger, DATA_DIR, LOG_DIR
from log_collector.source_manager import SourceManager
from log_collector.processor import ProcessorManager
from log_collector.listener import LogListener
from log_collector.health_check import HealthCheck
from log_collector.cli import CLI
from log_collector.auth import AuthManager
from log_collector.utils import get_version, create_dir_if_not_exists

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
        "--reset-password",
        help="Reset admin password and exit",
        action="store_true"
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
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Handle custom data and log directories
    if args.data_dir:
        global DATA_DIR
        DATA_DIR = Path(args.data_dir)
        create_dir_if_not_exists(DATA_DIR)
    
    if args.log_dir:
        global LOG_DIR
        LOG_DIR = Path(args.log_dir)
        create_dir_if_not_exists(LOG_DIR)
    
    # Reset admin password if requested
    if args.reset_password:
        auth_manager = AuthManager()
        success, message = auth_manager.reset_password("admin")
        if success:
            print(f"Admin password reset to default: {message}")
        else:
            print(f"Error resetting admin password: {message}")
        return 0
    
    try:
        # Initialize components
        logger.info("Initializing Log Collector...")
        source_manager = SourceManager()
        processor_manager = ProcessorManager(source_manager)
        listener_manager = LogListener(source_manager, processor_manager)
        health_check = HealthCheck(source_manager, processor_manager)
        
        # Start CLI in interactive mode
        if not args.no_interactive:
            cli = CLI(source_manager, processor_manager, listener_manager, health_check)
            cli.start()
        else:
            # Non-interactive mode for service deployment
            logger.info("Running in non-interactive mode...")
            
            # Start all services
            processor_manager.start()
            listener_manager.start()
            
            # TODO: Load health check config from a file and start if configured
            
            # Keep the main thread running
            main_thread = threading.current_thread()
            for thread in threading.enumerate():
                if thread is not main_thread:
                    thread.join()
                    
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
