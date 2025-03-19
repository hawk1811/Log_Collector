"""
Log Collector - High-performance log collection and processing system.
"""
from .utils import get_version
from .cli_main import CLI
from .auth import AuthManager
from .updater import check_for_updates, restart_application

__version__ = get_version()
__all__ = ['CLI', 'get_version', 'AuthManager', 'check_for_updates', 'restart_application']
