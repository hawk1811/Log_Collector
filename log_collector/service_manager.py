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
        # First check using system service commands if available
        is_running = self._check_service_running()
        
        # If we couldn't determine using system commands, fall back to PID file
        if is_running is None:
            # Get the PID from the file
            pid = self._get_process_pid()
            
            # Check if the process is running
            is_running = self._is_process_running(pid)
            
            # Additional check for "starting" marker
            if not is_running and os.path.exists(self.pid_file):
                try:
                    with open(self.pid_file, 'r') as f:
                        content = f.read().strip()
                    if content == "starting":
                        # Service is still starting up
                        logger.debug("Service is in starting state according to PID file")
                        is_running = False  # Don't consider it running yet
                except Exception:
                    pass
        
        # Update state
        self.state["running"] = is_running
        self.state["pid"] = self._get_process_pid()  # Still try to get PID for info
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
    
    def _check_service_running(self):
        """Check if service is running using system service commands.
        
        Returns:
            bool or None: True if running, False if not running, None if could not determine
        """
        if platform.system() == "Windows":
            try:
                # Check if the Windows service "LogCollector" is running
                result = subprocess.run(
                    ["sc", "query", "LogCollector"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0 and "RUNNING" in result.stdout:
                    return True
                elif result.returncode == 0 and "STOPPED" in result.stdout:
                    return False
                else:
                    # Service might not be installed or other issues
                    logger.debug("Could not determine service status using sc query")
                    return None
            except Exception as e:
                logger.debug(f"Error checking Windows service status: {e}")
                return None
        else:
            # Linux/Unix platforms - check using systemctl
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", "log_collector.service"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0 and result.stdout.strip() == "active":
                    return True
                elif result.returncode != 0:
                    return False
                else:
                    return None
            except Exception as e:
                # Try service command as fallback
                try:
                    result = subprocess.run(
                        ["service", "log_collector", "status"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    
                    if result.returncode == 0 and "running" in result.stdout.lower():
                        return True
                    elif result.returncode != 0:
                        return False
                    else:
                        return None
                except Exception as e:
                    logger.debug(f"Error checking Linux service status: {e}")
                    return None
    
    def start_service(self):
        """Start the Log Collector service."""
        # Check if already running
        if self._check_status():
            logger.info("Service is already running")
            return True, "Service is already running"
        
        # Prepare command
        cmd = self._build_service_command("start")
        
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
        
        # Add the correct PID file path to the environment
        env = os.environ.copy()
        env["LOG_COLLECTOR_PID_FILE"] = str(self.pid_file)
        env["LOG_COLLECTOR_LOG_FILE"] = str(self.log_file)
        
        try:
            # Start the service
            logger.info(f"Starting service with command: {' '.join(cmd)}")
            
            if platform.system() == "Windows":
                # On Windows, use subprocess.CREATE_NEW_PROCESS_GROUP to detach the process
                
                # First, check if we're trying to start the Windows service
                if self._is_windows_service_installed():
                    # Try to start the Windows service using sc
                    result = subprocess.run(
                        ["sc", "start", "LogCollector"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    
                    if result.returncode == 0:
                        # Wait for service to start
                        time.sleep(2)
                        if self._check_status():
                            self.state["start_time"] = time.time()
                            self._save_state(self.state)
                            return True, "Windows service started successfully"
                
                # Fall back to command-line approach
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
                
                # Use absolute paths for the Python executable and script
                if cmd[0] == sys.executable:
                    python_exe = cmd[0]
                else:
                    python_exe = sys.executable
                    
                if len(cmd) > 1 and os.path.exists(cmd[1]):
                    script_path = os.path.abspath(cmd[1])
                    new_cmd = [python_exe, script_path] + cmd[2:]
                else:
                    new_cmd = cmd
                    
                logger.info(f"Starting service with modified command: {' '.join(new_cmd)}")
                
                # First write a direct marker to the PID file to help with status detection
                try:
                    with open(self.pid_file, 'w') as f:
                        f.write("starting")
                except Exception as e:
                    logger.warning(f"Could not write starting marker to PID file: {e}")
                
                process = subprocess.Popen(
                    new_cmd,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env
                )
                
                # Give the process a moment to start
                time.sleep(1)
                
                # Try to get some output to diagnose issues
                try:
                    stdout, stderr = process.communicate(timeout=2)
                    if stderr:
                        logger.error(f"Process stderr: {stderr.decode('utf-8', errors='ignore')}")
                    if stdout:
                        logger.info(f"Process stdout: {stdout.decode('utf-8', errors='ignore')}")
                except subprocess.TimeoutExpired:
                    # This is normal - the process is still running
                    pass
            else:
                # On Unix, we can just use subprocess.Popen with normal arguments
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env
                )
            
            # Wait for service to start
            for i in range(15):  # Increased timeout to 15 seconds
                time.sleep(1)
                if self._check_status():
                    self.state["start_time"] = time.time()
                    self._save_state(self.state)
                    return True, "Service started successfully"
                
                # Check if the PID file exists but doesn't contain a valid PID yet
                if os.path.exists(self.pid_file):
                    try:
                        with open(self.pid_file, 'r') as f:
                            content = f.read().strip()
                        if content == "starting":
                            # Still starting, continue waiting
                            logger.info(f"Service still starting (attempt {i+1})")
                            continue
                    except Exception:
                        pass
            
            logger.error("Service failed to start within timeout")
            return False, "Service failed to start within timeout"
        
        except Exception as e:
            logger.error(f"Error starting service: {e}")
            return False, f"Error starting service: {e}"

    def _is_windows_service_installed(self):
        """Check if the LogCollector Windows service is installed."""
        if platform.system() != "Windows":
            return False
            
        try:
            result = subprocess.run(
                ["sc", "query", "LogCollector"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            return result.returncode == 0
        except Exception:
            return False
    
    def stop_service(self):
        """Stop the Log Collector service."""
        # Check if running
        if not self._check_status():
            logger.info("Service is not running")
            return True, "Service is not running"
        
        # Try to stop using system commands first
        system_stop_result = self._stop_service_system()
        if system_stop_result is True:
            # System command successfully stopped the service
            self.state["running"] = False
            self._save_state(self.state)
            return True, "Service stopped successfully using system commands"
        
        # Fall back to command-line approach
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
    
    def _stop_service_system(self):
        """Stop the service using system commands.
        
        Returns:
            bool or None: True if successfully stopped, False if failed, None if not possible
        """
        if platform.system() == "Windows":
            try:
                # Try to stop the Windows service
                result = subprocess.run(
                    ["sc", "stop", "LogCollector"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    # Wait briefly to allow service to stop
                    time.sleep(2)
                    return True
                else:
                    logger.debug(f"Error stopping Windows service: {result.stderr}")
                    return False
            except Exception as e:
                logger.debug(f"Exception stopping Windows service: {e}")
                return None
        else:
            # Linux/Unix platforms - try systemctl
            try:
                result = subprocess.run(
                    ["systemctl", "stop", "log_collector.service"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    # Wait briefly to allow service to stop
                    time.sleep(2)
                    return True
                
                # Try service command as fallback
                result = subprocess.run(
                    ["service", "log_collector", "stop"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    # Wait briefly to allow service to stop
                    time.sleep(2)
                    return True
                
                return False
            except Exception as e:
                logger.debug(f"Error stopping Linux service: {e}")
                return None
    
    def restart_service(self):
        """Restart the Log Collector service."""
        # First try system commands for restart
        system_restart_result = self._restart_service_system()
        if system_restart_result is True:
            # Wait for service to restart
            for _ in range(10):
                time.sleep(1)
                if self._check_status():
                    self.state["start_time"] = time.time()
                    self._save_state(self.state)
                    return True, "Service restarted successfully using system commands"
        
        # Fall back to manual stop+start
        was_running = self._check_status()
        
        if was_running:
            stop_success, stop_message = self.stop_service()
            if not stop_success:
                return False, f"Failed to restart service: {stop_message}"
        
        # Start the service
        return self.start_service()
    
    def _restart_service_system(self):
        """Restart the service using system commands.
        
        Returns:
            bool or None: True if successfully restarted, False if failed, None if not possible
        """
        if platform.system() == "Windows":
            try:
                # Try to restart the Windows service
                result = subprocess.run(
                    ["sc", "stop", "LogCollector"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode != 0:
                    logger.debug(f"Error stopping Windows service for restart: {result.stderr}")
                    return False
                
                # Wait for service to stop
                time.sleep(2)
                
                # Start the service
                result = subprocess.run(
                    ["sc", "start", "LogCollector"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    return True
                else:
                    logger.debug(f"Error starting Windows service after stop: {result.stderr}")
                    return False
            except Exception as e:
                logger.debug(f"Exception restarting Windows service: {e}")
                return None
        else:
            # Linux/Unix platforms - try systemctl
            try:
                result = subprocess.run(
                    ["systemctl", "restart", "log_collector.service"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    return True
                
                # Try service command as fallback
                result = subprocess.run(
                    ["service", "log_collector", "restart"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    return True
                
                return False
            except Exception as e:
                logger.debug(f"Error restarting Linux service: {e}")
                return None
    
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
