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

# Import terminal handling functions
from log_collector.cli_utils import setup_terminal, restore_terminal

def login_screen(auth_manager, cli):
    """Display login screen and handle authentication.
    
    Args:
        auth_manager: Authentication manager instance
        cli: CLI instance for printing header
        
    Returns:
        tuple: (success, username, needs_password_change)
    """
    # Setup terminal to ensure we start with a clean state
    old_settings = setup_terminal()
    
    try:
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
    
    finally:
        # Always restore terminal settings before returning
        restore_terminal(old_settings)

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
    # Setup terminal to ensure we start with a clean state
    old_settings = setup_terminal()
    
    try:
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
            print("")
        else:
            print(f"{Fore.CYAN}=== Change Password ==={ColorStyle.RESET_ALL}")
            print("\nPassword requirements:")
            print("- At least 12 characters long")
            print("- At least one uppercase letter")
            print("- At least one digit")
            print("- At least one special character (!@#$%^&*()_+{}[]:<>,.?~/\\-)")
            print("")
        
        # Validate current password before proceeding
        attempts = 0
        max_attempts = 3  # Limit retry attempts
        
        while attempts < max_attempts:
            print(f"{Fore.CYAN}Current password:{ColorStyle.RESET_ALL}")
            try:
                print(f"{Fore.CYAN}Current password:{ColorStyle.RESET_ALL} ", end="")
                current_password = getpass.getpass("")
            except (getpass.GetPassWarning, Exception):
                current_password = prompt(
                    HTML("<ansicyan>Current password: </ansicyan>"),
                    style=cli.prompt_style,
                    is_password=True
                )
        
            # Check if the current password is correct
            success, message, _ = auth_manager.authenticate(username, current_password)
            if success:
                break  # Proceed if the current password is correct
            else:
                print(f"{Fore.RED}{message}{ColorStyle.RESET_ALL}")
                attempts += 1
        
        if attempts == max_attempts:
            print(f"{Fore.RED}Too many failed attempts. Exiting password change.{ColorStyle.RESET_ALL}")
            input("Press Enter to return to login screen...")
            return False  # Properly return False to avoid getting stuck


        
        # Get new password
        attempts = 0
        max_attempts = 3  # Set a retry limit
        
        while attempts < max_attempts:
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
                attempts += 1
                continue
        
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
                attempts += 1
                continue
        
            # Attempt to change password
            success, message = auth_manager.change_password(username, current_password, new_password)
            if success:
                print(f"{Fore.GREEN}{message}{ColorStyle.RESET_ALL}")
                input("Press Enter to continue...")
                return True
            else:
                print(f"{Fore.RED}{message}{ColorStyle.RESET_ALL}")
                attempts += 1
        
        print(f"{Fore.RED}Too many failed attempts. Exiting password change.{ColorStyle.RESET_ALL}")
        input("Press Enter to return to login screen...")
        return False  # Ensure the flow doesn't get stuck



        
    finally:
        # Always restore terminal settings before returning
        restore_terminal(old_settings)
    
