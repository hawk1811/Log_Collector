"""
Health check configuration module for Log Collector.
Provides functions for configuring and managing health check monitoring.
"""
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.formatted_text import HTML
from colorama import Fore, Style as ColorStyle

from log_collector.config import DEFAULT_HEALTH_CHECK_INTERVAL

def configure_health_check(health_check, cli):
    """Configure health check monitoring.
    
    Args:
        health_check: Health check instance
        cli: CLI instance for printing header
    """
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Health Check Configuration ==={ColorStyle.RESET_ALL}")
    
    # Check if health check is already configured
    is_configured = hasattr(health_check, 'config') and health_check.config is not None
    is_running = is_configured and health_check.running
    
    if is_configured:
        config = health_check.config
        print(f"\nCurrent Configuration:")
        print(f"HEC URL: {config['hec_url']}")
        print(f"HEC Token: {'*' * 10}")
        print(f"Interval: {config['interval']} seconds")
        print(f"Status: {'Running' if is_running else 'Stopped'}")
        
        print("\nOptions:")
        print("1. Update Configuration")
        print("2. Start/Stop Health Check")
        print("3. Return to Main Menu")
        
        choice = prompt(
            HTML("<ansicyan>Choose an option (1-3): </ansicyan>"),
            style=cli.prompt_style
        )
        
        if choice == "1":
            update_health_check(health_check, cli)
            return  # Return after update to prevent menu stacking
        elif choice == "2":
            if is_running:
                health_check.stop()
                print(f"{Fore.YELLOW}Health check monitoring stopped.{ColorStyle.RESET_ALL}")
            else:
                if health_check.start():
                    print(f"{Fore.GREEN}Health check monitoring started.{ColorStyle.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Failed to start health check monitoring.{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")
            clear()  # Clear screen when returning
            return
        elif choice == "3":
            clear()  # Clear screen when returning
            return
        else:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")
            configure_health_check(health_check, cli)  # Recursive call to show the menu again
            return
    else:
        print("Health check is not configured.")
        print("\nOptions:")
        print("1. Configure Health Check")
        print("2. Return to Main Menu")
        
        choice = prompt(
            HTML("<ansicyan>Choose an option (1-2): </ansicyan>"),
            style=cli.prompt_style
        )
        
        if choice == "1":
            update_health_check(health_check, cli)
            return  # Return after update to prevent menu stacking
        elif choice == "2":
            clear()  # Clear screen when returning
            return
        else:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")
            configure_health_check(health_check, cli)  # Recursive call to show the menu again
            return

def update_health_check(health_check, cli):
    """Update health check configuration.
    
    Args:
        health_check: Health check instance
        cli: CLI instance for printing header
    """
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Configure Health Check ==={ColorStyle.RESET_ALL}")
    
    # Check if health check is already configured
    is_configured = hasattr(health_check, 'config') and health_check.config is not None
    current_url = health_check.config['hec_url'] if is_configured else ""
    current_token = health_check.config['hec_token'] if is_configured else ""
    current_interval = health_check.config['interval'] if is_configured else DEFAULT_HEALTH_CHECK_INTERVAL
    
    # Get HEC URL
    while True:
        hec_url = prompt(f"HEC URL {f'[{current_url}]' if current_url else ''}: ")
        if not hec_url and current_url:
            hec_url = current_url
        
        if hec_url and hec_url.startswith(("http://", "https://")):
            break
        
        print(f"{Fore.RED}Invalid URL. Please enter a valid URL starting with http:// or https://.{ColorStyle.RESET_ALL}")
    
    # Get HEC token
    while True:
        hec_token = prompt(f"HEC Token {f'[{current_token}]' if current_token else ''}: ")
        if not hec_token and current_token:
            hec_token = current_token
        
        if hec_token:
            break
        
        print(f"{Fore.RED}HEC token cannot be empty.{ColorStyle.RESET_ALL}")
    
    # Get interval
    while True:
        interval_str = prompt(f"Check Interval in seconds [{current_interval}]: ")
        if not interval_str:
            interval = current_interval
            break
        
        try:
            interval = int(interval_str)
            if interval > 0:
                break
            else:
                print(f"{Fore.RED}Interval must be greater than 0.{ColorStyle.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid interval. Please enter a valid number.{ColorStyle.RESET_ALL}")
    
    # Configure health check
    print(f"\n{Fore.CYAN}Testing health check connection...{ColorStyle.RESET_ALL}")
    
    # Store current running state to restore it if needed
    was_running = hasattr(health_check, 'running') and health_check.running
    
    # Stop health check if it's running
    if was_running:
        health_check.stop()
    
    if health_check.configure(hec_url, hec_token, interval):
        print(f"{Fore.GREEN}Health check configured successfully.{ColorStyle.RESET_ALL}")
        
        # Auto-start health check
        if health_check.start():
            print(f"{Fore.GREEN}Health check monitoring started.{ColorStyle.RESET_ALL}")
        else:
            print(f"{Fore.RED}Failed to start health check monitoring.{ColorStyle.RESET_ALL}")
    else:
        print(f"{Fore.RED}Failed to configure health check.{ColorStyle.RESET_ALL}")
        
        # Restore previous health check state if possible
        if was_running and hasattr(health_check, 'config') and health_check.config is not None:
            if health_check.start():
                print(f"{Fore.YELLOW}Restored previous health check configuration.{ColorStyle.RESET_ALL}")
    
    input("Press Enter to continue...")
    clear()  # Clear screen when returning
    return
