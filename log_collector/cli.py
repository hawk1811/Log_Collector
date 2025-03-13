"""
Command Line Interface module for Log Collector.
Provides interactive CLI menu for configuration and management.
"""
import os
import re
import sys
import time
import threading
import signal
from pathlib import Path
from datetime import datetime

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from colorama import init, Fore, Style as ColorStyle

# Initialize colorama for cross-platform colored terminal output
init()

# Try to import curses, but provide fallback for Windows
try:
    import curses
    CURSES_AVAILABLE = True
except ImportError:
    CURSES_AVAILABLE = False

import psutil
from log_collector.config import (
    logger,
    DEFAULT_UDP_PROTOCOL,
    DEFAULT_HEC_BATCH_SIZE,
    DEFAULT_FOLDER_BATCH_SIZE,
    DEFAULT_HEALTH_CHECK_INTERVAL,
)
from log_collector.auth import AuthManager

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
        self.auth_manager = AuthManager()
        
        # Define prompt style
        self.prompt_style = Style.from_dict({
            'prompt': 'ansicyan bold',
        })
        
        # Flag to track if user is authenticated
        self.is_authenticated = False
        self.current_user = None
        
        # For live status display
        self.status_running = False
        self.status_thread = None
    
    def _authenticate_user(self):
        """Authenticate user before allowing access to the application."""
        max_attempts = 3
        attempt = 0
        
        while attempt < max_attempts:
            print(f"{Fore.CYAN}=== Authentication Required ==={ColorStyle.RESET_ALL}")
            print(f"Please log in to continue. Default credentials: admin/password")
            print(f"Note: You will be required to change the default password after first login.")
            
            username = prompt("Username: ")
            password = prompt("Password: ", is_password=True)
            
            success, message, force_change = self.auth_manager.authenticate(username, password)
            
            if success:
                self.is_authenticated = True
                self.current_user = username
                print(f"{Fore.GREEN}{message}{ColorStyle.RESET_ALL}")
                
                # If password change is required
                if force_change:
                    print(f"{Fore.YELLOW}You must change your password before continuing.{ColorStyle.RESET_ALL}")
                    if not self._change_password(force_change=True):
                        # If password change failed, authentication fails
                        return False
                
                return True
            else:
                print(f"{Fore.RED}{message}{ColorStyle.RESET_ALL}")
                attempt += 1
                
                if attempt < max_attempts:
                    print(f"{Fore.YELLOW}Attempts remaining: {max_attempts - attempt}{ColorStyle.RESET_ALL}")
                    time.sleep(1)
        
        print(f"{Fore.RED}Maximum authentication attempts exceeded.{ColorStyle.RESET_ALL}")
        return False
    
    def _change_password(self, force_change=False):
        """Change user password.
        
        Args:
            force_change: If True, user cannot cancel the operation
            
        Returns:
            bool: True if password was changed successfully
        """
        if not self.is_authenticated:
            print(f"{Fore.RED}You must be logged in to change password.{ColorStyle.RESET_ALL}")
            return False
        
        clear()
        self._print_header()
        print(f"{Fore.CYAN}=== Change Password ==={ColorStyle.RESET_ALL}")
        print("Password requirements:")
        print("- At least 12 characters long")
        print("- At least one uppercase letter")
        print("- At least one digit")
        print("- At least one special character")
        
        # Get current password
        old_password = prompt("Current Password: ", is_password=True)
        
        # Get new password
        while True:
            new_password = prompt("New Password: ", is_password=True)
            confirm_password = prompt("Confirm New Password: ", is_password=True)
            
            if new_password != confirm_password:
                print(f"{Fore.RED}Passwords do not match. Please try again.{ColorStyle.RESET_ALL}")
                continue
            
            # If user can cancel and enters empty password
            if not force_change and not new_password:
                print(f"{Fore.YELLOW}Password change cancelled.{ColorStyle.RESET_ALL}")
                return False
            
            # If password change is forced, don't allow empty password
            if force_change and not new_password:
                print(f"{Fore.RED}Password cannot be empty. You must change your password.{ColorStyle.RESET_ALL}")
                continue
            
            # Change password
            success, message = self.auth_manager.change_password(
                self.current_user, old_password, new_password
            )
            
            if success:
                print(f"{Fore.GREEN}{message}{ColorStyle.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}{message}{ColorStyle.RESET_ALL}")
                
                if "Invalid username or password" in message:
                    # If current password is wrong, give option to try again or cancel
                    if not force_change:
                        retry = prompt("Would you like to try again? (y/n): ")
                        if retry.lower() != 'y':
                            return False
                        old_password = prompt("Current Password: ", is_password=True)
                    else:
                        # If forced, must try again
                        old_password = prompt("Current Password: ", is_password=True)
                else:
                    # Other issues like password complexity
                    if not force_change:
                        retry = prompt("Would you like to try again? (y/n): ")
                        if retry.lower() != 'y':
                            return False
    
    def start(self):
        """Start CLI interface."""
        clear()
        self._print_header()
        
        # Authenticate user before proceeding
        if not self._authenticate_user():
            print(f"{Fore.RED}Authentication failed. Exiting...{ColorStyle.RESET_ALL}")
            sys.exit(1)
        
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
        print(f"\nLogged in as: {Fore.GREEN}{self.current_user}{ColorStyle.RESET_ALL}")
        print("\nMain Menu:")
        print("1. Add New Source")
        print("2. Manage Sources")
        print("3. Health Check Configuration")
        print("4. View Live Status")
        print("5. Change Password")
        print("6. Exit")
        
        choice = prompt(
            HTML("<ansicyan>Choose an option (1-6): </ansicyan>"),
            style=self.prompt_style
        )
        
        if choice == "1":
            self._add_source()
        elif choice == "2":
            self._manage_sources()
        elif choice == "3":
            self._configure_health_check()
        elif choice == "4":
            self._view_live_status()
        elif choice == "5":
            self._change_password()
        elif choice == "6":
            self._exit_application()
            # If we return here, it means the user canceled the exit
            return
        else:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
    
    def _add_source(self):
        """Add a new log source."""
        clear()
        self._print_header()
        print(f"{Fore.CYAN}=== Add New Source ==={ColorStyle.RESET_ALL}")
        
        source_data = {}
        
        # Get source name
        source_data["source_name"] = prompt("Source Name: ")
        if not source_data["source_name"]:
            print(f"{Fore.RED}Source name cannot be empty.{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")
            return
        
        # Get source IP
        ip_pattern = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
        
        # Check if IP already exists in any source
        existing_ips = [src["source_ip"] for src in self.source_manager.get_sources().values()]
        
        while True:
            source_data["source_ip"] = prompt("Source IP: ")
            
            # Check if the IP is already in use
            if source_data["source_ip"] in existing_ips:
                print(f"{Fore.RED}This IP is already used by another source. Please enter a different IP.{ColorStyle.RESET_ALL}")
                continue
                
            if re.match(ip_pattern, source_data["source_ip"]):
                # Validate each octet
                octets = [int(octet) for octet in source_data["source_ip"].split(".")]
                if all(0 <= octet <= 255 for octet in octets):
                    break
            print(f"{Fore.RED}Invalid IP address. Please enter a valid IPv4 address.{ColorStyle.RESET_ALL}")
        
        # Get listener port
        while True:
            port = prompt("Listener Port [514]: ")
            try:
                if not port:  # If user just presses Enter, use 514 as default
                    port = 514
                    source_data["listener_port"] = port
                    break
                else:
                    port = int(port)
                    if 1 <= port <= 65535:
                        source_data["listener_port"] = port
                        break
                    else:
                        print(f"{Fore.RED}Port must be between 1 and 65535.{ColorStyle.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid port. Please enter a valid number.{ColorStyle.RESET_ALL}")
        
        # Get protocol - simplified to accept single letter with UDP as default
        protocol = prompt("Protocol (u-UDP, t-TCP) [UDP]: ")
        if protocol.lower() == 't':
            source_data["protocol"] = "TCP"
        else:
            source_data["protocol"] = "UDP"
            print(f"Using protocol: UDP")
        
        # Get target type - simplified to accept single letter
        while True:
            target_type = prompt("Target Type (f-Folder, h-HEC): ")
            if target_type.lower() == 'f':
                source_data["target_type"] = "FOLDER"
                break
            elif target_type.lower() == 'h':
                source_data["target_type"] = "HEC"
                break
            print(f"{Fore.RED}Invalid target type. Please enter f for Folder or h for HEC.{ColorStyle.RESET_ALL}")
        
        # Get target-specific settings
        if source_data["target_type"] == "FOLDER":
            # Get folder path with improved guidance
            print(f"\n{Fore.CYAN}Folder Path Examples:{ColorStyle.RESET_ALL}")
            print("  - Local folder: C:\\logs\\collector")
            print("  - Network share: \\\\server\\share\\logs")
            print("  - Linux path: /var/log/collector")
            
            while True:
                folder_path = prompt("\nFolder Path: ")
                path = Path(folder_path)
                
                # First check if the path exists
                if not path.exists():
                    try:
                        os.makedirs(path, exist_ok=True)
                        print(f"{Fore.GREEN}Created folder: {path}{ColorStyle.RESET_ALL}")
                    except Exception as e:
                        print(f"{Fore.RED}Error creating folder: {e}{ColorStyle.RESET_ALL}")
                        print(f"{Fore.YELLOW}Please ensure the path is valid and you have permission to create it.{ColorStyle.RESET_ALL}")
                        continue
                
                # Check if folder is writable
                try:
                    test_file = path / ".test_write_access"
                    with open(test_file, "w") as f:
                        f.write("test")
                    os.remove(test_file)
                    source_data["folder_path"] = str(path)
                    print(f"{Fore.GREEN}Folder is accessible and writable.{ColorStyle.RESET_ALL}")
                    break
                except Exception as e:
                    print(f"{Fore.RED}Folder is not writable: {e}{ColorStyle.RESET_ALL}")
                    print(f"{Fore.YELLOW}Please ensure you have write permissions to this folder.{ColorStyle.RESET_ALL}")
            
            # Get batch size
            batch_size = prompt(f"Batch Size [{DEFAULT_FOLDER_BATCH_SIZE}]: ")
            if batch_size and batch_size.isdigit() and int(batch_size) > 0:
                source_data["batch_size"] = int(batch_size)
            else:
                source_data["batch_size"] = DEFAULT_FOLDER_BATCH_SIZE
        
        elif source_data["target_type"] == "HEC":
            # Get HEC URL
            while True:
                hec_url = prompt("HEC URL: ")
                if hec_url.startswith(("http://", "https://")):
                    source_data["hec_url"] = hec_url
                    break
                print(f"{Fore.RED}Invalid URL. Please enter a valid URL starting with http:// or https://.{ColorStyle.RESET_ALL}")
            
            # Get HEC token
            hec_token = prompt("HEC Token: ")
            if not hec_token:
                print(f"{Fore.RED}HEC token cannot be empty.{ColorStyle.RESET_ALL}")
                input("Press Enter to continue...")
                return
            source_data["hec_token"] = hec_token
            
            # Get batch size
            batch_size = prompt(f"Batch Size [{DEFAULT_HEC_BATCH_SIZE}]: ")
            if batch_size and batch_size.isdigit() and int(batch_size) > 0:
                source_data["batch_size"] = int(batch_size)
            else:
                source_data["batch_size"] = DEFAULT_HEC_BATCH_SIZE
        
        # Add the source
        print(f"\n{Fore.CYAN}Validating source configuration...{ColorStyle.RESET_ALL}")
        result = self.source_manager.add_source(source_data)
        
        if result["success"]:
            print(f"{Fore.GREEN}Source added successfully with ID: {result['source_id']}{ColorStyle.RESET_ALL}")
            
            # Start newly added source by completely restarting the services
            print(f"\n{Fore.CYAN}Starting newly added source...{ColorStyle.RESET_ALL}")
            
            try:
                # Stop all services
                print(f"- Stopping all services...")
                self.processor_manager.stop()
                self.listener_manager.stop()
                
                # Start all services with new configuration
                print(f"- Starting all services with new configuration...")
                self.processor_manager.start()
                self.listener_manager.start()
                
                print(f"{Fore.GREEN}Source started successfully.{ColorStyle.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}Error starting services: {e}{ColorStyle.RESET_ALL}")
                print(f"{Fore.YELLOW}Source configuration saved, but service could not be started.{ColorStyle.RESET_ALL}")
                print(f"{Fore.YELLOW}You may need to restart the application to fully apply changes.{ColorStyle.RESET_ALL}")
        else:
            print(f"{Fore.RED}Failed to add source: {result['error']}{ColorStyle.RESET_ALL}")
        
        print("\nReturning to main menu...")
        input("Press Enter to continue...")
        clear()  # Ensure screen is cleared before returning
        return  # Return to previous menu
    
    def _manage_sources(self):
        """Manage existing sources."""
        while True:
            clear()
            self._print_header()
            print(f"{Fore.CYAN}=== Manage Sources ==={ColorStyle.RESET_ALL}")
            
            sources = self.source_manager.get_sources()
            if not sources:
                print("No sources configured.")
                input("Press Enter to return to main menu...")
                return
            
            print("\nConfigured Sources:")
            for i, (source_id, source) in enumerate(sources.items(), 1):
                print(f"{i}. {source['source_name']} ({source['source_ip']}:{source['listener_port']} {source['protocol']})")
            
            print("\nOptions:")
            print("0. Return to Main Menu")
            print("1-N. Select Source to Manage")
            
            choice = prompt(
                HTML("<ansicyan>Choose an option: </ansicyan>"),
                style=self.prompt_style
            )
            
            if choice == "0":
                return
            
            try:
                index = int(choice) - 1
                if 0 <= index < len(sources):
                    source_id = list(sources.keys())[index]
                    self._manage_source(source_id)
                else:
                    print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
                    input("Press Enter to continue...")
            except ValueError:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
                input("Press Enter to continue...")
    
    def _manage_source(self, source_id):
        """Manage a specific source."""
        while True:
            clear()
            self._print_header()
            source = self.source_manager.get_source(source_id)
            if not source:
                print(f"{Fore.RED}Source not found.{ColorStyle.RESET_ALL}")
                input("Press Enter to continue...")
                return
            
            print(f"{Fore.CYAN}=== Manage Source: {source['source_name']} ==={ColorStyle.RESET_ALL}")
            print(f"\nSource ID: {source_id}")
            print(f"Source Name: {source['source_name']}")
            print(f"Source IP: {source['source_ip']}")
            print(f"Listener Port: {source['listener_port']}")
            print(f"Protocol: {source['protocol']}")
            print(f"Target Type: {source['target_type']}")
            
            if source['target_type'] == "FOLDER":
                print(f"Folder Path: {source['folder_path']}")
            elif source['target_type'] == "HEC":
                print(f"HEC URL: {source['hec_url']}")
                print(f"HEC Token: {'*' * 10}")
            
            print(f"Batch Size: {source.get('batch_size', 'Default')}")
            
            print("\nOptions:")
            print("1. Edit Source")
            print("2. Delete Source")
            print("3. Return to Sources List")
            
            choice = prompt(
                HTML("<ansicyan>Choose an option (1-3): </ansicyan>"),
                style=self.prompt_style
            )
            
            if choice == "1":
                self._edit_source(source_id)
            elif choice == "2":
                self._delete_source(source_id)
                return
            elif choice == "3":
                return
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
                input("Press Enter to continue...")
    
    def _edit_source(self, source_id):
        """Edit a source configuration."""
        clear()
        self._print_header()
        source = self.source_manager.get_source(source_id)
        if not source:
            print(f"{Fore.RED}Source not found.{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")
            return
        
        print(f"{Fore.CYAN}=== Edit Source: {source['source_name']} ==={ColorStyle.RESET_ALL}")
        print("Leave fields blank to keep current values.")
        
        # Create a copy for updates
        updated_data = {}
        
        # Get source name
        current_name = source['source_name']
        new_name = prompt(f"Source Name [{current_name}]: ")
        if new_name:
            updated_data["source_name"] = new_name
        
        # Get source IP
        current_ip = source['source_ip']
        ip_pattern = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
        
        # Check if IP already exists in any OTHER source
        existing_ips = [src["source_ip"] for src_id, src in self.source_manager.get_sources().items() 
                       if src_id != source_id]
        
        while True:
            new_ip = prompt(f"Source IP [{current_ip}]: ")
            if not new_ip:
                break
            
            # Check if the IP is already in use by another source
            if new_ip in existing_ips:
                print(f"{Fore.RED}This IP is already used by another source. Please enter a different IP.{ColorStyle.RESET_ALL}")
                continue
                
            if re.match(ip_pattern, new_ip):
                # Validate each octet
                octets = [int(octet) for octet in new_ip.split(".")]
                if all(0 <= octet <= 255 for octet in octets):
                    updated_data["source_ip"] = new_ip
                    break
            
            print(f"{Fore.RED}Invalid IP address. Please enter a valid IPv4 address.{ColorStyle.RESET_ALL}")
        
        # Get listener port
        current_port = source['listener_port']
        while True:
            new_port = prompt(f"Listener Port [{current_port}]: ")
            if not new_port:
                break
            
            try:
                port = int(new_port)
                if 1 <= port <= 65535:
                    updated_data["listener_port"] = port
                    break
                else:
                    print(f"{Fore.RED}Port must be between 1 and 65535.{ColorStyle.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid port. Please enter a valid number.{ColorStyle.RESET_ALL}")
        
        # Get protocol - simplified to accept single letter
        current_protocol = source['protocol']
        new_protocol = prompt(f"Protocol (u/t) [current: {current_protocol}]: ")
        if new_protocol:
            if new_protocol.lower() == 't':
                updated_data["protocol"] = "TCP"
            elif new_protocol.lower() == 'u':
                updated_data["protocol"] = "UDP"
        
        # Target type cannot be changed, but target settings can be updated
        if source['target_type'] == "FOLDER":
            # Get folder path with improved guidance
            current_path = source['folder_path']
            print(f"\n{Fore.CYAN}Current folder path: {current_path}{ColorStyle.RESET_ALL}")
            print(f"\n{Fore.CYAN}Folder Path Examples:{ColorStyle.RESET_ALL}")
            print("  - Local folder: C:\\logs\\collector")
            print("  - Network share: \\\\server\\share\\logs")
            print("  - Linux path: /var/log/collector")
            
            new_path = prompt(f"\nNew Folder Path (or leave blank to keep current): ")
            if new_path:
                path = Path(new_path)
                if not path.exists():
                    try:
                        os.makedirs(path, exist_ok=True)
                        print(f"{Fore.GREEN}Created folder: {path}{ColorStyle.RESET_ALL}")
                    except Exception as e:
                        print(f"{Fore.RED}Error creating folder: {e}{ColorStyle.RESET_ALL}")
                        print(f"{Fore.YELLOW}Please ensure the path is valid and you have permission to create it.{ColorStyle.RESET_ALL}")
                        input("Press Enter to continue...")
                        return
                
                # Check if folder is writable
                try:
                    test_file = path / ".test_write_access"
                    with open(test_file, "w") as f:
                        f.write("test")
                    os.remove(test_file)
                    updated_data["folder_path"] = str(path)
                    print(f"{Fore.GREEN}Folder is accessible and writable.{ColorStyle.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.RED}Folder is not writable: {e}{ColorStyle.RESET_ALL}")
                    print(f"{Fore.YELLOW}Please ensure you have write permissions to this folder.{ColorStyle.RESET_ALL}")
                    input("Press Enter to continue...")
                    return
            
            # Get batch size
            current_batch = source.get('batch_size', DEFAULT_FOLDER_BATCH_SIZE)
            new_batch = prompt(f"Batch Size [{current_batch}]: ")
            if new_batch and new_batch.isdigit() and int(new_batch) > 0:
                updated_data["batch_size"] = int(new_batch)
        
        elif source['target_type'] == "HEC":
            # Get HEC URL
            current_url = source['hec_url']
            while True:
                new_url = prompt(f"HEC URL [{current_url}]: ")
                if not new_url:
                    break
                
                if new_url.startswith(("http://", "https://")):
                    updated_data["hec_url"] = new_url
                    break
                
                print(f"{Fore.RED}Invalid URL. Please enter a valid URL starting with http:// or https://.{ColorStyle.RESET_ALL}")
            
            # Get HEC token
            new_token = prompt("HEC Token (leave blank to keep current): ")
            if new_token:
                updated_data["hec_token"] = new_token
            
            # Get batch size
            current_batch = source.get('batch_size', DEFAULT_HEC_BATCH_SIZE)
            new_batch = prompt(f"Batch Size [{current_batch}]: ")
            if new_batch and new_batch.isdigit() and int(new_batch) > 0:
                updated_data["batch_size"] = int(new_batch)
        
        # Update the source if changes were made
        if updated_data:
            print(f"\n{Fore.CYAN}Updating source configuration...{ColorStyle.RESET_ALL}")
            result = self.source_manager.update_source(source_id, updated_data)
            
            if result["success"]:
                print(f"{Fore.GREEN}Source updated successfully.{ColorStyle.RESET_ALL}")
                
                # Restart services using the same approach as in _add_source
                print(f"\n{Fore.CYAN}Applying changes...{ColorStyle.RESET_ALL}")
                
                try:
                    # Stop all services
                    print(f"- Stopping all services...")
                    self.processor_manager.stop()
                    self.listener_manager.stop()
                    
                    # Start all services with new configuration
                    print(f"- Starting all services with new configuration...")
                    self.processor_manager.start()
                    self.listener_manager.start()
                    
                    print(f"{Fore.GREEN}Changes applied successfully.{ColorStyle.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.RED}Error applying changes: {e}{ColorStyle.RESET_ALL}")
                    print(f"{Fore.YELLOW}Source configuration saved, but service update may be incomplete.{ColorStyle.RESET_ALL}")
                    print(f"{Fore.YELLOW}You may need to restart the application to fully apply changes.{ColorStyle.RESET_ALL}")
            else:
                print(f"{Fore.RED}Failed to update source: {result['error']}{ColorStyle.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}No changes were made.{ColorStyle.RESET_ALL}")
        
        input("Press Enter to continue...")
    
    def _delete_source(self, source_id):
        """Delete a source."""
        source = self.source_manager.get_source(source_id)
        if not source:
            print(f"{Fore.RED}Source not found.{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")
            return
        
        confirm = prompt(f"Are you sure you want to delete source '{source['source_name']}'? (y/n): ")
        if confirm.lower() != 'y':
            print("Deletion cancelled.")
            input("Press Enter to continue...")
            return
        
        result = self.source_manager.delete_source(source_id)
        if result["success"]:
            print(f"{Fore.GREEN}Source deleted successfully.{ColorStyle.RESET_ALL}")
            
            # Restart services using the same approach as in _add_source
            print(f"\n{Fore.CYAN}Applying changes...{ColorStyle.RESET_ALL}")
            
            try:
                # Stop all services
                print(f"- Stopping all services...")
                self.processor_manager.stop()
                self.listener_manager.stop()
                
                # Start all services with new configuration
                print(f"- Starting all services with new configuration...")
                self.processor_manager.start()
                self.listener_manager.start()
                
                print(f"{Fore.GREEN}Changes applied successfully.{ColorStyle.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}Error applying changes: {e}{ColorStyle.RESET_ALL}")
                print(f"{Fore.YELLOW}Source deleted, but service update may be incomplete.{ColorStyle.RESET_ALL}")
                print(f"{Fore.YELLOW}You may need to restart the application to fully apply changes.{ColorStyle.RESET_ALL}")
        else:
            print(f"{Fore.RED}Failed to delete source: {result['error']}{ColorStyle.RESET_ALL}")
        
        input("Press Enter to continue...")
    
    def _configure_health_check(self):
        """Configure health check monitoring."""
        clear()
        self._print_header()
        print(f"{Fore.CYAN}=== Health Check Configuration ==={ColorStyle.RESET_ALL}")
        
        # Check if health check is already configured
        is_configured = hasattr(self.health_check, 'config') and self.health_check.config is not None
        is_running = is_configured and self.health_check.running
        
        if is_configured:
            config = self.health_check.config
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
                style=self.prompt_style
            )
            
            if choice == "1":
                self._update_health_check()
                return  # Return after update to prevent menu stacking
            elif choice == "2":
                if is_running:
                    self.health_check.stop()
                    print(f"{Fore.YELLOW}Health check monitoring stopped.{ColorStyle.RESET_ALL}")
                else:
                    if self.health_check.start():
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
                self._configure_health_check()  # Recursive call to show the menu again
                return
        else:
            print("Health check is not configured.")
            print("\nOptions:")
            print("1. Configure Health Check")
            print("2. Return to Main Menu")
            
            choice = prompt(
                HTML("<ansicyan>Choose an option (1-2): </ansicyan>"),
                style=self.prompt_style
            )
            
            if choice == "1":
                self._update_health_check()
                return  # Return after update to prevent menu stacking
            elif choice == "2":
                clear()  # Clear screen when returning
                return
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
                input("Press Enter to continue...")
                self._configure_health_check()  # Recursive call to show the menu again
                return
                
    def _update_health_check(self):
        """Update health check configuration."""
        clear()
        self._print_header()
        print(f"{Fore.CYAN}=== Configure Health Check ==={ColorStyle.RESET_ALL}")
        
        # Check if health check is already configured
        is_configured = hasattr(self.health_check, 'config') and self.health_check.config is not None
        current_url = self.health_check.config['hec_url'] if is_configured else ""
        current_token = self.health_check.config['hec_token'] if is_configured else ""
        current_interval = self.health_check.config['interval'] if is_configured else DEFAULT_HEALTH_CHECK_INTERVAL
        
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
        was_running = hasattr(self.health_check, 'running') and self.health_check.running
        
        # Stop health check if it's running
        if was_running:
            self.health_check.stop()
        
        if self.health_check.configure(hec_url, hec_token, interval):
            print(f"{Fore.GREEN}Health check configured successfully.{ColorStyle.RESET_ALL}")
            
            # Auto-start health check
            if self.health_check.start():
                print(f"{Fore.GREEN}Health check monitoring started.{ColorStyle.RESET_ALL}")
            else:
                print(f"{Fore.RED}Failed to start health check monitoring.{ColorStyle.RESET_ALL}")
        else:
            print(f"{Fore.RED}Failed to configure health check.{ColorStyle.RESET_ALL}")
            
            # Restore previous health check state if possible
            if was_running and hasattr(self.health_check, 'config') and self.health_check.config is not None:
                if self.health_check.start():
                    print(f"{Fore.YELLOW}Restored previous health check configuration.{ColorStyle.RESET_ALL}")
        
        input("Press Enter to continue...")
        clear()  # Clear screen when returning
        return
           
    def _view_live_status(self):
        """View system and sources status with live updates."""
        # Use curses-based display if available, otherwise use simple console-based display
        if CURSES_AVAILABLE:
            self._view_live_status_curses()
        else:
            self._view_live_status_simple()
    
    def _view_live_status_simple(self):
        """Simple live status display for Windows systems without curses."""
        self.status_running = True
        
        # Store stats for each source
        source_stats = {}
        
        print(f"{Fore.CYAN}=== LIVE STATUS DISPLAY ==={ColorStyle.RESET_ALL}")
        print("Press Ctrl+C to return to the main menu.")
        print("")
        
        try:
            while self.status_running:
                # Clear screen (Windows-compatible)
                os.system('cls' if os.name == 'nt' else 'clear')
                
                # Print title and current time
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"{Fore.CYAN}=== LOG COLLECTOR - LIVE STATUS ==={ColorStyle.RESET_ALL}")
                print(f"Time: {current_time}")
                print("Press Ctrl+C to return to the main menu.")
                print("")
                
                # System information
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                print(f"{Fore.CYAN}SYSTEM RESOURCES:{ColorStyle.RESET_ALL}")
                
                # CPU with color
                cpu_color = Fore.GREEN if cpu_percent < 70 else (Fore.YELLOW if cpu_percent < 90 else Fore.RED)
                print(f"  CPU Usage: {cpu_color}{cpu_percent}%{ColorStyle.RESET_ALL}")
                
                # Memory with color
                mem_color = Fore.GREEN if memory.percent < 70 else (Fore.YELLOW if memory.percent < 90 else Fore.RED)
                print(f"  Memory: {mem_color}{memory.percent}%{ColorStyle.RESET_ALL} ({memory.used // (1024**2)} MB / {memory.total // (1024**2)} MB)")
                
                # Disk with color
                disk_color = Fore.GREEN if disk.percent < 70 else (Fore.YELLOW if disk.percent < 90 else Fore.RED)
                print(f"  Disk: {disk_color}{disk.percent}%{ColorStyle.RESET_ALL} ({disk.used // (1024**3)} GB / {disk.total // (1024**3)} GB)")
                
                thread_count = threading.active_count()
                print(f"  Active Threads: {thread_count}")
                print("")
                
                # Health check status
                print(f"{Fore.CYAN}HEALTH CHECK:{ColorStyle.RESET_ALL}")
                is_configured = hasattr(self.health_check, 'config') and self.health_check.config is not None
                is_running = is_configured and self.health_check.running
                
                if is_configured:
                    hc_color = Fore.GREEN if is_running else Fore.RED
                    print(f"  Status: {hc_color}{'Running' if is_running else 'Stopped'}{ColorStyle.RESET_ALL}")
                    
                    if is_running:
                        interval = self.health_check.config['interval']
                        print(f"  Interval: {interval} seconds")
                else:
                    print(f"  {Fore.YELLOW}Not Configured{ColorStyle.RESET_ALL}")
                
                print("")
                
                # Sources information
                sources = self.source_manager.get_sources()
                
                if sources:
                    print(f"{Fore.CYAN}SOURCES STATUS:{ColorStyle.RESET_ALL}")
                    print(f"  {'ID':<36} {'NAME':<15} {'TARGET':<8} {'QUEUE':<8} {'THREADS':<8} {'TOTAL LOGS':<12} {'STATUS':<8}")
                    print(f"  {'-' * 95}")
                    
                    for source_id, source in sources.items():
                        # Initialize stats if not exist
                        if source_id not in source_stats:
                            source_stats[source_id] = {"processed_logs": 0}
                        
                        # Get current stats
                        stats = self.processor_manager.get_source_stats(source_id)
                        
                        # Update our stored stats if newer
                        if stats["processed_logs"] > source_stats[source_id]["processed_logs"]:
                            source_stats[source_id] = stats
                        
                        # Get display values
                        name = source["source_name"][:15]
                        target_type = source["target_type"][:8]
                        queue_size = stats["queue_size"]
                        active_processors = stats["active_processors"]
                        processed_logs = stats["processed_logs"]
                        
                        # Check if listener is active
                        listener_port = source["listener_port"]
                        listener_protocol = source["protocol"]
                        listener_key = f"{listener_protocol}:{listener_port}"
                        listener_active = listener_key in self.listener_manager.listeners and self.listener_manager.listeners[listener_key].is_alive()
                        
                        # Set status and color
                        if listener_active and active_processors > 0:
                            status = "ACTIVE"
                            status_color = Fore.GREEN
                        elif listener_active:
                            status = "PARTIAL"
                            status_color = Fore.YELLOW
                        else:
                            status = "INACTIVE"
                            status_color = Fore.RED
                        
                        # Queue size color
                        queue_color = Fore.GREEN if queue_size < 1000 else (Fore.YELLOW if queue_size < 5000 else Fore.RED)
                        
                        # Format the row
                        print(f"  {source_id:<36} {name:<15} {target_type:<8} {queue_color}{queue_size:<8}{ColorStyle.RESET_ALL} {active_processors:<8} {processed_logs:<12} {status_color}{status:<8}{ColorStyle.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}No sources configured.{ColorStyle.RESET_ALL}")
                
                # Sleep briefly before next update
                time.sleep(1)
                
        except KeyboardInterrupt:
            # User pressed Ctrl+C to exit
            self.status_running = False
            # Clear screen before returning to menu
            os.system('cls' if os.name == 'nt' else 'clear')

    def _view_live_status_curses(self):
        """View live system and sources status using curses for Unix systems."""
        try:
            # Initialize curses
            stdscr = curses.initscr()
            curses.start_color()
            curses.use_default_colors()
            curses.curs_set(0)  # Hide cursor
            curses.noecho()
            curses.cbreak()
            stdscr.keypad(True)
            stdscr.timeout(500)  # Set getch timeout to 500ms
            
            # Define color pairs
            curses.init_pair(1, curses.COLOR_GREEN, -1)  # Green text
            curses.init_pair(2, curses.COLOR_RED, -1)    # Red text
            curses.init_pair(3, curses.COLOR_CYAN, -1)   # Cyan text
            curses.init_pair(4, curses.COLOR_YELLOW, -1) # Yellow text
            
            # Colors
            GREEN = curses.color_pair(1)
            RED = curses.color_pair(2)
            CYAN = curses.color_pair(3)
            YELLOW = curses.color_pair(4)
            NORMAL = curses.A_NORMAL
            BOLD = curses.A_BOLD
            
            # Start live update
            self.status_running = True
            max_y, max_x = stdscr.getmaxyx()
            
            # Store stats for each source
            source_stats = {}
            
            while self.status_running:
                try:
                    # Clear screen
                    stdscr.clear()
                    
                    # Update max size in case terminal was resized
                    max_y, max_x = stdscr.getmaxyx()
                    
                    # Get current time
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Print header
                    stdscr.addstr(0, 0, "LOG COLLECTOR - LIVE STATUS", CYAN | BOLD)
                    stdscr.addstr(0, max_x - len(current_time) - 1, current_time)
                    stdscr.addstr(1, 0, "Press any key to return to main menu.")
                    
                    # System information
                    cpu_percent = psutil.cpu_percent(interval=0.1)
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage('/')
                    
                    # Print system info
                    row = 3
                    stdscr.addstr(row, 0, "SYSTEM RESOURCES:", CYAN | BOLD)
                    row += 1
                    
                    cpu_str = f"CPU Usage: {cpu_percent}%"
                    cpu_color = GREEN if cpu_percent < 70 else (YELLOW if cpu_percent < 90 else RED)
                    stdscr.addstr(row, 2, cpu_str, cpu_color)
                    row += 1
                    
                    mem_str = f"Memory: {memory.percent}% ({memory.used // (1024**2)} MB / {memory.total // (1024**2)} MB)"
                    mem_color = GREEN if memory.percent < 70 else (YELLOW if memory.percent < 90 else RED)
                    stdscr.addstr(row, 2, mem_str, mem_color)
                    row += 1
                    
                    disk_str = f"Disk: {disk.percent}% ({disk.used // (1024**3)} GB / {disk.total // (1024**3)} GB)"
                    disk_color = GREEN if disk.percent < 70 else (YELLOW if disk.percent < 90 else RED)
                    stdscr.addstr(row, 2, disk_str, disk_color)
                    row += 1
                    
                    thread_count = threading.active_count()
                    stdscr.addstr(row, 2, f"Active Threads: {thread_count}")
                    row += 2
                    
                    # Health check status
                    stdscr.addstr(row, 0, "HEALTH CHECK:", CYAN | BOLD)
                    row += 1
                    
                    is_configured = hasattr(self.health_check, 'config') and self.health_check.config is not None
                    is_running = is_configured and self.health_check.running
                    
                    if is_configured:
                        hc_str = f"Status: {'Running' if is_running else 'Stopped'}"
                        hc_color = GREEN if is_running else RED
                        stdscr.addstr(row, 2, hc_str, hc_color)
                        row += 1
                        
                        if is_running:
                            interval = self.health_check.config['interval']
                            stdscr.addstr(row, 2, f"Interval: {interval} seconds")
                            row += 1
                    else:
                        stdscr.addstr(row, 2, "Not Configured", YELLOW)
                        row += 1
                    
                    # Sources information
                    row += 1
                    sources = self.source_manager.get_sources()
                    
                    if sources:
                        stdscr.addstr(row, 0, "SOURCES STATUS:", CYAN | BOLD)
                        row += 1
                        
                        # Table header
                        header_format = f"{'ID':<8} {'NAME':<15} {'TARGET':<8} {'QUEUE':<8} {'THREADS':<8} {'TOTAL LOGS':<12} {'STATUS':<8}"
                        stdscr.addstr(row, 2, header_format, BOLD)
                        row += 1
                        stdscr.addstr(row, 2, "-" * (len(header_format)))
                        row += 1
                        
                        # Get stats for each source
                        for source_id, source in sources.items():
                            # Initialize stats if not exist
                            if source_id not in source_stats:
                                source_stats[source_id] = {"processed_logs": 0}
                            
                            # Get current stats
                            stats = self.processor_manager.get_source_stats(source_id)
                            
                            # Update our stored stats if newer
                            if stats["processed_logs"] > source_stats[source_id]["processed_logs"]:
                                source_stats[source_id] = stats
                            
                            # Get display values
                            name = source["source_name"][:15]  # Truncate if too long
                            target_type = source["target_type"][:8]
                            queue_size = stats["queue_size"]
                            active_processors = stats["active_processors"]
                            processed_logs = stats["processed_logs"]
                            
                            # Check if listener is active
                            listener_port = source["listener_port"]
                            listener_protocol = source["protocol"]
                            listener_key = f"{listener_protocol}:{listener_port}"
                            listener_active = listener_key in self.listener_manager.listeners and self.listener_manager.listeners[listener_key].is_alive()
                            
                            # Set status and color
                            if listener_active and active_processors > 0:
                                status = "ACTIVE"
                                status_color = GREEN
                            elif listener_active:
                                status = "PARTIAL"
                                status_color = YELLOW
                            else:
                                status = "INACTIVE"
                                status_color = RED
                            
                            # Queue size color
                            queue_color = GREEN if queue_size < 1000 else (YELLOW if queue_size < 5000 else RED)
                            
                            # Print source row
                            id_short = source_id[:7]  # Truncate ID to first 7 chars
                            
                            # Format the row
                            stdscr.addstr(row, 2, f"{id_short:<8}", NORMAL)
                            stdscr.addstr(f"{name:<15}", NORMAL)
                            stdscr.addstr(f"{target_type:<8}", NORMAL)
                            stdscr.addstr(f"{queue_size:<8}", queue_color)
                            stdscr.addstr(f"{active_processors:<8}", NORMAL)
                            stdscr.addstr(f"{processed_logs:<12}", NORMAL)
                            stdscr.addstr(f"{status:<8}", status_color)
                            
                            row += 1
                            
                            # Check if we're running out of screen space
                            if row >= max_y - 2:
                                stdscr.addstr(row, 2, "... more sources not shown (screen too small) ...", YELLOW)
                                break
                    else:
                        stdscr.addstr(row, 2, "No sources configured.", YELLOW)
                    
                    # Refresh the screen
                    stdscr.refresh()
                    
                    # Check for key press
                    key = stdscr.getch()
                    if key != -1:  # Any key pressed
                        self.status_running = False
                        break
                    
                    # Sleep briefly before next update
                    time.sleep(0.5)
                    
                except Exception as e:
                    # Log error but continue
                    logger.error(f"Error in live status display: {e}")
                    time.sleep(1)
        
        except Exception as e:
            # Log the error
            logger.error(f"Error initializing curses: {e}")
        
        finally:
            # Clean up curses
            if 'stdscr' in locals():
                stdscr.keypad(False)
            curses.nocbreak()
            curses.echo()
            curses.endwin()
            self.status_running = False
            
            # Give terminal a moment to reset
            time.sleep(0.5)

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
        
        # Stop status display if running
        if self.status_running:
            self.status_running = False
            if self.status_thread and self.status_thread.is_alive():
                self.status_thread.join(timeout=2)
        
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
