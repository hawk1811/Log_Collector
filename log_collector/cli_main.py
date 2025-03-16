"""
Command Line Interface main module for Log Collector.
Contains the core CLI class and main menu functions.
"""
import os
import sys
import signal
import time
import json
import subprocess
import platform
from pathlib import Path

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
from log_collector.config import DATA_DIR

class CLI:
    """Command Line Interface for Log Collector."""
    
    def __init__(self, source_manager, processor_manager, listener_manager, health_check):
        """Initialize CLI.
        
        Args:
            source_manager: Instance of SourceManager
            processor_manager: Instance of ProcessorManager
            listener_manager: Instance of LogListener
            health_check: Instance of HealthCheck
        """
        self.source_manager = source_manager
        self.processor_manager = processor_manager
        self.listener_manager = listener_manager
        self.health_check = health_check
        
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
                    print(f"{Fore.CYAN}Exiting CLI...{ColorStyle.RESET_ALL}")
                    self._clean_exit()
                    print(f"{Fore.GREEN}Goodbye!{ColorStyle.RESET_ALL}")
                    sys.exit(0)
                else:
                    print(f"{Fore.GREEN}Continuing...{ColorStyle.RESET_ALL}")
                    return
            except KeyboardInterrupt:
                # If Ctrl+C is pressed during the prompt, exit immediately
                print(f"\n{Fore.CYAN}Forced exit.{ColorStyle.RESET_ALL}")
                self._clean_exit()
                print(f"{Fore.GREEN}Goodbye!{ColorStyle.RESET_ALL}")
                sys.exit(0)
        
        # Register the signal handler for SIGINT (Ctrl+C)
        signal.signal(signal.SIGINT, signal_handler)
        
        print("\nWelcome to Log Collector CLI")
        print("This interface allows you to manage log collection sources and control the service.")
        
        # Check service status
        service_status = self._get_service_status()
        
        if service_status["running"]:
            print(f"\n{Fore.GREEN}Log Collector Service is running.{ColorStyle.RESET_ALL}")
            print(f"Processing {service_status.get('sources_count', 0)} sources")
        else:
            print(f"\n{Fore.RED}Log Collector Service is not running.{ColorStyle.RESET_ALL}")
            print("You can start it from the Service Management menu.")
        
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
    
    def _get_service_status(self):
        """Get current service status."""
        # Default status (not running)
        status = {
            "running": False,
            "sources_count": 0,
            "processor_running": False,
            "listener_running": False,
            "health_check_running": False,
            "timestamp": time.time(),
            "pid": None
        }
        
        # Check if PID file exists
        pid_file = DATA_DIR / "logcollector.pid"
        if not pid_file.exists():
            return status
        
        # Read PID
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            
            # Check if process is running
            try:
                os.kill(pid, 0)  # This raises an exception if process doesn't exist
                status["running"] = True
                status["pid"] = pid
            except OSError:
                # Process not running
                return status
            
            # Read status file if available
            status_file = DATA_DIR / "service_status.json"
            if status_file.exists():
                try:
                    with open(status_file, "r") as f:
                        file_status = json.load(f)
                    
                    # Update status with file information
                    status.update(file_status)
                except:
                    # Failed to read status file
                    pass
        
        except (ValueError, IOError):
            # Invalid PID file
            pass
        
        return status
    
    def _show_main_menu(self):
        """Display main menu and handle commands."""
        clear()  # Ensure screen is cleared
        self._print_header()
        
        # Get service status
        service_status = self._get_service_status()
        
        # Display service status summary
        if service_status["running"]:
            print(f"Service: {Fore.GREEN}Running{ColorStyle.RESET_ALL} (PID: {service_status.get('pid', 'Unknown')})")
            print(f"Sources: {service_status.get('sources_count', 0)}")
        else:
            print(f"Service: {Fore.RED}Stopped{ColorStyle.RESET_ALL}")
        
        print("\nMain Menu:")
        print("1. Add New Source")
        print("2. Manage Sources")
        print("3. Health Check Configuration")
        print("4. Service Management")
        print("5. View Status")
        print("6. Exit")
        
        choice = prompt(
            HTML("<ansicyan>Choose an option (1-6): </ansicyan>"),
            style=self.prompt_style
        )
        
        if choice == "1":
            add_source(self.source_manager, self.processor_manager, self.listener_manager, self)
        elif choice == "2":
            manage_sources(self.source_manager, self.processor_manager, self.listener_manager, self)
        elif choice == "3":
            configure_health_check(self.health_check, self)
        elif choice == "4":
            self._manage_service()
        elif choice == "5":
            view_status(self.source_manager, self.processor_manager, self.listener_manager, self.health_check)
        elif choice == "6":
            self._exit_application()
            # If we return here, it means the user canceled the exit
            return
        else:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
    
    def _manage_service(self):
        """Service management menu."""
        while True:
            clear()
            self._print_header()
            print(f"{Fore.CYAN}=== Service Management ==={ColorStyle.RESET_ALL}")
            
            # Get service status
            service_status = self._get_service_status()
            
            # Display current status
            if service_status["running"]:
                status_color = Fore.GREEN
                status_text = "Running"
            else:
                status_color = Fore.RED
                status_text = "Stopped"
            
            print(f"\nStatus: {status_color}{status_text}{ColorStyle.RESET_ALL}")
            
            if service_status["running"]:
                print(f"PID: {service_status.get('pid', 'Unknown')}")
                print(f"Sources: {service_status.get('sources_count', 0)}")
                print(f"Processor: {'Running' if service_status.get('processor_running', False) else 'Stopped'}")
                print(f"Listener: {'Running' if service_status.get('listener_running', False) else 'Stopped'}")
                print(f"Health Check: {'Running' if service_status.get('health_check_running', False) else 'Stopped'}")
                last_update = service_status.get('timestamp', 0)
                print(f"Last Update: {time.ctime(last_update)}")
            
            print("\nOptions:")
            
            if service_status["running"]:
                print("1. Stop Service")
            else:
                print("1. Start Service")
            
            print("2. Install as System Service")
            print("3. Remove System Service")
            print("4. Return to Main Menu")
            
            choice = prompt(
                HTML("<ansicyan>Choose an option (1-4): </ansicyan>"),
                style=self.prompt_style
            )
            
            if choice == "1":
                if service_status["running"]:
                    # Stop service
                    print(f"\n{Fore.CYAN}Stopping Log Collector Service...{ColorStyle.RESET_ALL}")
                    try:
                        result = subprocess.run(
                            [sys.executable, "-m", "log_collector.service", "stop"],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        print(f"{Fore.GREEN}Service stopped successfully.{ColorStyle.RESET_ALL}")
                    except subprocess.CalledProcessError as e:
                        print(f"{Fore.RED}Error stopping service: {e}{ColorStyle.RESET_ALL}")
                        print(e.stderr)
                else:
                    # Start service
                    print(f"\n{Fore.CYAN}Starting Log Collector Service...{ColorStyle.RESET_ALL}")
                    try:
                        # Start in background
                        if platform.system() == "Windows":
                            # Use subprocess.Popen on Windows to avoid blocking
                            subprocess.Popen(
                                [sys.executable, "-m", "log_collector.service", "run"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW
                            )
                        else:
                            # Use daemon mode on Unix
                            subprocess.run(
                                [sys.executable, "-m", "log_collector.service", "run", "--daemon"],
                                check=True
                            )
                        
                        print(f"{Fore.GREEN}Service started successfully.{ColorStyle.RESET_ALL}")
                    except subprocess.CalledProcessError as e:
                        print(f"{Fore.RED}Error starting service: {e}{ColorStyle.RESET_ALL}")
                
                input("\nPress Enter to continue...")
            
            elif choice == "2":
                # Install as system service
                print(f"\n{Fore.CYAN}Installing Log Collector as system service...{ColorStyle.RESET_ALL}")
                print(f"{Fore.YELLOW}This operation requires administrative privileges.{ColorStyle.RESET_ALL}")
                
                confirm = prompt("Continue with installation? (y/n): ")
                if confirm.lower() != 'y':
                    continue
                
                try:
                    # On Windows, elevate privileges if needed
                    if platform.system() == "Windows":
                        try:
                            # Try to check if we have admin rights
                            import ctypes
                            if not ctypes.windll.shell32.IsUserAnAdmin():
                                print(f"{Fore.YELLOW}This operation requires administrative privileges.{ColorStyle.RESET_ALL}")
                                print("Please run the command 'log_collector.service install' as Administrator.")
                                input("\nPress Enter to continue...")
                                continue
                        except:
                            pass
                    
                    result = subprocess.run(
                        [sys.executable, "-m", "log_collector.service", "install"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    print(f"{Fore.GREEN}Service installed successfully.{ColorStyle.RESET_ALL}")
                    print(result.stdout)
                except subprocess.CalledProcessError as e:
                    print(f"{Fore.RED}Error installing service: {e}{ColorStyle.RESET_ALL}")
                    print(e.stderr)
                
                input("\nPress Enter to continue...")
            
            elif choice == "3":
                # Remove system service
                print(f"\n{Fore.CYAN}Removing Log Collector system service...{ColorStyle.RESET_ALL}")
                print(f"{Fore.YELLOW}This operation requires administrative privileges.{ColorStyle.RESET_ALL}")
                
                confirm = prompt("Continue with removal? (y/n): ")
                if confirm.lower() != 'y':
                    continue
                
                try:
                    # On Windows, elevate privileges if needed
                    if platform.system() == "Windows":
                        try:
                            # Try to check if we have admin rights
                            import ctypes
                            if not ctypes.windll.shell32.IsUserAnAdmin():
                                print(f"{Fore.YELLOW}This operation requires administrative privileges.{ColorStyle.RESET_ALL}")
                                print("Please run the command 'log_collector.service uninstall' as Administrator.")
                                input("\nPress Enter to continue...")
                                continue
                        except:
                            pass
                    
                    result = subprocess.run(
                        [sys.executable, "-m", "log_collector.service", "uninstall"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    print(f"{Fore.GREEN}Service removed successfully.{ColorStyle.RESET_ALL}")
                    print(result.stdout)
                except subprocess.CalledProcessError as e:
                    print(f"{Fore.RED}Error removing service: {e}{ColorStyle.RESET_ALL}")
                    print(e.stderr)
                
                input("\nPress Enter to continue...")
            
            elif choice == "4":
                # Return to main menu
                break
            
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
                input("Press Enter to continue...")
    
    def _exit_application(self):
        """Exit the application cleanly."""
        print(f"\n{Fore.YELLOW}Are you sure you want to exit?{ColorStyle.RESET_ALL}")
        
        service_status = self._get_service_status()
        if service_status["running"]:
            print(f"{Fore.CYAN}Note: The Log Collector Service will continue running in the background.{ColorStyle.RESET_ALL}")
        
        confirm = prompt("Exit the application? (y/n): ")
        
        if confirm.lower() == 'y':
            self._clean_exit()
            print(f"{Fore.GREEN}Goodbye!{ColorStyle.RESET_ALL}")
            sys.exit(0)
        else:
            print(f"{Fore.GREEN}Continuing...{ColorStyle.RESET_ALL}")
            return
            
    def _clean_exit(self):
        """Clean up resources before exiting."""
        # Just restore terminal settings
        restore_terminal(self.old_terminal_settings)
