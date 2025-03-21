"""
Command Line Interface main module for Log Collector.
Contains the core CLI class and main menu functions.
"""
import os
import sys
import signal
import time

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from colorama import init, Fore, Style as ColorStyle
from log_collector.updater import check_for_updates, restart_application



# Initialize colorama for cross-platform colored terminal output
init()

# Import CLI modules
from log_collector.cli_utils import setup_terminal, restore_terminal
from log_collector.cli_sources import add_source, manage_sources
from log_collector.cli_health import configure_health_check
from log_collector.cli_status import view_status
from log_collector.cli_auth import login_screen, change_password_screen
from log_collector.cli_service import manage_service, get_service_status_summary
from log_collector.service_manager import ServiceManager

class CLI:
    """Command Line Interface for Log Collector."""
    
    def __init__(self, source_manager, processor_manager, listener_manager, health_check, aggregation_manager=None, auth_manager=None, filter_manager=None):
        """Initialize CLI.
        
        Args:
            source_manager: Instance of SourceManager
            processor_manager: Instance of ProcessorManager
            listener_manager: Instance of LogListener
            health_check: Instance of HealthCheck
            aggregation_manager: Optional instance of AggregationManager
            auth_manager: Optional instance of AuthManager
        """
        self.source_manager = source_manager
        self.processor_manager = processor_manager
        self.listener_manager = listener_manager
        self.health_check = health_check
        self.aggregation_manager = aggregation_manager
        self.auth_manager = auth_manager
        self.filter_manager = filter_manager
        
        # Service manager for independent service control
        self.service_manager = ServiceManager()
        
        # Authentication state
        self.authenticated = False
        self.current_user = None
        
        # Define prompt style
        self.prompt_style = Style.from_dict({
            'prompt': 'ansicyan bold',
        })
        
        # Setup terminal for non-blocking input in Unix systems
        self.old_terminal_settings = None
    
    def start(self):
        """Start CLI interface."""
        clear()
        self._print_header()
        
        # Setup signal handler for clean exits
        def signal_handler(sig, frame):
            print("\n\n")
            print(f"{Fore.YELLOW}Ctrl+C detected. Do you want to exit?{ColorStyle.RESET_ALL}")
            try:
                # Ensure terminal is restored for the prompt
                if self.old_terminal_settings:
                    restore_terminal(self.old_terminal_settings)
                    self.old_terminal_settings = None
                
                confirm = prompt("Exit the application? (y/n): ")
                if confirm.lower() == 'y':
                    print(f"{Fore.CYAN}Cleaning up resources...{ColorStyle.RESET_ALL}")
                    self._clean_exit()
                    print(f"{Fore.GREEN}Graceful shutdown completed. Goodbye!{ColorStyle.RESET_ALL}")
                    sys.exit(0)
                else:
                    print(f"{Fore.GREEN}Continuing...{ColorStyle.RESET_ALL}")
                    # Re-initialize terminal settings after continuing
                    self.old_terminal_settings = setup_terminal()
                    return
            except KeyboardInterrupt:
                # If Ctrl+C is pressed during the prompt, exit immediately
                print(f"\n{Fore.CYAN}Forced exit. Cleaning up resources...{ColorStyle.RESET_ALL}")
                self._clean_exit()
                print(f"{Fore.GREEN}Graceful shutdown completed. Goodbye!{ColorStyle.RESET_ALL}")
                sys.exit(0)
        
        # Register the signal handler for SIGINT (Ctrl+C)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Handle authentication if auth_manager is provided
        if self.auth_manager:
            # Let login_screen manage its own terminal settings
            authenticated, username, needs_password_change = login_screen(self.auth_manager, self)
            
            if not authenticated:
                print(f"{Fore.RED}Authentication failed. Exiting.{ColorStyle.RESET_ALL}")
                sys.exit(1)
            
            self.authenticated = True
            self.current_user = username
            
            # Handle forced password change - function handles its own terminal settings
            if needs_password_change:
                password_changed = False
                while not password_changed:
                    password_changed = change_password_screen(self.auth_manager, username, True, self)
        
        # Initialize terminal settings for the main application after authentication
        self.old_terminal_settings = setup_terminal()
        
        # Check if the service is running
        service_running = self.service_manager.is_running()
        
        if not service_running and self.service_manager.get_auto_start():
            # Start the service if it's not running and auto-start is enabled
            print(f"{Fore.YELLOW}Starting Log Collector service...{ColorStyle.RESET_ALL}")
            success, message = self.service_manager.start_service()
            if success:
                print(f"{Fore.GREEN}Log Collector service started successfully.{ColorStyle.RESET_ALL}")
            else:
                print(f"{Fore.RED}Failed to start Log Collector service: {message}{ColorStyle.RESET_ALL}")
                print(f"{Fore.YELLOW}You can start the service manually from the Service Status menu.{ColorStyle.RESET_ALL}")
        
        print("\nPress Enter to continue to main menu...")
        input()
        
        while True:
            try:
                self._show_main_menu()
            except KeyboardInterrupt:
                # This should not be reached due to the signal handler, but just in case
                signal_handler(signal.SIGINT, None)
            except Exception as e:
                print(f"{Fore.RED}Error: {e}{ColorStyle.RESET_ALL}")
                input("Press Enter to continue...")
    
    def _print_header(self):
        """Print application header."""
        print(f"{Fore.CYAN}======================================")
        print("         LOG COLLECTOR")
        print(f"{Fore.LIGHTBLACK_EX}          K.G. @ 2025{ColorStyle.RESET_ALL}")
        print(f"{Fore.CYAN}======================================")
        print(f"Version: 1.0.0{ColorStyle.RESET_ALL}")
        print()
    
    def _show_main_menu(self):
        """Display main menu and handle commands."""
        clear()  # Ensure screen is cleared
        self._print_header()
        
        # Show logged in user if authenticated and service status
        status_line = []
        if self.authenticated and self.current_user:
            status_line.append(f"Logged in as: {Fore.GREEN}{self.current_user}{ColorStyle.RESET_ALL}")
        
        # Add service status
        service_status = get_service_status_summary(self.service_manager)
        status_line.append(f"Service: {service_status}")
        
        if status_line:
            print(" | ".join(status_line))
        
        print("\nMain Menu:")
        print("1. Add New Source")
        print("2. Manage Sources")
        print("3. Health Check Configuration")
        print("4. View Status")
        print("5. Service Management")
        
        # Add change password option if auth_manager is available
        if self.auth_manager and self.authenticated:
            print("6. Change Password")
            print("7. Check for Updates")
            print("8. Exit")
            max_option = 8
        else:
            print("6. Check for Updates")
            print("7. Exit")
            max_option = 7
        
        choice = prompt(
            HTML(f"<ansicyan>Choose an option (1-{max_option}): </ansicyan>"),
            style=self.prompt_style
        )
        
        if choice == "1":
            add_source(self.source_manager, self.processor_manager, self.listener_manager, self)
        elif choice == "2":
            manage_sources(self.source_manager, self.processor_manager, self.listener_manager, self, self.aggregation_manager, self.filter_manager)
        elif choice == "3":
            configure_health_check(self.health_check, self)
        elif choice == "4":
            view_status(self.source_manager, self.processor_manager, self.listener_manager, self.health_check, self.aggregation_manager, self.current_user)
        elif choice == "5":
            # Service management
            manage_service(self.service_manager, self)
        elif choice == "6" and self.auth_manager and self.authenticated:
            # Change password
            change_password_screen(self.auth_manager, self.current_user, False, self)
        elif (choice == "7" and self.auth_manager and self.authenticated) or (choice == "6" and (not self.auth_manager or not self.authenticated)):
            # Check for updates
            should_restart = check_for_updates(self)
            if should_restart:
                print(f"\n{Fore.GREEN}Update successful! The application will now restart...{ColorStyle.RESET_ALL}")
                print(f"{Fore.CYAN}Please wait...{ColorStyle.RESET_ALL}")
                time.sleep(2)  # Give user time to read the message
                
                self._clean_exit()
                # After clean exit, restart the application
                restart_application()
        elif (choice == "8" and self.auth_manager and self.authenticated) or (choice == "7" and (not self.auth_manager or not self.authenticated)):
            self._exit_application()
            # If we return here, it means the user canceled the exit
            return
        else:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
    
    def _exit_application(self):
        """Exit the application cleanly."""
        print(f"\n{Fore.YELLOW}Are you sure you want to exit?{ColorStyle.RESET_ALL}")
        confirm = prompt("Exit the application? (y/n): ")
        
        if confirm.lower() == 'y':
            self._clean_exit()
            print(f"{Fore.GREEN}Graceful shutdown completed. Goodbye!{ColorStyle.RESET_ALL}")
            sys.exit(0)
        else:
            print(f"{Fore.GREEN}Continuing...{ColorStyle.RESET_ALL}")
            return
            
    def _clean_exit(self):
        """Clean up resources before exiting."""
        # Only restore terminal settings - don't stop the service
        if self.old_terminal_settings:
            restore_terminal(self.old_terminal_settings)
            self.old_terminal_settings = None
        
        # Log the exit
        print(f"{Fore.CYAN}Exiting application. The service will continue running in the background.{ColorStyle.RESET_ALL}")
        
        # Check service status
        if not self.service_manager.is_running():
            print(f"{Fore.YELLOW}Note: The Log Collector service is not running.{ColorStyle.RESET_ALL}")
            print(f"{Fore.YELLOW}You can start it using 'python log_collector_service.py start' or from the Service Management menu.{ColorStyle.RESET_ALL}")
