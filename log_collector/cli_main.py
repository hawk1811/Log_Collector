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

# Initialize colorama for cross-platform colored terminal output
init()

# Import CLI modules
from log_collector.cli_utils import setup_terminal, restore_terminal
from log_collector.cli_sources import add_source, manage_sources
from log_collector.cli_health import configure_health_check
from log_collector.cli_status import view_status

class CLI:
    """Command Line Interface for Log Collector."""
    
    def __init__(self, source_manager, processor_manager, listener_manager, health_check, aggregation_manager=None):
        """Initialize CLI.
        
        Args:
            source_manager: Instance of SourceManager
            processor_manager: Instance of ProcessorManager
            listener_manager: Instance of LogListener
            health_check: Instance of HealthCheck
            aggregation_manager: Optional instance of AggregationManager
        """
        self.source_manager = source_manager
        self.processor_manager = processor_manager
        self.listener_manager = listener_manager
        self.health_check = health_check
        self.aggregation_manager = aggregation_manager
        
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
                confirm = prompt("Exit the application? (y/n): ")
                if confirm.lower() == 'y':
                    print(f"{Fore.CYAN}Cleaning up resources...{ColorStyle.RESET_ALL}")
                    self._clean_exit()
                    print(f"{Fore.GREEN}Graceful shutdown completed. Goodbye!{ColorStyle.RESET_ALL}")
                    sys.exit(0)
                else:
                    print(f"{Fore.GREEN}Continuing...{ColorStyle.RESET_ALL}")
                    return
            except KeyboardInterrupt:
                # If Ctrl+C is pressed during the prompt, exit immediately
                print(f"\n{Fore.CYAN}Forced exit. Cleaning up resources...{ColorStyle.RESET_ALL}")
                self._clean_exit()
                print(f"{Fore.GREEN}Graceful shutdown completed. Goodbye!{ColorStyle.RESET_ALL}")
                sys.exit(0)
        
        # Register the signal handler for SIGINT (Ctrl+C)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Start component threads if there are already sources configured
        sources = self.source_manager.get_sources()
        if sources:
            self.processor_manager.start()
            self.listener_manager.start()
            print(f"{Fore.GREEN}Started with {len(sources)} configured sources.{ColorStyle.RESET_ALL}")
        
        # Automatically start health check if configured
        if hasattr(self.health_check, 'config') and self.health_check.config is not None:
            if self.health_check.start():
                print(f"{Fore.GREEN}Health check monitoring started automatically.{ColorStyle.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}Health check is configured but failed to start.{ColorStyle.RESET_ALL}")
        
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
        print("======================================")
        print(f"Version: 1.0.0{ColorStyle.RESET_ALL}")
        print()
    
    def _show_main_menu(self):
        """Display main menu and handle commands."""
        clear()  # Ensure screen is cleared
        self._print_header()
        print("\nMain Menu:")
        print("1. Add New Source")
        print("2. Manage Sources")
        print("3. Health Check Configuration")
        print("4. View Status")
        print("5. Exit")
        
        choice = prompt(
            HTML("<ansicyan>Choose an option (1-5): </ansicyan>"),
            style=self.prompt_style
        )
        
        if choice == "1":
            add_source(self.source_manager, self.processor_manager, self.listener_manager, self)
        elif choice == "2":
            manage_sources(self.source_manager, self.processor_manager, self.listener_manager, self, self.aggregation_manager)
        elif choice == "3":
            configure_health_check(self.health_check, self)
        elif choice == "4":
            view_status(self.source_manager, self.processor_manager, self.listener_manager, self.health_check)
        elif choice == "5":
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
        print(f"{Fore.CYAN}Shutting down services...{ColorStyle.RESET_ALL}")
        
        # Restore terminal settings
        restore_terminal(self.old_terminal_settings)
        
        # Stop health check if running
        if hasattr(self.health_check, 'running') and self.health_check.running:
            print("- Stopping health check...")
            self.health_check.stop()
        
        # Stop processor manager
        print("- Stopping processors...")
        self.processor_manager.stop()
        
        # Stop listener manager
        print("- Stopping listeners...")
        self.listener_manager.stop()
        
        print(f"{Fore.CYAN}All services stopped.{ColorStyle.RESET_ALL}")
