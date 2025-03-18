"""
CLI authentication module for Log Collector.
Provides functions for handling login and password management.
"""
import getpass
import platform
import time

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.formatted_text import HTML
from colorama import Fore, Style as ColorStyle

def login_screen(auth_manager, cli):
    """Display login screen and handle authentication.
    
    Args:
        auth_manager: Authentication manager instance
        cli: CLI instance for printing header
        
    Returns:
        tuple: (success, username, needs_password_change)
    """
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Log Collector Login ==={ColorStyle.RESET_ALL}")
    
    max_attempts = 5
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        
        # Get username
        username = prompt(
            HTML("<ansicyan>Username: </ansicyan>"),
            style=cli.prompt_style
        )
        
        if not username:
            print(f"{Fore.RED}Username cannot be empty.{ColorStyle.RESET_ALL}")
            continue
        
        # Get password (use getpass for more secure input if available)
        # In some environments, getpass might not work as expected
        try:
            # Try to use getpass for secure password entry
            password = getpass.getpass("Password: ")
        except (getpass.GetPassWarning, Exception):
            # Fall back to regular prompt if getpass fails
            password = prompt(
                HTML("<ansicyan>Password: </ansicyan>"),
                style=cli.prompt_style,
                is_password=True
            )
        
        # Authenticate
        success, message, needs_password_change = auth_manager.authenticate(username, password)
        
        if success:
            print(f"{Fore.GREEN}Login successful.{ColorStyle.RESET_ALL}")
            return True, username, needs_password_change
        else:
            print(f"{Fore.RED}{message}{ColorStyle.RESET_ALL}")
            
            # For lockout messages, give the user more time to read
            if "locked" in message.lower():
                time.sleep(2)
    
    print(f"{Fore.RED}Maximum login attempts exceeded. Exiting.{ColorStyle.RESET_ALL}")
    return False, None, False

def change_password_screen(auth_manager, username, force_change, cli):
    """Display the change password screen.
    
    Args:
        auth_manager: Authentication manager instance
        username: Username to change password for
        force_change: Whether this is a forced password change
        cli: CLI instance for printing header
        
    Returns:
        bool: Success or failure
    """
    clear()
    cli._print_header()
    
    if force_change:
        print(f"{Fore.YELLOW}=== Password Change Required ==={ColorStyle.RESET_ALL}")
        print("\nYou must change your password before continuing.")
        print("\nPassword requirements:")
        print("- At least 12 characters long")
        print("- At least one uppercase letter")
        print("- At least one digit")
        print("- At least one special character (!@#$%^&*()_+{}[]:<>,.?~/\\-)")
    else:
        print(f"{Fore.CYAN}=== Change Password ==={ColorStyle.RESET_ALL}")
        print("\nPassword requirements:")
        print("- At least 12 characters long")
        print("- At least one uppercase letter")
        print("- At least one digit")
        print("- At least one special character (!@#$%^&*()_+{}[]:<>,.?~/\\-)")
    
    # Get current password
    try:
        current_password = getpass.getpass("Current password: ")
    except (getpass.GetPassWarning, Exception):
        current_password = prompt(
            HTML("<ansicyan>Current password: </ansicyan>"),
            style=cli.prompt_style,
            is_password=True
        )
    
    # Get new password
    while True:
        try:
            new_password = getpass.getpass("New password: ")
        except (getpass.GetPassWarning, Exception):
            new_password = prompt(
                HTML("<ansicyan>New password: </ansicyan>"),
                style=cli.prompt_style,
                is_password=True
            )
        
        # Validate password
        valid, message = auth_manager.validate_password(new_password)
        if not valid:
            print(f"{Fore.RED}{message}{ColorStyle.RESET_ALL}")
            continue
        
        # Confirm new password
        try:
            confirm_password = getpass.getpass("Confirm new password: ")
        except (getpass.GetPassWarning, Exception):
            confirm_password = prompt(
                HTML("<ansicyan>Confirm new password: </ansicyan>"),
                style=cli.prompt_style,
                is_password=True
            )
        
        if new_password != confirm_password:
            print(f"{Fore.RED}Passwords do not match. Please try again.{ColorStyle.RESET_ALL}")
            continue
        
        # Change password
        success, message = auth_manager.change_password(username, current_password, new_password)
        if success:
            print(f"{Fore.GREEN}{message}{ColorStyle.RESET_ALL}")
            # Don't modify terminal settings here - just show message and return success
            input("Press Enter to continue...")
            return True
        else:
            print(f"{Fore.RED}{message}{ColorStyle.RESET_ALL}")
            
            # If authentication failed with the current password, start over
            if "Invalid username or password" in message:
                input("Press Enter to try again...")
                return False
    
    return False
