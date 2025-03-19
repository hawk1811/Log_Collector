"""
Source management module for Log Collector.
Provides functions for adding, updating, and deleting log sources.
"""
import os
import re
import time
import json
from pathlib import Path

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.formatted_text import HTML
from colorama import Fore, Style as ColorStyle

from log_collector.config import (
    DEFAULT_UDP_PROTOCOL,
    DEFAULT_HEC_BATCH_SIZE,
    DEFAULT_FOLDER_BATCH_SIZE,
    DEFAULT_COMPRESSION_ENABLED,
    DEFAULT_COMPRESSION_LEVEL,
)

def add_source(source_manager, processor_manager, listener_manager, cli):
    """Add a new log source.
    
    Args:
        source_manager: Source manager instance
        processor_manager: Processor manager instance
        listener_manager: Listener manager instance
        cli: CLI instance for printing header
    """
    clear()
    cli._print_header()
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
    existing_ips = [src["source_ip"] for src in source_manager.get_sources().values()]
    
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
        
        # Get compression settings
        enable_compression = prompt(f"Enable compression (y/n) [{DEFAULT_COMPRESSION_ENABLED and 'y' or 'n'}]: ")
        if enable_compression.lower() == 'n':
            source_data["compression_enabled"] = False
        else:
            source_data["compression_enabled"] = True
            
            # Get compression level (1-9, with 9 being highest)
            compression_level = prompt(f"Compression level (1-9, 9=highest) [{DEFAULT_COMPRESSION_LEVEL}]: ")
            if compression_level and compression_level.isdigit() and 1 <= int(compression_level) <= 9:
                source_data["compression_level"] = int(compression_level)
            else:
                source_data["compression_level"] = DEFAULT_COMPRESSION_LEVEL
    
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
    result = source_manager.add_source(source_data)
    
    if result["success"]:
        source_id = result["source_id"]
        print(f"{Fore.GREEN}Source added successfully with ID: {source_id}{ColorStyle.RESET_ALL}")
        
        # Start newly added source by completely restarting the services
        print(f"\n{Fore.CYAN}Starting newly added source...{ColorStyle.RESET_ALL}")
        
        try:
            # Stop all services
            print(f"- Stopping all services...")
            processor_manager.stop()
            listener_manager.stop()
            
            # Start all services with new configuration
            print(f"- Starting all services with new configuration...")
            processor_manager.start()
            listener_manager.start()
            
            print(f"{Fore.GREEN}Source started successfully.{ColorStyle.RESET_ALL}")
            
            # Check if we have access to the aggregation manager
            if cli and hasattr(cli, 'aggregation_manager') and cli.aggregation_manager:
                # Add a message about log templates
                print(f"\n{Fore.CYAN}Log template information:{ColorStyle.RESET_ALL}")
                print(f"- The system will automatically capture the first log received for this source")
                print(f"- This log will be used to identify fields for aggregation rules")
                print(f"- You can view and manage fields by selecting 'Manage Sources' -> select this source -> 'Manage Aggregation Rules'")
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

