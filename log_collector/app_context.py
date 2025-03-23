"""
Application context module for Log Collector.
Provides consistent access to paths and resources regardless of deployment method.
"""
import os
import sys
import platform
from pathlib import Path

class AppContext:
    """Manages application paths and environment regardless of deployment method."""
    
    def __init__(self):
        # Detect if running as a frozen executable
        self.is_frozen = getattr(sys, 'frozen', False)
        
        # Initialize paths
        self.base_dir = self._determine_base_dir()
        self.data_dir = self._get_data_dir()
        self.log_dir = self._get_log_dir()
        self.sources_file = self._get_sources_file()
        self.pid_file = self._get_pid_file()
        self.log_file = self._get_log_file()
        self.auth_file = self._get_auth_file()
        self.policy_file = self._get_policy_file()
        self.filter_file = self._get_filter_file()
        self.service_state_file = self._get_service_state_file()
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _determine_base_dir(self):
        """Determine the base directory regardless of deployment method."""
        if self.is_frozen:
            # For frozen executables (PyInstaller)
            return Path(os.path.dirname(sys.executable))
        else:
            # For module-based deployment
            return Path(__file__).resolve().parent.parent
    
    def _get_data_dir(self):
        """Get the data directory path."""
        return self.base_dir / "data"
    
    def _get_log_dir(self):
        """Get the log directory path."""
        return self.base_dir / "logs"
    
    def _get_sources_file(self):
        """Get the sources configuration file path."""
        return self.data_dir / "sources.json"
    
    def _get_pid_file(self):
        """Get the PID file path."""
        return self.data_dir / "service.pid"
    
    def _get_log_file(self):
        """Get the service log file path."""
        return self.log_dir / "service.log"
    
    def _get_auth_file(self):
        """Get the authentication file path."""
        return self.data_dir / "auth.json"
    
    def _get_policy_file(self):
        """Get the aggregation policy file path."""
        return self.data_dir / "policy.json"
    
    def _get_filter_file(self):
        """Get the filter configuration file path."""
        return self.data_dir / "filters.json"
    
    def _get_service_state_file(self):
        """Get the service state file path."""
        return self.data_dir / "service_state.json"
    
    def _ensure_directories(self):
        """Ensure all required directories exist."""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
    
    def get_resource_path(self, relative_path):
        """Get the absolute path to a resource file."""
        if self.is_frozen:
            # Running as compiled executable
            if hasattr(sys, '_MEIPASS'):
                # PyInstaller creates a temp folder and stores path in _MEIPASS
                base_path = Path(sys._MEIPASS)
            else:
                base_path = Path(os.path.dirname(sys.executable))
        else:
            # Running as a normal Python script/module
            base_path = self.base_dir
            
        return base_path / relative_path

# Create a singleton instance
_app_context = None

def get_app_context():
    """Get the global app context instance."""
    global _app_context
    if _app_context is None:
        _app_context = AppContext()
    return _app_context
