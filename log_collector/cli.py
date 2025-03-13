"""
Command Line Interface module for Log Collector.
Provides interactive CLI menu for configuration and management.
"""
import os
import re
import sys
import time
from pathlib import Path

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from colorama import init, Fore, Style as ColorStyle

# Initialize colorama for cross-platform colored terminal output
init()

from log_collector.config import (
    logger,
    DEFAULT_UDP_PROTOCOL,
    DEFAULT_HEC_BATCH_SIZE,
    DEFAULT_FOLDER_BATCH_SIZE,
    DEFAULT_HEALTH_CHECK_INTERVAL,
)

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
    
    def start(self):
        """Start CLI interface."""
        clear()
        self._print_header()
        
        # Start component threads if there are already sources configured
        sources = self.source_manager.get_sources()
        if sources:
            self.processor_manager.start()
            self.listener_manager.start()
            print(f"{Fore.GREEN}Started with {len(sources)} configured sources{ColorStyle.RESET_ALL}")
        
        # Check for health check config
        # TODO: Load health check config from a file
        
        while True:
            try:
                self._show_main_menu()
            except KeyboardInterrupt:
                print("\nExiting...")
                break
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
        clear()
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
            self._add_source()
        elif choice == "2":
            self._manage_sources()
        elif choice == "3":
            self._configure_health_check()
        elif choice == "4":
            self._view_status()
        elif choice == "5":
            print("Exiting...")
            sys.exit(0)
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
            port = prompt("Listener Port: ")
            try:
                port = int(port)
                if 1 <= port <= 65535:
                    source_data["listener_port"] = port
                    break
                else:
                    print(f"{Fore.RED}Port must be between 1 and 65535.{ColorStyle.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid port. Please enter a valid number.{ColorStyle.RESET_ALL}")
        
        # Get protocol - simplified to accept single letter
        protocol = prompt("Protocol (u/t) [u for UDP, t for TCP]: ")
        if protocol.lower() == 't':
            source_data["protocol"] = "TCP"
        else:
            source_data["protocol"] = "UDP"
            print(f"Using protocol: UDP")
        
        # Get target type - simplified to accept single letter
        while True:
            target_type = prompt("Target Type (f/h) [f for Folder, h for HEC]: ")
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
            
            # Restart listeners and processors to apply changes
            self.processor_manager.update_processors()
            self.listener_manager.update_listeners()
            
            input("Press Enter to continue...")
        else:
            print(f"{Fore.RED}Failed to add source: {result['error']}{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")
    
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
                
                # Restart listeners and processors to apply changes
                self.processor_manager.update_processors()
                self.listener_manager.update_listeners()
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
            
            # Restart listeners and processors to apply changes
            self.processor_manager.update_processors()
            self.listener_manager.update_listeners()
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
            elif choice == "3":
                return
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
                input("Press Enter to continue...")
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
            elif choice == "2":
                return
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
                input("Press Enter to continue...")
    
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
        if self.health_check.configure(hec_url, hec_token, interval):
            print(f"{Fore.GREEN}Health check configured successfully.{ColorStyle.RESET_ALL}")
            
            # Ask to start health check
            start = prompt("Start health check monitoring now? (y/n): ")
            if start.lower() == 'y':
                if self.health_check.start():
                    print(f"{Fore.GREEN}Health check monitoring started.{ColorStyle.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Failed to start health check monitoring.{ColorStyle.RESET_ALL}")
        else:
            print(f"{Fore.RED}Failed to configure health check.{ColorStyle.RESET_ALL}")
        
        input("Press Enter to continue...")
    
    def _view_status(self):
        """View system and sources status."""
        clear()
        self._print_header()
        print(f"{Fore.CYAN}=== System Status ==={ColorStyle.RESET_ALL}")
        
        # System information
        import psutil
        import threading
        
        # CPU and memory
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        print(f"\nSystem Resources:")
        print(f"CPU Usage: {cpu_percent}%")
        print(f"Memory Usage: {memory.percent}% ({memory.used / (1024**3):.2f} GB / {memory.total / (1024**3):.2f} GB)")
        
        # Thread information
        thread_count = threading.active_count()
        print(f"Active Threads: {thread_count}")
        
        # Sources information
        sources = self.source_manager.get_sources()
        
        if sources:
            print(f"\n{Fore.CYAN}Active Sources:{ColorStyle.RESET_ALL}")
            for source_id, source in sources.items():
                # Get queue size if available
                queue_size = 0
                if source_id in self.processor_manager.queues:
                    queue_size = self.processor_manager.queues[source_id].qsize()