def edit_source(source_id, source_manager, processor_manager, listener_manager, cli):
    """Edit a source configuration.
    
    Args:
        source_id: ID of the source to edit
        source_manager: Source manager instance
        processor_manager: Processor manager instance
        listener_manager: Listener manager instance
        cli: CLI instance for header
    """
    clear()
    cli._print_header()
    source = source_manager.get_source(source_id)
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
    existing_ips = [src["source_ip"] for src_id, src in source_manager.get_sources().items() 
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
            
        # Get compression enabled/disabled
        current_compression = source.get('compression_enabled', DEFAULT_COMPRESSION_ENABLED)
        current_compression_str = "y" if current_compression else "n"
        new_compression = prompt(f"Enable compression (y/n) [{current_compression_str}]: ")
        
        if new_compression.lower() in ['y', 'n']:
            updated_data["compression_enabled"] = (new_compression.lower() == 'y')
        
        # Only ask for compression level if compression is enabled
        if (new_compression.lower() == 'y' or (new_compression == '' and current_compression)):
            current_level = source.get('compression_level', DEFAULT_COMPRESSION_LEVEL)
            new_level = prompt(f"Compression level (1-9, 9=highest) [{current_level}]: ")
            
            if new_level and new_level.isdigit() and 1 <= int(new_level) <= 9:
                updated_data["compression_level"] = int(new_level)
    
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
        result = source_manager.update_source(source_id, updated_data)
        
        if result["success"]:
            print(f"{Fore.GREEN}Source updated successfully.{ColorStyle.RESET_ALL}")
            
            # Restart services using the same approach as in _add_source
            print(f"\n{Fore.CYAN}Applying changes...{ColorStyle.RESET_ALL}")
            
            try:
                # Stop all services
                print(f"- Stopping all services...")
                processor_manager.stop()
                listener_manager.stop()
                
                # Start all services with new configuration
                print(f"- Starting all services with new configuration...")
                processor_manager.start()
                listener_manager.start()
                
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

def delete_source(source_id, source_manager, processor_manager, listener_manager):
    """Delete a source.
    
    Args:
        source_id: ID of the source to delete
        source_manager: Source manager instance
        processor_manager: Processor manager instance
        listener_manager: Listener manager instance
    """
    source = source_manager.get_source(source_id)
    if not source:
        print(f"{Fore.RED}Source not found.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    confirm = prompt(f"Are you sure you want to delete source '{source['source_name']}'? (y/n): ")
    if confirm.lower() != 'y':
        print("Deletion cancelled.")
        input("Press Enter to continue...")
        return
    
    result = source_manager.delete_source(source_id)
    if result["success"]:
        print(f"{Fore.GREEN}Source deleted successfully.{ColorStyle.RESET_ALL}")
        
        # Restart services using the same approach as in _add_source
        print(f"\n{Fore.CYAN}Applying changes...{ColorStyle.RESET_ALL}")
        
        try:
            # Stop all services
            print(f"- Stopping all services...")
            processor_manager.stop()
            listener_manager.stop()
            
            # Start all services with new configuration
            print(f"- Starting all services with new configuration...")
            processor_manager.start()
            listener_manager.start()
            
            print(f"{Fore.GREEN}Changes applied successfully.{ColorStyle.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error applying changes: {e}{ColorStyle.RESET_ALL}")
            print(f"{Fore.YELLOW}Source deleted, but service update may be incomplete.{ColorStyle.RESET_ALL}")
            print(f"{Fore.YELLOW}You may need to restart the application to fully apply changes.{ColorStyle.RESET_ALL}")
    else:
        print(f"{Fore.RED}Failed to delete source: {result['error']}{ColorStyle.RESET_ALL}")
    
    input("Press Enter to continue...")

def view_template_fields(source_id, source_manager, aggregation_manager, cli):
    """View all fields in a log template.
    
    Args:
        source_id: Source ID to view template for
        source_manager: Source manager instance
        aggregation_manager: Aggregation manager instance
        cli: CLI instance for header
    """
    clear()
    cli._print_header()
    source = source_manager.get_source(source_id)
    
    if not source:
        print(f"{Fore.RED}Source not found.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    print(f"{Fore.CYAN}=== Log Template Fields for {source['source_name']} ==={ColorStyle.RESET_ALL}")
    
    # Get template
    template = aggregation_manager.get_template(source_id)
    if not template or "fields" not in template or not template["fields"]:
        print(f"\n{Fore.YELLOW}No template fields available for this source.{ColorStyle.RESET_ALL}")
        print("Waiting for the first log to be received...")
        input("Press Enter to continue...")
        return
    
    # Get template details
    fields = template["fields"]
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(template.get("timestamp", 0)))
    field_count = len(fields)
    
    print(f"\nTemplate captured on: {timestamp}")
    print(f"Total fields: {field_count}")
    
    if "log" in template:
        # Show the original log that was used to create the template
        print(f"\n{Fore.CYAN}Original Log Sample:{ColorStyle.RESET_ALL}")
        log_sample = template["log"]
        if isinstance(log_sample, dict):
            try:
                # Pretty-print JSON for better readability
                print(json.dumps(log_sample, indent=2)[:500])
                if len(json.dumps(log_sample, indent=2)) > 500:
                    print("... (truncated)")
            except:
                print(str(log_sample)[:500])
                if len(str(log_sample)) > 500:
                    print("... (truncated)")
        else:
            print(str(log_sample)[:500])
            if len(str(log_sample)) > 500:
                print("... (truncated)")
    
    # Display the fields in a structured table
    print(f"\n{Fore.CYAN}Extracted Fields:{ColorStyle.RESET_ALL}")
    print(f"\n{Fore.GREEN}{'Field Name':<30} {'Type':<15} {'Value Example':<40}{ColorStyle.RESET_ALL}")
    print(f"{'-'*30} {'-'*15} {'-'*40}")
    
    # First show special fields that are most important
    special_fields = ["timestamp", "message", "log_level", "severity", "level", "host", "source", "ip_address"]
    for field_name in special_fields:
        if field_name in fields:
            field_info = fields[field_name]
            field_type = field_info.get("type", "unknown")
            
            # Get example with formatting if available
            if "formatted" in field_info:
                example = field_info.get("formatted", "")
            else:
                example = field_info.get("example", "")
            
            # Add length info for string fields
            if field_type == "string" and "length" in field_info:
                field_type = f"string({field_info['length']})"
            
            # Truncate long examples
            example_str = str(example)
            if len(example_str) > 37:
                example_str = example_str[:34] + "..."
            
            # Format the line with highlighting for special fields
            print(f"{Fore.YELLOW}{field_name:<30}{ColorStyle.RESET_ALL} {field_type:<15} {example_str:<40}")
    
    # Then show all other fields
    for field_name, field_info in sorted(fields.items()):
        # Skip special fields we already showed
        if field_name in special_fields:
            continue
            
        field_type = field_info.get("type", "unknown")
        
        # Get example with formatting if available
        if "formatted" in field_info:
            example = field_info.get("formatted", "")
        else:
            example = field_info.get("example", "")
        
        # Add length info for string fields
        if field_type == "string" and "length" in field_info:
            field_type = f"string({field_info['length']})"
        
        # Truncate long examples
        example_str = str(example)
        if len(example_str) > 37:
            example_str = example_str[:34] + "..."
        
        # Format the line
        print(f"{field_name:<30} {field_type:<15} {example_str:<40}")
    
    # Show aggregation status
    policy = aggregation_manager.get_policy(source_id)
    print(f"\n{Fore.CYAN}Aggregation Status:{ColorStyle.RESET_ALL}")
    if policy:
        status = "Enabled" if policy.get("enabled", True) else "Disabled"
        fields = ", ".join(policy["fields"])
        print(f"Status: {status}")
        print(f"Aggregation Fields: {fields}")
    else:
        print("No aggregation rule configured")
    
    print("\nNote: Template is automatically created from the first log received.")
    print("To refresh template, delete it and wait for the next log.")
    
    input("\nPress Enter to continue...")

def delete_template(source_id, source_manager, aggregation_manager, cli):
    """Delete a log template.
    
    Args:
        source_id: Source ID to delete template for
        source_manager: Source manager instance
        aggregation_manager: Aggregation manager instance
        cli: CLI instance for header
    """
    clear()
    cli._print_header()
    source = source_manager.get_source(source_id)
    
    if not source:
        print(f"{Fore.RED}Source not found.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    print(f"{Fore.CYAN}=== Delete Log Template for {source['source_name']} ==={ColorStyle.RESET_ALL}")
    
    # Check if template exists
    if source_id not in aggregation_manager.templates:
        print(f"\n{Fore.YELLOW}No template exists for this source.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    # Get template details for confirmation
    template = aggregation_manager.get_template(source_id)
    if template and "fields" in template:
        field_count = len(template["fields"])
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(template.get("timestamp", 0)))
        print(f"\nTemplate details:")
        print(f"- Captured on: {timestamp}")
        print(f"- Fields: {field_count}")
    
    # Check if there's an aggregation policy
    policy = aggregation_manager.get_policy(source_id)
    if policy:
        print(f"\n{Fore.YELLOW}Warning: This source has an active aggregation rule.{ColorStyle.RESET_ALL}")
        print(f"Deleting the template will also delete the aggregation rule.")
    
    # Confirm deletion
    confirm = prompt(
        HTML("<ansicyan>Are you sure you want to delete this template? (y/n): </ansicyan>"),
        style=cli.prompt_style
    )
    
    if confirm.lower() == 'y':
        # Delete template
        result = aggregation_manager.delete_template(source_id)
        
        if result:
            print(f"\n{Fore.GREEN}Template deleted successfully.{ColorStyle.RESET_ALL}")
            print("A new template will be created when the next log is received.")
        else:
            print(f"\n{Fore.RED}Failed to delete template.{ColorStyle.RESET_ALL}")
    else:
        print(f"\n{Fore.YELLOW}Deletion cancelled.{ColorStyle.RESET_ALL}")
    
    input("Press Enter to continue...")

def delete_aggregation_rule(source_id, source_manager, aggregation_manager, cli):
    """Delete an aggregation rule.
    
    Args:
        source_id: Source ID to delete rule for
        source_manager: Source manager instance
        aggregation_manager: Aggregation manager instance
        cli: CLI instance for header
    """
    clear()
    cli._print_header()
    source = source_manager.get_source(source_id)
    
    if not source:
        print(f"{Fore.RED}Source not found.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    print(f"{Fore.CYAN}=== Delete Aggregation Rule for {source['source_name']} ==={ColorStyle.RESET_ALL}")
    
    # Check if rule exists
    policy = aggregation_manager.get_policy(source_id)
    if not policy:
        print(f"\n{Fore.YELLOW}No aggregation rule exists for this source.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    # Get policy details for confirmation
    fields = ", ".join(policy["fields"])
    status = "Enabled" if policy.get("enabled", True) else "Disabled"
    
    print(f"\nAggregation rule details:")
    print(f"- Status: {status}")
    print(f"- Fields: {fields}")
    
    # Confirm deletion
    confirm = prompt(
        HTML("<ansicyan>Are you sure you want to delete this rule? (y/n): </ansicyan>"),
        style=cli.prompt_style
    )
    
    if confirm.lower() == 'y':
        # Delete rule
        result = aggregation_manager.delete_policy(source_id)
        
        if result:
            print(f"\n{Fore.GREEN}Aggregation rule deleted successfully.{ColorStyle.RESET_ALL}")
        else:
            print(f"\n{Fore.RED}Failed to delete aggregation rule.{ColorStyle.RESET_ALL}")
    else:
        print(f"\n{Fore.YELLOW}Deletion cancelled.{ColorStyle.RESET_ALL}")
    
    input("Press Enter to continue...")

def manage_source(source_id, source_manager, processor_manager, listener_manager, cli, 
                 aggregation_manager=None, filter_manager=None):
    """Manage a specific source.
    
    Args:
        source_id: ID of the source to manage
        source_manager: Source manager instance
        processor_manager: Processor manager instance
        listener_manager: Listener manager instance
        cli: CLI instance for style and header
        aggregation_manager: Optional aggregation manager instance
        filter_manager: Optional filter manager instance
    """
    while True:
        clear()
        cli._print_header()
        source = source_manager.get_source(source_id)
        if not source:
            print(f"{Fore.RED}Source not found.{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")
            return
        
        # Auto-save template if not already saved
        if aggregation_manager:
            aggregation_manager.ensure_template(source_id, processor_manager)
        
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
        
        # Display aggregation status if available
        if aggregation_manager:
            policy = aggregation_manager.get_policy(source_id)
            has_template = source_id in aggregation_manager.templates
            
            if policy:
                status = "Enabled" if policy.get("enabled", True) else "Disabled"
                fields = ", ".join(policy["fields"])
                print(f"\n{Fore.CYAN}Aggregation Status:{ColorStyle.RESET_ALL} {status}")
                print(f"{Fore.CYAN}Aggregation Fields:{ColorStyle.RESET_ALL} {fields}")
            else:
                print(f"\n{Fore.CYAN}Aggregation Status:{ColorStyle.RESET_ALL} Not Configured")
        
        # Display filter status if available
        if filter_manager:
            filter_rules = filter_manager.get_source_filters(source_id)
            if filter_rules:
                enabled_count = sum(1 for rule in filter_rules if rule.get("enabled", True))
                print(f"\n{Fore.CYAN}Filter Rules:{ColorStyle.RESET_ALL} {enabled_count} active filters out of {len(filter_rules)} total")
                
                # Show first 2 filter rules as preview
                preview_count = min(2, len(filter_rules))
                if preview_count > 0:
                    print(f"{Fore.CYAN}Active Filters:{ColorStyle.RESET_ALL}")
                    for i, rule in enumerate(filter_rules[:preview_count]):
                        if rule.get("enabled", True):
                            print(f"  - Field: {rule['field']} = \"{rule['value']}\"")
            else:
                print(f"\n{Fore.CYAN}Filter Rules:{ColorStyle.RESET_ALL} None configured")
            
        # Display template information if available
        if aggregation_manager:
            if has_template:
                template = aggregation_manager.get_template(source_id)
                if template and "fields" in template:
                    field_count = len(template["fields"])
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(template.get("timestamp", 0)))
                    print(f"\n{Fore.CYAN}Log Template:{ColorStyle.RESET_ALL} Available ({field_count} fields extracted on {timestamp})")
                    
                    # Show top 3 most relevant fields as a preview
                    priority_fields = ["timestamp", "message", "log_level", "host", "severity", "source"]
                    shown_fields = []
                    
                    # First try priority fields
                    for field in priority_fields:
                        if field in template["fields"] and len(shown_fields) < 3:
                            value = template["fields"][field].get("example", "")
                            if len(str(value)) > 30:
                                value = str(value)[:27] + "..."
                            shown_fields.append(f"{field}={value}")
                    
                    # Then add other fields until we have 3
                    if len(shown_fields) < 3:
                        for field, info in template["fields"].items():
                            if field not in priority_fields and len(shown_fields) < 3:
                                value = info.get("example", "")
                                if len(str(value)) > 30:
                                    value = str(value)[:27] + "..."
                                shown_fields.append(f"{field}={value}")
                    
                    if shown_fields:
                        print(f"{Fore.CYAN}Sample Fields:{ColorStyle.RESET_ALL} {', '.join(shown_fields)}")
                        
                    # Add option to view all fields
                    print(f"\n{Fore.YELLOW}Use option 4 to view all template fields{ColorStyle.RESET_ALL}")
                else:
                    print(f"\n{Fore.CYAN}Log Template:{ColorStyle.RESET_ALL} Available for configuration")
            else:
                print(f"\n{Fore.YELLOW}Log Template: Waiting for first log to be received{ColorStyle.RESET_ALL}")
        
        print("\nOptions:")
        print("1. Edit Source")
        print("2. Delete Source")
        
        # Build menu based on available components
        has_aggregation = aggregation_manager is not None
        has_filtering = filter_manager is not None
        option_count = 3
        
        if has_aggregation:
            print(f"{option_count}. Manage Aggregation Rules")
            option_count += 1
            
        if has_filtering:
            print(f"{option_count}. Manage Filter Rules")
            filter_option = option_count
            option_count += 1
        
        if has_aggregation:
            print(f"{option_count}. View Log Template Fields")
            option_count += 1
            print(f"{option_count}. Delete Log Template")
            option_count += 1
        
        print(f"{option_count}. Return to Sources List")
        
        choice = prompt(
            HTML("<ansicyan>Choose an option: </ansicyan>"),
            style=cli.prompt_style
        )
        
        if choice == "1":
            edit_source(source_id, source_manager, processor_manager, listener_manager, cli)
        elif choice == "2":
            delete_source(source_id, source_manager, processor_manager, listener_manager)
            return
        elif choice == "3" and has_aggregation:
            from log_collector.cli_aggregation import create_aggregation_rule, edit_aggregation_rule
            policy = aggregation_manager.get_policy(source_id)
            if policy:
                # Edit existing rule
                edit_aggregation_rule(source_manager, processor_manager, aggregation_manager, cli)
            else:
                # Create new rule
                create_aggregation_rule(source_manager, processor_manager, aggregation_manager, cli)
        elif has_filtering and choice == str(filter_option):
            # Manage filter rules
            if has_template:
                from log_collector.cli_filters import manage_filter_rules
                manage_filter_rules(source_manager, aggregation_manager, filter_manager, cli)
            else:
                print(f"{Fore.YELLOW}No log template available. Wait for logs to be received.{ColorStyle.RESET_ALL}")
                input("Press Enter to continue...")
        elif (choice == "4" and has_aggregation and not has_filtering) or \
             (choice == "5" and has_aggregation and has_filtering):
            # View log template fields
            view_template_fields(source_id, source_manager, aggregation_manager, cli)
        elif (choice == "5" and has_aggregation and not has_filtering) or \
             (choice == "6" and has_aggregation and has_filtering):
            # Delete log template
            delete_template(source_id, source_manager, aggregation_manager, cli)
        elif choice == str(option_count):
            return
        else:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")

def manage_sources(source_manager, processor_manager, listener_manager, cli, 
                  aggregation_manager=None, filter_manager=None):
    """Manage existing sources.
    
    Args:
        source_manager: Source manager instance
        processor_manager: Processor manager instance
        listener_manager: Listener manager instance
        cli: CLI instance for style and header
        aggregation_manager: Optional aggregation manager instance
        filter_manager: Optional filter manager instance
    """
    while True:
        clear()
        cli._print_header()
        print(f"{Fore.CYAN}=== Manage Sources ==={ColorStyle.RESET_ALL}")
        
        sources = source_manager.get_sources()
        if not sources:
            print("No sources configured.")
            input("Press Enter to return to main menu...")
            return
        
        # Try to auto-save templates for all sources and track results
        template_status = {}
        if aggregation_manager:
            for source_id in sources:
                has_template = source_id in aggregation_manager.templates
                if not has_template:
                    # Try to create a template if it doesn't exist
                    has_template = aggregation_manager.ensure_template(source_id, processor_manager)
                template_status[source_id] = has_template
        
        print("\nConfigured Sources:")
        for i, (source_id, source) in enumerate(sources.items(), 1):
            # Show template status if aggregation manager is available
            template_info = ""
            if aggregation_manager:
                has_template = template_status.get(source_id, False)
                if has_template:
                    template_info = f" {Fore.GREEN}[Log template available]{ColorStyle.RESET_ALL}"
                else:
                    template_info = f" {Fore.YELLOW}[Waiting for logs]{ColorStyle.RESET_ALL}"
            
            # Show filter info if filter manager is available
            filter_info = ""
            if filter_manager:
                filter_rules = filter_manager.get_source_filters(source_id)
                if filter_rules:
                    enabled_count = sum(1 for rule in filter_rules if rule.get("enabled", True))
                    filter_info = f" {Fore.CYAN}[{enabled_count} active filters]{ColorStyle.RESET_ALL}"
            
            print(f"{i}. {source['source_name']} ({source['source_ip']}:{source['listener_port']} {source['protocol']}){template_info}{filter_info}")
        
        print("\nOptions:")
        print("0. Return to Main Menu")
        print("1-N. Select Source to Manage")
        
        # Additional options based on available managers
        additional_options = []
        
        if aggregation_manager:
            additional_options.append(("A", "Manage Aggregation Rules"))
        
        if filter_manager:
            additional_options.append(("F", "Manage Filter Rules"))
        
        if additional_options:
            print("\nOr select:")
            for key, desc in additional_options:
                print(f"{key}. {desc}")
        
        choice = prompt(
            HTML("<ansicyan>Choose an option: </ansicyan>"),
            style=cli.prompt_style
        )
        
        if choice == "0":
            return
        elif choice.upper() == "A" and aggregation_manager:
            from log_collector.cli_aggregation import manage_aggregation_rules
            manage_aggregation_rules(source_manager, processor_manager, aggregation_manager, cli)
        elif choice.upper() == "F" and filter_manager:
            from log_collector.cli_filters import manage_filter_rules
            manage_filter_rules(source_manager, aggregation_manager, filter_manager, cli)
        else:
            try:
                index = int(choice) - 1
                if 0 <= index < len(sources):
                    source_id = list(sources.keys())[index]
                    manage_source(source_id, source_manager, processor_manager, listener_manager, 
                                 cli, aggregation_manager, filter_manager)
                else:
                    print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
                    input("Press Enter to continue...")
            except ValueError:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
                input("Press Enter to continue...")
