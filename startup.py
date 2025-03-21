#!/usr/bin/env python3
"""
Startup script for Log Collector application.
Provides standalone execution capabilities for offline deployments.
"""
import os
import sys
import argparse
import subprocess
import logging
import platform
import time
from pathlib import Path

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("LogCollector-Startup")

def setup_environment():
    """Set up environment for the application."""
    # Get script location to determine application root
    if getattr(sys, 'frozen', False):
        # Running as a bundled executable
        app_path = Path(os.path.dirname(sys.executable))
    else:
        # Running as a script
        app_path = Path(os.path.dirname(os.path.abspath(__file__)))
    
    # Create required directories
    data_dir = app_path / "data"
    logs_dir = app_path / "logs"
    
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    
    logger.info(f"Application path: {app_path}")
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Logs directory: {logs_dir}")
    
    # Add application directory to Python path
    if app_path not in sys.path:
        sys.path.insert(0, str(app_path))
    
    return app_path

def run_as_cli():
    """Run the application in CLI mode."""
    logger.info("Starting Log Collector in CLI mode")
    
    try:
        # Import the CLI entry point
        from log_collector import CLI
        from log_collector.source_manager import SourceManager
        from log_collector.processor import ProcessorManager
        from log_collector.listener import LogListener
        from log_collector.health_check import HealthCheck
        from log_collector.aggregation_manager import AggregationManager
        from log_collector.filter_manager import FilterManager
        from log_collector.auth import AuthManager
        
        # Initialize components
        auth_manager = AuthManager()
        source_manager = SourceManager()
        aggregation_manager = AggregationManager()
        filter_manager = FilterManager()  
        processor_manager = ProcessorManager(source_manager, aggregation_manager, filter_manager)
        listener_manager = LogListener(source_manager, processor_manager)
        health_check = HealthCheck(source_manager, processor_manager)
        
        # Start CLI
        cli = CLI(source_manager, processor_manager, listener_manager, health_check, 
                 aggregation_manager, auth_manager, filter_manager)
        cli.start()
        
    except Exception as e:
        logger.error(f"Error starting CLI: {e}", exc_info=True)
        return 1
    
    return 0

def run_as_service(args):
    """Run the application as a service."""
    logger.info("Starting Log Collector service mode")
    
    try:
        # Determine the path to log_collector_service.py
        if getattr(sys, 'frozen', False):
            # Bundled application
            app_dir = os.path.dirname(sys.executable)
            service_script = os.path.join(app_dir, "log_collector_service.py")
        else:
            # Running as script
            app_dir = os.path.dirname(os.path.abspath(__file__))
            service_script = os.path.join(app_dir, "log_collector_service.py")
        
        if not os.path.exists(service_script):
            logger.error(f"Service script not found at {service_script}")
            return 1
        
        # Special handling for Windows service
        if platform.system() == 'Windows':
            # Check if the first service argument is a Windows service command
            win_commands = ["install", "update", "remove", "start", "stop", "restart", "status"]
            
            if args.service_command and args.service_command in win_commands:
                # Import win32 modules directly
                try:
                    # Execute win32serviceutil.HandleCommandLine
                    cmd = [sys.executable, service_script, args.service_command]
                    if args.service_args:
                        cmd.extend(args.service_args)
                    
                    logger.info(f"Running Windows service command: {' '.join(cmd)}")
                    subprocess.run(cmd, check=True)
                    return 0
                except Exception as e:
                    logger.error(f"Error running Windows service command: {e}")
                    return 1
        
        # For Linux or other Windows commands, pass through to service script
        cmd = [sys.executable, service_script]
        if args.service_command:
            cmd.append(args.service_command)
        if args.service_args:
            cmd.extend(args.service_args)
        
        logger.info(f"Executing service command: {' '.join(cmd)}")
        
        if platform.system() == 'Windows':
            subprocess.run(cmd, check=True)
        else:
            # On Linux/Unix, we can just replace the current process
            os.execv(sys.executable, [sys.executable] + cmd[1:])
            
    except Exception as e:
        logger.error(f"Error in service mode: {e}", exc_info=True)
        return 1
    
    return 0

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Log Collector Startup Script")
    
    # Basic arguments
    parser.add_argument("--service", action="store_true", 
                       help="Run in service mode")
    
    # Service command and arguments
    parser.add_argument("service_command", nargs="?", default=None,
                       help="Service command (install, start, stop, etc.)")
    parser.add_argument("service_args", nargs="*",
                       help="Additional arguments for service command")
    
    args = parser.parse_args()
    
    try:
        # Set up environment
        setup_environment()
        
        # Run CLI or service based on arguments
        if args.service or args.service_command:
            return run_as_service(args)
        else:
            return run_as_cli()
    
    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())