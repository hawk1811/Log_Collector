"""
CLI module for managing log aggregation rules.
"""
import json
import time
from datetime import datetime

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.formatted_text import HTML
from colorama import Fore, Style as ColorStyle

from log_collector.config import logger

def manage_aggregation_rules(source_manager, processor_manager, aggregation_manager, cli):
    """Manage log aggregation rules.
    
    Args:
        source_manager: Source manager instance
        processor_manager: Processor manager instance
        aggregation_manager: Aggregation manager instance
        cli: CLI instance for header
    """
    while True:
        clear()
        cli._print_header()
        print(f"{Fore.CYAN}=== Aggregation Rule Management ==={ColorStyle.RESET_ALL}")
        
        # Show current policies
        policies = aggregation_manager.get_all_policies()
        sources = source_manager.get_sources()
        
        if policies:
            print("\nConfigured Aggregation Rules:")
            for i, (source_id, policy) in enumerate(policies.items(), 1):
                source_name = sources[source_id]["source_name"] if source_id in sources else "Unknown"
                fields = ", ".join(policy["fields"])
                status = "Enabled" if policy.get("enabled", True) else "Disabled"
                
                print(f"{i}. {source_name} - {status}")
                print(f"   Fields: {fields}")
        else:
            print("\nNo aggregation rules configured.")
        
        print("\nOptions:")
        print("1. Create New Aggregation Rule")
        print("2. Edit Existing Rule")
        print("3. Delete Rule")
        print("4. Return to Source Management")
        
        choice = prompt(
            HTML("<ansicyan>Choose an option (1-4): </ansicyan>"),
            style=cli.prompt_style
        )
        
        if choice == "1":
            create_aggregation_rule(source_manager, processor_manager, aggregation_manager, cli)
        elif choice == "2":
            edit_aggregation_rule(source_manager, processor_manager, aggregation_manager, cli)
        elif choice == "3":
            delete_aggregation_rule(source_manager, processor_manager, aggregation_manager, cli)
        elif choice == "4":
            return
        else:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")

