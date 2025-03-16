"""
Command Line Interface utility functions for Log Collector.
Contains terminal handling, formatting, and other helper functions.
"""
import os
import sys
from colorama import Fore, Style as ColorStyle
from log_collector.config import logger

def setup_terminal():
    """Setup terminal for non-blocking input.
    
    Returns:
        Terminal settings to be used for restoration later, or None if N/A
    """
    try:
        if os.name == 'posix':
            import termios
            import tty
            # Save current terminal settings
            old_settings = termios.tcgetattr(sys.stdin)
            # Set terminal to raw mode
            tty.setraw(sys.stdin.fileno(), termios.TCSANOW)
            return old_settings
        elif os.name == 'nt':
            # No special setup needed for Windows
            return None
    except Exception as e:
        logger.error(f"Error setting up terminal: {e}")
    return None

def restore_terminal(old_settings):
    """Restore terminal settings.
    
    Args:
        old_settings: Terminal settings to restore
    """
    try:
        if os.name == 'posix' and old_settings:
            import termios
            # Restore terminal settings
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    except Exception as e:
        logger.error(f"Error restoring terminal: {e}")

def is_key_pressed():
    """Check if a key is pressed without blocking.
    
    Returns:
        bool: True if key pressed, False otherwise
    """
    try:
        if os.name == 'posix':
            import select
            return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])
        elif os.name == 'nt':
            import msvcrt
            return msvcrt.kbhit()
    except Exception:
        # Fallback
        return False
    return False

def read_key():
    """Read a key press.
    
    Returns:
        str: Key pressed or empty string
    """
    try:
        if os.name == 'posix':
            return sys.stdin.read(1)
        elif os.name == 'nt':
            import msvcrt
            if msvcrt.kbhit():
                return msvcrt.getch().decode('utf-8', errors='ignore')
    except Exception:
        # Fallback
        pass
    return ''

def format_timestamp(timestamp):
    """Format timestamp for display.
    
    Args:
        timestamp: Timestamp to format, or None
        
    Returns:
        str: Formatted timestamp string
    """
    if timestamp is None:
        return "Never"
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def get_bar(percentage, width=20):
    """Generate a visual bar representation of a percentage.
    
    Args:
        percentage: Percentage value (0-100)
        width: Width of the bar in characters
        
    Returns:
        str: Visual bar
    """
    filled_width = int(width * percentage / 100)
    bar = '█' * filled_width + '░' * (width - filled_width)
    return bar

def format_bytes(bytes_value):
    """Format bytes into human-readable format.
    
    Args:
        bytes_value: Value in bytes
        
    Returns:
        str: Formatted string with appropriate unit
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"
