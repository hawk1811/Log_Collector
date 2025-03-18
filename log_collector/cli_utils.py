"""
Command Line Interface utility functions for Log Collector.
Contains terminal handling, formatting, and other helper functions.
"""
import os
import sys
import platform
import re
from colorama import Fore, Style as ColorStyle, init
from log_collector.config import logger

# Force colorama to initialize with specific settings for better Linux compatibility
init(autoreset=False, strip=False)

def setup_terminal():
    """Setup terminal for non-blocking input while preserving normal input mode.
    
    Returns:
        Terminal settings to be used for restoration later, or None if N/A
    """
    try:
        if os.name == 'posix':
            import termios
            import tty
            # Save current terminal settings
            old_settings = termios.tcgetattr(sys.stdin)
            # We don't modify them here to preserve normal input behavior
            # Terminal modes will be temporarily changed only during key checks
            return old_settings
        elif os.name == 'nt':
            # No special setup needed for Windows
            return None
    except Exception as e:
        logger.error(f"Error setting up terminal: {e}")
    return None

def is_key_pressed():
    """Check if a key is pressed without blocking.
    
    Returns:
        bool: True if key pressed, False otherwise
    """
    try:
        if os.name == 'posix':
            import select
            import termios
            import tty
            
            # Save current terminal settings
            old_settings = termios.tcgetattr(sys.stdin)
            
            try:
                # Temporarily set terminal to raw mode for check
                tty.setraw(sys.stdin.fileno(), termios.TCSANOW)
                
                # Check for input with a very short timeout
                result = select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])
                
                return result
            finally:
                # Always restore terminal settings
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                
        elif os.name == 'nt':
            import msvcrt
            return msvcrt.kbhit()
    except Exception as e:
        logger.error(f"Error checking for key press: {e}")
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
            import termios
            import tty
            
            # Save current terminal settings
            old_settings = termios.tcgetattr(sys.stdin)
            
            try:
                # Temporarily set terminal to raw mode for reading
                tty.setraw(sys.stdin.fileno(), termios.TCSANOW)
                
                # Read a single character
                ch = sys.stdin.read(1)
                
                return ch
            finally:
                # Always restore terminal settings
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                
        elif os.name == 'nt':
            import msvcrt
            if msvcrt.kbhit():
                return msvcrt.getch().decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Error reading key: {e}")
        # Fallback
        pass
    return ''

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

# Global variable to track terminal state
_terminal_modified = False

def safe_setup_terminal():
    """Safely setup terminal for non-blocking input with state tracking."""
    global _terminal_modified
    
    try:
        old_settings = setup_terminal()
        _terminal_modified = True
        return old_settings
    except Exception as e:
        logger.error(f"Error in safe terminal setup: {e}")
        return None

def safe_restore_terminal(old_settings):
    """Safely restore terminal settings with state tracking."""
    global _terminal_modified
    
    if _terminal_modified and old_settings:
        restore_terminal(old_settings)
        _terminal_modified = False

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
    # Use simple block characters that work reliably in all Linux terminals
    is_linux = platform.system() != "Windows"
    
    if is_linux:
        filled_char = '▓'  # This works better on Linux terminals
        empty_char = '░'
    else:
        filled_char = '█'  # Windows has better Unicode support in terminals
        empty_char = '░'
    
    # Ensure percentage is within valid range
    percentage = max(0, min(100, percentage))
    
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

def calculate_content_width(text):
    """Calculate the display width of a string considering ANSI codes.
    
    Args:
        text: Text that may contain ANSI color codes
        
    Returns:
        int: Visual display width
    """
    # Strip ANSI codes to get true display length
    return len(strip_ansi(text))