def create_aggregation_rule(source_manager, processor_manager, aggregation_manager, cli):
    """Create a new aggregation rule.
    
    Args:
        source_manager: Source manager instance
        processor_manager: Processor manager instance
        aggregation_manager: Aggregation manager instance
        cli: CLI instance for header
    """
    # Ensure we're using the updated terminal mode for paste functionality
    old_settings = None
    
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Create Aggregation Rule ==={ColorStyle.RESET_ALL}")
    
    # Get sources without aggregation rules
    sources = source_manager.get_sources()
    policies = aggregation_manager.get_all_policies()
    
    available_sources = {source_id: source for source_id, source in sources.items() 
                       if source_id not in policies}
    
    if not available_sources:
        print(f"{Fore.YELLOW}All sources already have aggregation rules.{ColorStyle.RESET_ALL}")
        print("You can edit or delete existing rules first.")
        input("Press Enter to continue...")
        return
    
    # Show available sources
    print("\nAvailable Sources:")
    for i, (source_id, source) in enumerate(available_sources.items(), 1):
        # Try to auto-save template
        has_template = aggregation_manager.ensure_template(source_id, processor_manager)
        template_status = " (Sample log available)" if has_template else ""
            
        print(f"{i}. {source['source_name']} ({source['source_ip']}:{source['listener_port']} {source['protocol']}){template_status}")
    
    print("\n0. Cancel")
    
    # Select source
    while True:
        choice = prompt(
            HTML("<ansicyan>Select a source: </ansicyan>"),
            style=cli.prompt_style
        )
        
        if choice == "0":
            return
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(available_sources):
                source_id = list(available_sources.keys())[index]
                source = available_sources[source_id]
                break
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
    
    # Check if we already have a template for this source
    template = aggregation_manager.get_template(source_id)
    
    if not template:
        print(f"\n{Fore.YELLOW}No log template available for this source.{ColorStyle.RESET_ALL}")
        print("We need a sample log to extract fields for aggregation.")
        print("Options:")
        print("1. Use a sample log from the queue")
        print("2. Enter a sample log manually")
        print("3. Cancel")
        
        choice = prompt(
            HTML("<ansicyan>Choose an option (1-3): </ansicyan>"),
            style=cli.prompt_style
        )
        
        if choice == "1":
            # Try to get a sample log from the queue
            if source_id in processor_manager.queues and not processor_manager.queues[source_id].empty():
                try:
                    # Get a sample log without removing it from the queue
                    sample_log = list(processor_manager.queues[source_id].queue)[0]
                    template_fields = aggregation_manager.store_log_template(source_id, sample_log)
                    print(f"{Fore.GREEN}Sample log obtained from queue.{ColorStyle.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.RED}Error getting sample log: {e}{ColorStyle.RESET_ALL}")
                    input("Press Enter to continue...")
                    return
            else:
                print(f"{Fore.RED}No logs available in the queue for this source.{ColorStyle.RESET_ALL}")
                print("Please enter a sample log manually.")
                
                print(f"\n{Fore.CYAN}Enter a sample log below. You can paste multi-line content.{ColorStyle.RESET_ALL}")
                print(f"{Fore.CYAN}Press Enter twice on an empty line when done.{ColorStyle.RESET_ALL}\n")
                
                # Collect multi-line input to support pastes
                lines = []
                while True:
                    line = prompt("", style=cli.prompt_style)
                    if not line and (not lines or not lines[-1]):
                        # Empty line after another empty line or as first input, we're done
                        break
                    lines.append(line)
                
                # Join lines for the full sample log
                sample_log = "\n".join(lines)
                
                if not sample_log:
                    print(f"{Fore.RED}Sample log cannot be empty.{ColorStyle.RESET_ALL}")
                    input("Press Enter to continue...")
                    return
                
                template_fields = aggregation_manager.store_log_template(source_id, sample_log)
        
        elif choice == "2":
            # Enter a sample log manually
            print(f"\n{Fore.CYAN}Enter a sample log below. You can paste multi-line content.{ColorStyle.RESET_ALL}")
            print(f"{Fore.CYAN}Press Enter twice on an empty line when done.{ColorStyle.RESET_ALL}\n")
            
            # Collect multi-line input to support pastes
            lines = []
            while True:
                line = prompt("", style=cli.prompt_style)
                if not line and (not lines or not lines[-1]):
                    # Empty line after another empty line or as first input, we're done
                    break
                lines.append(line)
            
            # Join lines for the full sample log
            sample_log = "\n".join(lines)
            
            if not sample_log:
                print(f"{Fore.RED}Sample log cannot be empty.{ColorStyle.RESET_ALL}")
                input("Press Enter to continue...")
                return
            
            template_fields = aggregation_manager.store_log_template(source_id, sample_log)
        
        elif choice == "3":
            return
        else:
            print(f"{Fore.RED}Invalid choice.{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")
            return
    else:
        # Use existing template
        template_fields = template["fields"]
    
    # Display the fields
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Select Fields for Aggregation ==={ColorStyle.RESET_ALL}")
    print(f"\nSource: {source['source_name']}")
    
    if not template_fields:
        print(f"{Fore.RED}No fields could be extracted from the log.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    # Display the fields in a more structured format
    print(f"\n{Fore.CYAN}Available Fields:{ColorStyle.RESET_ALL}")
    field_list = list(template_fields.keys())
    
    # Print field info in a table-like format
    print(f"\n{Fore.GREEN}{'#':<4} {'Field Name':<25} {'Type':<15} {'Value Example':<40}{ColorStyle.RESET_ALL}")
    print(f"{'-'*4} {'-'*25} {'-'*15} {'-'*40}")
    
    for i, field_name in enumerate(field_list, 1):
        field_info = template_fields[field_name]
        field_type = field_info.get("type", "unknown")
        
        # Get example with formatting if available
        if "formatted" in field_info:
            example = field_info.get("formatted", "")
        else:
            example = field_info.get("example", "")
        
        # Add length info for string fields
        if field_type == "string" and "length" in field_info:
            field_type = f"string({field_info['length']})"
        
        # Highlight special fields
        field_name_display = field_name
        if field_name in ["timestamp", "log_level", "message", "host", "source", "severity"]:
            field_name_display = f"{Fore.YELLOW}{field_name}{ColorStyle.RESET_ALL}"
        
        # Truncate long examples
        if len(str(example)) > 37:
            example = str(example)[:34] + "..."
        
        # Format the line
        print(f"{i:<4} {field_name_display:<25} {field_type:<15} {example:<40}")
    
    # Select fields for aggregation
    print("\nEnter the numbers of fields to include in the aggregation rule,")
    print("separated by commas (e.g., 1,3,5):")
    
    while True:
        field_selection = prompt(
            HTML("<ansicyan>Field selection: </ansicyan>"),
            style=cli.prompt_style
        )
        
        if not field_selection:
            print(f"{Fore.RED}You must select at least one field.{ColorStyle.RESET_ALL}")
            continue
        
        try:
            # Parse the selection
            selected_indices = [int(idx.strip()) for idx in field_selection.split(",")]
            
            # Validate indices
            if any(idx < 1 or idx > len(field_list) for idx in selected_indices):
                print(f"{Fore.RED}Invalid field number. Please try again.{ColorStyle.RESET_ALL}")
                continue
            
            # Get the selected field names
            selected_fields = [field_list[idx-1] for idx in selected_indices]
            break
        
        except ValueError:
            print(f"{Fore.RED}Invalid input format. Please use comma-separated numbers.{ColorStyle.RESET_ALL}")
    
    # Create the aggregation policy
    result = aggregation_manager.create_policy(source_id, selected_fields)
    
    if result:
        print(f"{Fore.GREEN}Aggregation rule created successfully.{ColorStyle.RESET_ALL}")
        print(f"Source: {source['source_name']}")
        print(f"Fields: {', '.join(selected_fields)}")
    else:
        print(f"{Fore.RED}Failed to create aggregation rule.{ColorStyle.RESET_ALL}")
    
    input("Press Enter to continue...")

def edit_aggregation_rule(source_manager, processor_manager, aggregation_manager, cli):
    """Edit an existing aggregation rule.
    
    Args:
        source_manager: Source manager instance
        processor_manager: Processor manager instance
        aggregation_manager: Aggregation manager instance
        cli: CLI instance for header
    """
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Edit Aggregation Rule ==={ColorStyle.RESET_ALL}")
    
    # Get sources with aggregation rules
    sources = source_manager.get_sources()
    policies = aggregation_manager.get_all_policies()
    
    if not policies:
        print(f"{Fore.YELLOW}No aggregation rules configured.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    # Show sources with policies
    print("\nConfigured Rules:")
    source_list = []
    
    for i, (source_id, policy) in enumerate(policies.items(), 1):
        source_name = sources[source_id]["source_name"] if source_id in sources else "Unknown"
        fields = ", ".join(policy["fields"])
        status = "Enabled" if policy.get("enabled", True) else "Disabled"
        
        print(f"{i}. {source_name} - {status}")
        print(f"   Fields: {fields}")
        
        source_list.append(source_id)
    
    print("\n0. Cancel")
    
    # Select source
    while True:
        choice = prompt(
            HTML("<ansicyan>Select a rule to edit: </ansicyan>"),
            style=cli.prompt_style
        )
        
        if choice == "0":
            return
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(source_list):
                source_id = source_list[index]
                source = sources.get(source_id, {"source_name": "Unknown"})
                policy = policies[source_id]
                break
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
    
    # Display the edit menu
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Edit Rule: {source['source_name']} ==={ColorStyle.RESET_ALL}")
    
    print(f"\nCurrent Configuration:")
    print(f"Status: {'Enabled' if policy.get('enabled', True) else 'Disabled'}")
    print(f"Fields: {', '.join(policy['fields'])}")
    
    print("\nEdit Options:")
    print("1. Toggle Status (Enable/Disable)")
    print("2. Change Aggregation Fields")
    print("3. Return")
    
    edit_choice = prompt(
        HTML("<ansicyan>Choose an option (1-3): </ansicyan>"),
        style=cli.prompt_style
    )
    
    if edit_choice == "1":
        # Toggle status
        current_status = policy.get("enabled", True)
        new_status = not current_status
        
        updates = {"enabled": new_status}
        result = aggregation_manager.update_policy(source_id, updates)
        
        if result:
            status_str = "enabled" if new_status else "disabled"
            print(f"{Fore.GREEN}Rule {status_str} successfully.{ColorStyle.RESET_ALL}")
        else:
            print(f"{Fore.RED}Failed to update rule status.{ColorStyle.RESET_ALL}")
    
    elif edit_choice == "2":
        # Change fields
        template = aggregation_manager.get_template(source_id)
        
        if not template or not template.get("fields"):
            print(f"{Fore.RED}No template fields available for this source.{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")
            return
        
        template_fields = template["fields"]
        
        # Display the fields in a more structured format
        print(f"\n{Fore.CYAN}Available Fields:{ColorStyle.RESET_ALL}")
        field_list = list(template_fields.keys())
        
        # Print field info in a table-like format
        print(f"\n{Fore.GREEN}{'Sel':<4} {'#':<4} {'Field Name':<25} {'Type':<15} {'Value Example':<40}{ColorStyle.RESET_ALL}")
        print(f"{'-'*4} {'-'*4} {'-'*25} {'-'*15} {'-'*40}")
        
        for i, field_name in enumerate(field_list, 1):
            field_info = template_fields[field_name]
            field_type = field_info.get("type", "unknown")
            
            # Get example with formatting if available
            if "formatted" in field_info:
                example = field_info.get("formatted", "")
            else:
                example = field_info.get("example", "")
            
            # Add length info for string fields
            if field_type == "string" and "length" in field_info:
                field_type = f"string({field_info['length']})"
            
            # Highlight special fields
            field_name_display = field_name
            if field_name in ["timestamp", "log_level", "message", "host", "source", "severity"]:
                field_name_display = f"{Fore.YELLOW}{field_name}{ColorStyle.RESET_ALL}"
            
            # Truncate long examples
            if len(str(example)) > 37:
                example = str(example)[:34] + "..."
            
            # Mark if field is currently selected
            is_selected = field_name in policy["fields"]
            selection_mark = f"{Fore.GREEN}[*]{ColorStyle.RESET_ALL}" if is_selected else "[ ]"
            
            # Format the line
            print(f"{selection_mark:<4} {i:<4} {field_name_display:<25} {field_type:<15} {example:<40}")
        
        # Select fields for aggregation
        print("\nEnter the numbers of fields to include in the aggregation rule,")
        print("separated by commas (e.g., 1,3,5):")
        
        while True:
            field_selection = prompt(
                HTML("<ansicyan>Field selection: </ansicyan>"),
                style=cli.prompt_style
            )
            
            if not field_selection:
                print(f"{Fore.RED}You must select at least one field.{ColorStyle.RESET_ALL}")
                continue
            
            try:
                # Parse the selection
                selected_indices = [int(idx.strip()) for idx in field_selection.split(",")]
                
                # Validate indices
                if any(idx < 1 or idx > len(field_list) for idx in selected_indices):
                    print(f"{Fore.RED}Invalid field number. Please try again.{ColorStyle.RESET_ALL}")
                    continue
                
                # Get the selected field names
                selected_fields = [field_list[idx-1] for idx in selected_indices]
                break
            
            except ValueError:
                print(f"{Fore.RED}Invalid input format. Please use comma-separated numbers.{ColorStyle.RESET_ALL}")
        
        # Update the fields
        if set(selected_fields) != set(policy["fields"]):
            updates = {"fields": selected_fields}
            result = aggregation_manager.update_policy(source_id, updates)
            
            if result:
                print(f"{Fore.GREEN}Aggregation fields updated successfully.{ColorStyle.RESET_ALL}")
            else:
                print(f"{Fore.RED}Failed to update aggregation fields.{ColorStyle.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}No changes were made.{ColorStyle.RESET_ALL}")
    
    input("Press Enter to continue...")
  
def delete_aggregation_rule(source_manager, processor_manager, aggregation_manager, cli):
  """Delete an aggregation rule.
  
  Args:
      source_manager: Source manager instance
      processor_manager: Processor manager instance
      aggregation_manager: Aggregation manager instance
      cli: CLI instance for header
  """
  clear()
  cli._print_header()
  print(f"{Fore.CYAN}=== Delete Aggregation Rule ==={ColorStyle.RESET_ALL}")
  
  # Get sources with aggregation rules
  sources = source_manager.get_sources()
  policies = aggregation_manager.get_all_policies()
  
  if not policies:
      print(f"{Fore.YELLOW}No aggregation rules configured.{ColorStyle.RESET_ALL}")
      input("Press Enter to continue...")
      return
  
  # Show sources with policies
  print("\nConfigured Rules:")
  source_list = []
  
  for i, (source_id, policy) in enumerate(policies.items(), 1):
      source_name = sources[source_id]["source_name"] if source_id in sources else "Unknown"
      fields = ", ".join(policy["fields"])
      status = "Enabled" if policy.get("enabled", True) else "Disabled"
      
      print(f"{i}. {source_name} - {status}")
      print(f"   Fields: {fields}")
      
      source_list.append(source_id)
  
  print("\n0. Cancel")
  
  # Select source
  while True:
      choice = prompt(
          HTML("<ansicyan>Select a rule to delete: </ansicyan>"),
          style=cli.prompt_style
      )
      
      if choice == "0":
          return
      
      try:
          index = int(choice) - 1
          if 0 <= index < len(source_list):
              source_id = source_list[index]
              source = sources.get(source_id, {"source_name": "Unknown"})
              break
          else:
              print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
      except ValueError:
          print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
  
  # Confirm deletion
  confirm = prompt(
      HTML(f"<ansicyan>Are you sure you want to delete the rule for {source['source_name']}? (y/n): </ansicyan>"),
      style=cli.prompt_style
  )
  
  if confirm.lower() != 'y':
      print(f"{Fore.YELLOW}Deletion cancelled.{ColorStyle.RESET_ALL}")
      input("Press Enter to continue...")
      return
  
  # Delete the rule
  result = aggregation_manager.delete_policy(source_id)
  
  if result:
      print(f"{Fore.GREEN}Aggregation rule deleted successfully.{ColorStyle.RESET_ALL}")
  else:
      print(f"{Fore.RED}Failed to delete aggregation rule.{ColorStyle.RESET_ALL}")
  
  input("Press Enter to continue...")
