"""
Service Manager module for Log Collector.
Handles interaction with the Log Collector service.
"""
import os
import sys
import time
import subprocess
import platform
import json
from pathlib import Path

from log_collector.config import (
    logger,
    DATA_DIR,
)

# Constants
SERVICE_STATE_FILE = DATA_DIR / "service_state.json"
DEFAULT_PID_FILE = DATA_DIR / "service.pid"
DEFAULT_LOG_FILE = DATA_DIR / "service.log"

class ServiceManager:
    """Manages Log Collector service lifecycle."""
    
    def __init__(self):
        """Initialize the service manager."""
        self.service_script = self._get_service_script_path()
        self.pid_file = DEFAULT_PID_FILE
        self.log_file = DEFAULT_LOG_FILE
        
        # Ensure data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # Initialize service state
        self.state = self._load_state()
    
    def _get_service_script_path(self):
        """Get the path to the service script."""
        # Check for installed log_collector_service.py
        # First, check if it's in the same directory as the current module
        module_dir = os.path.dirname(os.path.abspath(__file__))
        service_script = os.path.join(os.path.dirname(module_dir), "log_collector_service.py")
        
        if os.path.exists(service_script):
            return service_script
        
        # Check if the service script is available in the PATH
        if platform.system() == "Windows":
            service_in_path = self._which("log_collector_service.py") or self._which("log_collector_service")
            if service_in_path:
                return service_in_path
        else:
            service_in_path = self._which("log_collector_service.py")
            if service_in_path:
                return service_in_path
        
        # If we can't find it, return the script name and rely on it being in PATH
        return "log_collector_service.py"
    
    def _which(self, program):
        """Cross-platform implementation of Unix's 'which' command."""
        def is_exe(fpath):
            return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

        fpath, fname = os.path.split(program)
        if fpath:
            if is_exe(program):
                return program
        else:
            for path in os.environ["PATH"].split(os.pathsep):
                exe_file = os.path.join(path, program)
                if is_exe(exe_file):
                    return exe_file

        return None
    
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
    
    def _get_process_pid(self):
        """Get PID from PID file."""
        try:
            if os.path.exists(self.pid_file):
                with open(self.pid_file, "r") as f:
                    pid = int(f.read().strip())
                return pid
            return None
        except (IOError, ValueError) as e:
            logger.error(f"Error reading PID file: {e}")
            return None
    
    def _is_process_running(self, pid):
        """Check if a process with the given PID is running."""
        if pid is None:
            return False
        
        try:
            if platform.system() == "Windows":
                # Windows-specific check
                import ctypes
                kernel32 = ctypes.windll.kernel32
                SYNCHRONIZE = 0x00100000
                process = kernel32.OpenProcess(SYNCHRONIZE, 0, pid)
                if process != 0:
                    kernel32.CloseHandle(process)
                    return True
                return False
            else:
                # Unix-specific check
                os.kill(pid, 0)  # Signal 0 is a null signal; tests if process exists
                return True
        except (ImportError, OSError):
            return False
    
    def _check_status(self):
        """Check the actual status of the service and update state."""
        # Get the PID from the file
        pid = self._get_process_pid()
        
        # Check if the process is running
        is_running = self._is_process_running(pid)
        
        # Update state
        self.state["running"] = is_running
        self.state["pid"] = pid
        self.state["last_status_check"] = time.time()
        
        # Clean up stale PID file if needed
        if not is_running and pid is not None and os.path.exists(self.pid_file):
            try:
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
        
        # Prepare command
        cmd = self._build_service_command("start")
        
        try:
            # Start the service
            logger.info(f"Starting service with command: {' '.join(cmd)}")
            
            if platform.system() == "Windows":
                # On Windows, we need to use subprocess.CREATE_NEW_PROCESS_GROUP
                # to detach the process
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
                
                subprocess.Popen(
                    cmd,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            else:
                # On Unix, we can just use subprocess.Popen with normal arguments
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            
            # Wait for service to start
            for _ in range(10):
                time.sleep(1)
                if self._check_status():
                    self.state["start_time"] = time.time()
                    self._save_state(self.state)
                    return True, "Service started successfully"
            
            return False, "Service failed to start within timeout"
        
        except Exception as e:
            logger.error(f"Error starting service: {e}")
            return False, f"Error starting service: {e}"
    
    def stop_service(self):
        """Stop the Log Collector service."""
        # Check if running
        if not self._check_status():
            logger.info("Service is not running")
            return True, "Service is not running"
        
        # Prepare command
        cmd = self._build_service_command("stop")
        
        try:
            # Stop the service
            logger.info(f"Stopping service with command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Error stopping service: {result.stderr}")
                return False, f"Error stopping service: {result.stderr}"
            
            # Wait for service to stop
            for _ in range(10):
                time.sleep(1)
                if not self._check_status():
                    return True, "Service stopped successfully"
            
            return False, "Service failed to stop within timeout"
        
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
    
    def _build_service_command(self, action):
        """Build command for service management."""
        cmd = []
        
        # Base command
        if self.service_script.endswith(".py"):
            cmd = [sys.executable, self.service_script]
        else:
            cmd = [self.service_script]
        
        # Add action
        cmd.append(action)
        
        # Add PID file
        cmd.extend(["--pid-file", str(self.pid_file)])
        
        # Add log file
        cmd.extend(["--log-file", str(self.log_file)])
        
        return cmd
