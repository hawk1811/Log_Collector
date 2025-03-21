"""
CLI module for service management.
Provides functions for checking service status and controlling the service.
"""
import time
from datetime import datetime
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.formatted_text import HTML
from colorama import Fore, Style as ColorStyle

def manage_service(service_manager, cli):
    """Manage the Log Collector service.
    
    Args:
        service_manager: Service manager instance
        cli: CLI instance for header
    """
    while True:
        clear()
        cli._print_header()
        print(f"{Fore.CYAN}=== Service Management ==={ColorStyle.RESET_ALL}")
        
        # Get current status
        status_info = service_manager.get_status_info()
        running = status_info["running"]
        pid = status_info["pid"]
        auto_start = status_info["auto_start"]
        uptime = status_info.get("uptime", "N/A")
        start_time = status_info.get("start_time")
        
        # Display status information
        print("\nCurrent Status:")
        if running:
            print(f"Service status: {Fore.GREEN}RUNNING{ColorStyle.RESET_ALL}")
            print(f"Process ID: {pid}")
            if start_time:
                start_time_str = datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S")
                print(f"Started at: {start_time_str}")
            print(f"Uptime: {uptime}")
        else:
            print(f"Service status: {Fore.RED}STOPPED{ColorStyle.RESET_ALL}")
        
        print(f"Auto-start: {'Enabled' if auto_start else 'Disabled'}")
        print(f"PID file: {status_info['pid_file']}")
        print(f"Log file: {status_info['log_file']}")
        
        # Show menu options
        print("\nOptions:")
        if running:
            print("1. Stop Service")
            print("2. Restart Service")
        else:
            print("1. Start Service")
        
        print(f"3. {'Disable' if auto_start else 'Enable'} Auto-start")
        print("4. View Service Log")
        print("5. Return to Main Menu")
        
        # Get user input
        choice = prompt(
            HTML("<ansicyan>Choose an option (1-5): </ansicyan>"),
            style=cli.prompt_style
        )
        
        if choice == "1":
            if running:
                # Stop service
                print(f"\n{Fore.YELLOW}Stopping Log Collector service...{ColorStyle.RESET_ALL}")
                success, message = service_manager.stop_service()
                if success:
                    print(f"{Fore.GREEN}Service stopped successfully.{ColorStyle.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Failed to stop service: {message}{ColorStyle.RESET_ALL}")
            else:
                # Start service
                print(f"\n{Fore.YELLOW}Starting Log Collector service...{ColorStyle.RESET_ALL}")
                success, message = service_manager.start_service()
                if success:
                    print(f"{Fore.GREEN}Service started successfully.{ColorStyle.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Failed to start service: {message}{ColorStyle.RESET_ALL}")
            
            input("Press Enter to continue...")
        
        elif choice == "2" and running:
            # Restart service
            print(f"\n{Fore.YELLOW}Restarting Log Collector service...{ColorStyle.RESET_ALL}")
            success, message = service_manager.restart_service()
            if success:
                print(f"{Fore.GREEN}Service restarted successfully.{ColorStyle.RESET_ALL}")
            else:
                print(f"{Fore.RED}Failed to restart service: {message}{ColorStyle.RESET_ALL}")
            
            input("Press Enter to continue...")
        
        elif choice == "3":
            # Toggle auto-start
            new_auto_start = not auto_start
            service_manager.set_auto_start(new_auto_start)
            status = "enabled" if new_auto_start else "disabled"
            print(f"\n{Fore.GREEN}Auto-start {status}.{ColorStyle.RESET_ALL}")
            
            input("Press Enter to continue...")
        
        elif choice == "4":
            # View service log
            view_service_log(service_manager, cli)
        
        elif choice == "5":
            return
        
        else:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")

def view_service_log(service_manager, cli):
    """View the Log Collector service log.
    
    Args:
        service_manager: Service manager instance
        cli: CLI instance for header
    """
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Service Log ==={ColorStyle.RESET_ALL}")
    
    # Get log lines
    log_lines = service_manager.get_service_log(100)
    
    if not log_lines:
        print(f"\n{Fore.YELLOW}No log data available.{ColorStyle.RESET_ALL}")
    else:
        print("\nLast 100 log lines:")
        print(f"{Fore.CYAN}-------------------------------------------{ColorStyle.RESET_ALL}")
        for line in log_lines:
            line = line.strip()
            # Color-code based on log level
            if "ERROR" in line:
                print(f"{Fore.RED}{line}{ColorStyle.RESET_ALL}")
            elif "WARNING" in line:
                print(f"{Fore.YELLOW}{line}{ColorStyle.RESET_ALL}")
            elif "INFO" in line:
                print(f"{Fore.GREEN}{line}{ColorStyle.RESET_ALL}")
            else:
                print(line)
        print(f"{Fore.CYAN}-------------------------------------------{ColorStyle.RESET_ALL}")
    
    print("\nOptions:")
    print("1. Refresh")
    print("2. Return to Service Management")
    
    choice = prompt(
        HTML("<ansicyan>Choose an option (1-2): </ansicyan>"),
        style=cli.prompt_style
    )
    
    if choice == "1":
        # Refresh log
        view_service_log(service_manager, cli)
    else:
        return

def get_service_status_summary(service_manager):
    """Get a summary of the service status for display in the main menu.
    
    Args:
        service_manager: Service manager instance
        
    Returns:
        str: Formatted status summary string with color codes
    """
    # Update status
    service_manager._check_status()
    
    # Get status info
    status_info = service_manager.get_status_info()
    running = status_info["running"]
    
    if running:
        status_str = f"{Fore.GREEN}RUNNING{ColorStyle.RESET_ALL}"
        if status_info.get("uptime"):
            status_str += f" (uptime: {status_info['uptime']})"
    else:
        status_str = f"{Fore.RED}STOPPED{ColorStyle.RESET_ALL}"
    
    return status_str
