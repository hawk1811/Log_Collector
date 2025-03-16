"""
Command Line Interface utility functions for Log Collector.
Contains terminal handling, formatting, and other helper functions.
"""
import os
import sys
import platform
from colorama import Fore, Style as ColorStyle, init
from log_collector.config import logger

# Force colorama to initialize with strip=False for Linux terminals
init(strip=False)

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
    # Use more compatible characters that render well across platforms
    if platform.system() == "Windows":
        filled_char = '█'
        empty_char = '░'
    else:
        filled_char = '▓'  # More compatible filled block
        empty_char = '░'   # More compatible empty block
    
    filled_width = int(width * percentage / 100)
    bar = filled_char * filled_width + empty_char * (width - filled_width)
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

def strip_ansi(text):
    """Remove ANSI color codes from text.
    
    Args:
        text: Text containing ANSI color codes
        
    Returns:
        str: Text without ANSI color codes
    """
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def get_terminal_size():
    """Get terminal size in a cross-platform way.
    
    Returns:
        tuple: (width, height) of terminal
    """
    try:
        # Try to get size from os module (works in most environments)
        columns, lines = os.get_terminal_size()
        return columns, lines
    except (AttributeError, OSError):
        # Fallback for older Python versions or unusual environments
        try:
            import shutil
            columns, lines = shutil.get_terminal_size()
            return columns, lines
        except (ImportError, AttributeError):
            # Final fallback: use standard sizes
            return 80, 24
