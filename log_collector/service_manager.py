"""
Service Manager module for Log Collector.
Handles interaction with the Log Collector service.
"""
import os
import sys
import time
import platform
import json

from log_collector.config import (
    logger,
)
from log_collector.app_context import get_app_context

# Get app context
app_context = get_app_context()

# Constants
SERVICE_STATE_FILE = app_context.service_state_file

# Import our service module functions
from log_collector.service_module import (
    start_service,
    stop_service,
    restart_service,
    get_service_status,
    is_process_running,
    get_pid_from_file,
)

class ServiceManager:
    """Manages Log Collector service lifecycle."""
    
    def __init__(self):
        """Initialize the service manager."""
        self.pid_file = app_context.pid_file
        self.log_file = app_context.log_file
        
        # Ensure data directory exists
        os.makedirs(app_context.data_dir, exist_ok=True)
        
        # Initialize service state
        self.state = self._load_state()
    
    def _load_state(self):
        """Load service state from file."""
        if not SERVICE_STATE_FILE.exists():
            # Initialize with default state
            default_state = {
                "running": False,
                "pid": None,
                "start_time": None,
                "last_status_check": None,
                "auto_start": True,
                "pid_file": str(self.pid_file),
                "log_file": str(self.log_file)
            }
            self._save_state(default_state)
            return default_state
        
        try:
            with open(SERVICE_STATE_FILE, "r") as f:
                state = json.load(f)
            
            # Update PID file and log file paths if they exist in the state
            if "pid_file" in state:
                self.pid_file = Path(state["pid_file"])
            if "log_file" in state:
                self.log_file = Path(state["log_file"])
                
            return state
        except Exception as e:
            logger.error(f"Error loading service state: {e}")
            # Return default state if loading fails
            return {
                "running": False,
                "pid": None,
                "start_time": None,
                "last_status_check": None,
                "auto_start": True,
                "pid_file": str(self.pid_file),
                "log_file": str(self.log_file)
            }
        
    def _save_state(self, state):
        """Save service state to file."""
        try:
            # Always update the pid_file and log_file in the state
            state["pid_file"] = str(self.pid_file)
            state["log_file"] = str(self.log_file)
            
            with open(SERVICE_STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
            
            # Update instance state
            self.state = state
            return True
        except Exception as e:
            logger.error(f"Error saving service state: {e}")
            return False
    
    def is_running(self):
        """Check if the service is running."""
        # First, update our state based on actual system state
        self._check_status()
        return self.state.get("running", False)
    
    def _check_status(self):
        """Check the actual status of the service and update state."""
        pid = get_pid_from_file(self.pid_file)
        is_running = False
        
        if pid is not None:
            is_running = is_process_running(pid)
        
        # Update state
        self.state["running"] = is_running
        self.state["pid"] = pid
        self.state["last_status_check"] = time.time()
        
        # Clean up stale PID file if needed
        if not is_running and os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, 'r') as f:
                    content = f.read().strip()
                if content != "starting":  # Don't remove if it's still starting
                    os.remove(self.pid_file)
                    self.state["pid"] = None
            except OSError as e:
                logger.error(f"Error removing stale PID file: {e}")
        
        # Save updated state
        self._save_state(self.state)
        
        return is_running
    
    def start_service(self):
        """Start the Log Collector service."""
        # Check if already running
        if self._check_status():
            logger.info("Service is already running")
            return True, "Service is already running"
        
        # Create the directories for PID and log files if they don't exist
        pid_dir = os.path.dirname(self.pid_file)
        log_dir = os.path.dirname(self.log_file)
        
        try:
            if pid_dir and not os.path.exists(pid_dir):
                os.makedirs(pid_dir, exist_ok=True)
                logger.info(f"Created PID directory: {pid_dir}")
                
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
                logger.info(f"Created log directory: {log_dir}")
        except Exception as e:
            logger.error(f"Error creating directories: {e}")
            return False, f"Error creating directories: {e}"
        
        try:
            # Call our service module function
            success = start_service(False, self.pid_file, self.log_file)
            
            if success:
                # Wait for service to start
                for i in range(15):  # Wait up to 15 seconds
                    time.sleep(1)
                    if self._check_status():
                        self.state["start_time"] = time.time()
                        self._save_state(self.state)
                        return True, "Service started successfully"
                
                return False, "Service failed to start within timeout"
            else:
                return False, "Error starting service"
                
        except Exception as e:
            logger.error(f"Error starting service: {e}")
            return False, f"Error starting service: {e}"
    
    def stop_service(self):
        """Stop the Log Collector service."""
        # Check if running
        if not self._check_status():
            logger.info("Service is not running")
            return True, "Service is not running"
        
        try:
            # Call our service module function
            success = stop_service(self.pid_file)
            
            if success:
                # Wait for service to stop
                for _ in range(10):
                    time.sleep(1)
                    if not self._check_status():
                        return True, "Service stopped successfully"
                
                return False, "Service failed to stop within timeout"
            else:
                return False, "Error stopping service"
        
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
            return False, f"Error stopping service: {e}"
    
    def restart_service(self):
        """Restart the Log Collector service."""
        # First stop the service
        was_running = self._check_status()
        
        if was_running:
            stop_success, stop_message = self.stop_service()
            if not stop_success:
                return False, f"Failed to restart service: {stop_message}"
        
        # Start the service
        time.sleep(2)  # Give it a moment after stopping
        return self.start_service()
    
    def get_service_log(self, lines=100):
        """Get the last N lines from the service log."""
        if not os.path.exists(self.log_file):
            return []
        
        try:
            with open(self.log_file, "r") as f:
                # Read all lines and get the last N
                log_lines = f.readlines()
                return log_lines[-lines:] if len(log_lines) > lines else log_lines
        except Exception as e:
            logger.error(f"Error reading service log: {e}")
            return [f"Error reading log: {e}"]
    
    def set_auto_start(self, enabled):
        """Set whether the service should auto-start."""
        self.state["auto_start"] = enabled
        self._save_state(self.state)
    
    def get_auto_start(self):
        """Get whether the service should auto-start."""
        return self.state.get("auto_start", True)
    
    def get_status_info(self):
        """Get detailed status information."""
        # Update status
        self._check_status()
        
        # Build status info
        pid = self.state.get("pid")
        running = self.state.get("running", False)
        start_time = self.state.get("start_time")
        uptime = None
        
        if running and start_time:
            uptime_seconds = time.time() - start_time
            uptime = self._format_uptime(uptime_seconds)
        
        return {
            "running": running,
            "pid": pid,
            "start_time": start_time,
            "uptime": uptime,
            "auto_start": self.state.get("auto_start", True),
            "pid_file": str(self.pid_file),
            "log_file": str(self.log_file)
        }
    
    def _format_uptime(self, seconds):
        """Format uptime in a human-readable way."""
        days, remainder = divmod(int(seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0 or days > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or hours > 0 or days > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        
        return " ".join(parts)
