"""
CLI module for managing log filter rules.
"""
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.formatted_text import HTML
from colorama import Fore, Style as ColorStyle

from log_collector.config import logger

def manage_filter_rules(source_manager, aggregation_manager, filter_manager, cli):
    """Manage filter rules for all sources.
    
    Args:
        source_manager: Source manager instance
        aggregation_manager: Aggregation manager instance
        filter_manager: Filter manager instance
        cli: CLI instance for header
    """
    while True:
        clear()
        cli._print_header()
        print(f"{Fore.CYAN}=== Filter Rule Management ==={ColorStyle.RESET_ALL}")
        
        # Show current filters
        filters = filter_manager.get_all_filters()
        sources = source_manager.get_sources()
        
        if filters:
            print("\nConfigured Filter Rules:")
            for i, (source_id, filter_rules) in enumerate(filters.items(), 1):
                source_name = sources[source_id]["source_name"] if source_id in sources else "Unknown"
                enabled_count = sum(1 for rule in filter_rules if rule.get("enabled", True))
                total_count = len(filter_rules)
                
                print(f"{i}. {source_name} ({enabled_count}/{total_count} active filters)")
                
                # Display filter details
                for j, rule in enumerate(filter_rules, 1):
                    status = "Enabled" if rule.get("enabled", True) else "Disabled"
                    status_color = Fore.GREEN if rule.get("enabled", True) else Fore.YELLOW
                    print(f"   {j}. Field: {rule['field']} | Value: \"{rule['value']}\" | Status: {status_color}{status}{ColorStyle.RESET_ALL}")
        else:
            print("\nNo filter rules configured.")
        
        print("\nOptions:")
        print("1. Add Filter Rule")
        print("2. Edit Filter Rule")
        print("3. Remove Filter Rule")
        print("4. Return to Source Management")
        
        choice = prompt(
            HTML("<ansicyan>Choose an option (1-4): </ansicyan>"),
            style=cli.prompt_style
        )
        
        if choice == "1":
            add_filter_rule(source_manager, aggregation_manager, filter_manager, cli)
        elif choice == "2":
            edit_filter_rule(source_manager, aggregation_manager, filter_manager, cli)
        elif choice == "3":
            remove_filter_rule(source_manager, aggregation_manager, filter_manager, cli)
        elif choice == "4":
            return
        else:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
            input("Press Enter to continue...")

def add_filter_rule(source_manager, aggregation_manager, filter_manager, cli):
    """Add a new filter rule.
    
    Args:
        source_manager: Source manager instance
        aggregation_manager: Aggregation manager instance
        filter_manager: Filter manager instance
        cli: CLI instance for header
    """
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Add Filter Rule ==={ColorStyle.RESET_ALL}")
    
    # Get sources with templates
    sources = source_manager.get_sources()
    available_sources = {}
    
    for source_id, source in sources.items():
        if aggregation_manager and source_id in aggregation_manager.templates:
            available_sources[source_id] = source
    
    if not available_sources:
        print(f"{Fore.YELLOW}No sources with extracted fields available.{ColorStyle.RESET_ALL}")
        print("Wait for log templates to be extracted before configuring filters.")
        input("Press Enter to continue...")
        return
    
    # Show available sources
    print("\nAvailable Sources:")
    for i, (source_id, source) in enumerate(available_sources.items(), 1):
        # Show current filter count
        filter_count = len(filter_manager.get_source_filters(source_id))
        filter_info = f" ({filter_count} filters)" if filter_count > 0 else ""
        print(f"{i}. {source['source_name']}{filter_info}")
    
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
    
    # Get template for this source
    template = aggregation_manager.get_template(source_id)
    if not template or not template.get("fields"):
        print(f"{Fore.RED}No field template available for this source.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    template_fields = template["fields"]
    
    # Display fields to choose from
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Select Field for Filter: {source['source_name']} ==={ColorStyle.RESET_ALL}")
    
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
    
    # Get existing filters to show what's already filtered
    existing_filters = filter_manager.get_source_filters(source_id)
    if existing_filters:
        print(f"\n{Fore.YELLOW}Existing Filters:{ColorStyle.RESET_ALL}")
        for i, filter_rule in enumerate(existing_filters, 1):
            status = "Enabled" if filter_rule.get("enabled", True) else "Disabled"
            status_color = Fore.GREEN if filter_rule.get("enabled", True) else Fore.YELLOW
            print(f"  {i}. Field: {filter_rule['field']} | Value: \"{filter_rule['value']}\" | Status: {status_color}{status}{ColorStyle.RESET_ALL}")
    
    print("\n0. Cancel")
    
    # Select field
    while True:
        choice = prompt(
            HTML("<ansicyan>Select field number to filter on: </ansicyan>"),
            style=cli.prompt_style
        )
        
        if choice == "0":
            return
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(field_list):
                field_name = field_list[index]
                field_info = template_fields[field_name]
                example = field_info.get("example", "")
                
                # Check if this field already has a filter
                has_filter = False
                for filter_rule in existing_filters:
                    if filter_rule["field"] == field_name:
                        print(f"{Fore.YELLOW}This field already has a filter. Choose Edit Filter to modify it.{ColorStyle.RESET_ALL}")
                        has_filter = True
                        break
                
                if has_filter:
                    input("Press Enter to continue...")
                    return
                
                break
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
    
    # Get value to filter
    print(f"\n{Fore.CYAN}Enter value to filter for field \"{field_name}\":{ColorStyle.RESET_ALL}")
    print(f"Example value: {example}")
    
    filter_value = prompt(
        HTML("<ansicyan>Filter value: </ansicyan>"),
        style=cli.prompt_style
    )
    
    if not filter_value:
        print(f"{Fore.RED}Filter value cannot be empty.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    # Confirm
    print(f"\n{Fore.CYAN}Filter Summary:{ColorStyle.RESET_ALL}")
    print(f"Source: {source['source_name']}")
    print(f"Field: {field_name}")
    print(f"Filter logs where {field_name} = \"{filter_value}\"")
    
    confirm = prompt(
        HTML("<ansicyan>Add this filter? (y/n): </ansicyan>"),
        style=cli.prompt_style
    )
    
    if confirm.lower() != 'y':
        print(f"{Fore.YELLOW}Filter creation cancelled.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    # Add the filter
    result = filter_manager.add_filter(source_id, field_name, filter_value)
    
    if result:
        print(f"{Fore.GREEN}Filter rule created successfully.{ColorStyle.RESET_ALL}")
    else:
        print(f"{Fore.RED}Failed to create filter rule.{ColorStyle.RESET_ALL}")
    
    input("Press Enter to continue...")

def edit_filter_rule(source_manager, aggregation_manager, filter_manager, cli):
    """Edit an existing filter rule.
    
    Args:
        source_manager: Source manager instance
        aggregation_manager: Aggregation manager instance
        filter_manager: Filter manager instance
        cli: CLI instance for header
    """
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Edit Filter Rule ==={ColorStyle.RESET_ALL}")
    
    # Get sources with filters
    filters = filter_manager.get_all_filters()
    sources = source_manager.get_sources()
    
    if not filters:
        print(f"{Fore.YELLOW}No filter rules configured.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    # Show sources with filters
    print("\nSources with Filters:")
    source_list = []
    
    for i, (source_id, filter_rules) in enumerate(filters.items(), 1):
        if source_id in sources:
            source_name = sources[source_id]["source_name"]
            enabled_count = sum(1 for rule in filter_rules if rule.get("enabled", True))
            total_count = len(filter_rules)
            
            print(f"{i}. {source_name} ({enabled_count}/{total_count} active filters)")
            source_list.append(source_id)
    
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
            if 0 <= index < len(source_list):
                source_id = source_list[index]
                source = sources.get(source_id, {"source_name": "Unknown"})
                break
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
    
    # Show filter rules for the selected source
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Filter Rules for {source['source_name']} ==={ColorStyle.RESET_ALL}")
    
    filter_rules = filter_manager.get_source_filters(source_id)
    
    if not filter_rules:
        print(f"{Fore.YELLOW}No filter rules configured for this source.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    print(f"\n{Fore.CYAN}Select a filter rule to edit:{ColorStyle.RESET_ALL}")
    
    for i, rule in enumerate(filter_rules, 1):
        status = "Enabled" if rule.get("enabled", True) else "Disabled"
        status_color = Fore.GREEN if rule.get("enabled", True) else Fore.YELLOW
        print(f"{i}. Field: {rule['field']} | Value: \"{rule['value']}\" | Status: {status_color}{status}{ColorStyle.RESET_ALL}")
    
    print("\nA. Clear all filters")
    print("0. Cancel")
    
    # Select filter rule
    while True:
        choice = prompt(
            HTML("<ansicyan>Select a filter rule or action: </ansicyan>"),
            style=cli.prompt_style
        )
        
        if choice == "0":
            return
        elif choice.upper() == "A":
            # Clear all filters
            confirm = prompt(
                HTML("<ansicyan>Are you sure you want to clear all filters? (y/n): </ansicyan>"),
                style=cli.prompt_style
            )
            
            if confirm.lower() == 'y':
                result = filter_manager.clear_filters(source_id)
                
                if result:
                    print(f"{Fore.GREEN}All filters cleared successfully.{ColorStyle.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Failed to clear filters.{ColorStyle.RESET_ALL}")
                
                input("Press Enter to continue...")
                return
            else:
                continue
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(filter_rules):
                selected_rule = filter_rules[index]
                field_name = selected_rule["field"]
                
                # Confirm removal
                confirm = prompt(
                    HTML(f"<ansicyan>Are you sure you want to remove the filter for field \"{field_name}\"? (y/n): </ansicyan>"),
                    style=cli.prompt_style
                )
                
                if confirm.lower() == 'y':
                    result = filter_manager.remove_filter(source_id, field_name)
                    
                    if result:
                        print(f"{Fore.GREEN}Filter removed successfully.{ColorStyle.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Failed to remove filter.{ColorStyle.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}Removal cancelled.{ColorStyle.RESET_ALL}")
                
                input("Press Enter to continue...")
                return
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
            
    input("Press Enter to continue...")
    
    print("\n0. Cancel")
    
    # Select filter rule
    while True:
        choice = prompt(
            HTML("<ansicyan>Select a filter rule: </ansicyan>"),
            style=cli.prompt_style
        )
        
        if choice == "0":
            return
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(filter_rules):
                selected_rule = filter_rules[index]
                field_name = selected_rule["field"]
                current_value = selected_rule["value"]
                is_enabled = selected_rule.get("enabled", True)
                break
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
    
    # Show edit options
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Edit Filter Rule ==={ColorStyle.RESET_ALL}")
    print(f"\nSource: {source['source_name']}")
    print(f"Field: {field_name}")
    print(f"Current Value: \"{current_value}\"")
    print(f"Status: {Fore.GREEN if is_enabled else Fore.YELLOW}{is_enabled and 'Enabled' or 'Disabled'}{ColorStyle.RESET_ALL}")
    
    print("\nEdit Options:")
    print("1. Change Filter Value")
    print("2. Toggle Enabled/Disabled")
    print("3. Return")
    
    edit_choice = prompt(
        HTML("<ansicyan>Choose an option (1-3): </ansicyan>"),
        style=cli.prompt_style
    )
    
    if edit_choice == "1":
        # Change filter value
        new_value = prompt(
            HTML(f"<ansicyan>New value (current: \"{current_value}\"): </ansicyan>"),
            style=cli.prompt_style
        )
        
        if new_value and new_value != current_value:
            result = filter_manager.add_filter(source_id, field_name, new_value)
            
            if result:
                print(f"{Fore.GREEN}Filter value updated successfully.{ColorStyle.RESET_ALL}")
            else:
                print(f"{Fore.RED}Failed to update filter value.{ColorStyle.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}No changes made.{ColorStyle.RESET_ALL}")
    
    elif edit_choice == "2":
        # Toggle enabled/disabled
        result = filter_manager.toggle_filter(source_id, field_name)
        
        if result:
            new_status = not is_enabled
            status_str = "enabled" if new_status else "disabled"
            print(f"{Fore.GREEN}Filter {status_str} successfully.{ColorStyle.RESET_ALL}")
        else:
            print(f"{Fore.RED}Failed to toggle filter status.{ColorStyle.RESET_ALL}")
    
    input("Press Enter to continue...")

def remove_filter_rule(source_manager, aggregation_manager, filter_manager, cli):
    """Remove a filter rule.
    
    Args:
        source_manager: Source manager instance
        aggregation_manager: Aggregation manager instance
        filter_manager: Filter manager instance
        cli: CLI instance for header
    """
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Remove Filter Rule ==={ColorStyle.RESET_ALL}")
    
    # Get sources with filters
    filters = filter_manager.get_all_filters()
    sources = source_manager.get_sources()
    
    if not filters:
        print(f"{Fore.YELLOW}No filter rules configured.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    # Show sources with filters
    print("\nSources with Filters:")
    source_list = []
    
    for i, (source_id, filter_rules) in enumerate(filters.items(), 1):
        if source_id in sources:
            source_name = sources[source_id]["source_name"]
            enabled_count = sum(1 for rule in filter_rules if rule.get("enabled", True))
            total_count = len(filter_rules)
            
            print(f"{i}. {source_name} ({enabled_count}/{total_count} active filters)")
            source_list.append(source_id)
    
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
            if 0 <= index < len(source_list):
                source_id = source_list[index]
                source = sources.get(source_id, {"source_name": "Unknown"})
                break
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
    
    # Show filter rules for the selected source
    clear()
    cli._print_header()
    print(f"{Fore.CYAN}=== Remove Filter Rules for {source['source_name']} ==={ColorStyle.RESET_ALL}")
    
    filter_rules = filter_manager.get_source_filters(source_id)
    
    if not filter_rules:
        print(f"{Fore.YELLOW}No filter rules configured for this source.{ColorStyle.RESET_ALL}")
        input("Press Enter to continue...")
        return
    
    print(f"\n{Fore.CYAN}Select a filter rule to remove:{ColorStyle.RESET_ALL}")
    
    for i, rule in enumerate(filter_rules, 1):
        status = "Enabled" if rule.get("enabled", True) else "Disabled"
        status_color = Fore.GREEN if rule.get("enabled", True) else Fore.YELLOW
        print(f"{i}. Field: {rule['field']} | Value: \"{rule['value']}\" | Status: {status_color}{status}{ColorStyle.RESET_ALL}")
    
    print("\nA. Clear all filters")
    print("0. Cancel")
    
    # Select filter rule
    while True:
        choice = prompt(
            HTML("<ansicyan>Select a filter rule or action: </ansicyan>"),
            style=cli.prompt_style
        )
        
        if choice == "0":
            return
        elif choice.upper() == "A":
            # Clear all filters
            confirm = prompt(
                HTML("<ansicyan>Are you sure you want to clear all filters? (y/n): </ansicyan>"),
                style=cli.prompt_style
            )
            
            if confirm.lower() == 'y':
                result = filter_manager.clear_filters(source_id)
                
                if result:
                    print(f"{Fore.GREEN}All filters cleared successfully.{ColorStyle.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Failed to clear filters.{ColorStyle.RESET_ALL}")
                
                input("Press Enter to continue...")
                return
            else:
                continue
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(filter_rules):
                selected_rule = filter_rules[index]
                field_name = selected_rule["field"]
                
                # Confirm removal
                confirm = prompt(
                    HTML(f"<ansicyan>Are you sure you want to remove the filter for field \"{field_name}\"? (y/n): </ansicyan>"),
                    style=cli.prompt_style
                )
                
                if confirm.lower() == 'y':
                    result = filter_manager.remove_filter(source_id, field_name)
                    
                    if result:
                        print(f"{Fore.GREEN}Filter removed successfully.{ColorStyle.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Failed to remove filter.{ColorStyle.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}Removal cancelled.{ColorStyle.RESET_ALL}")
                
                input("Press Enter to continue...")
                return
            else:
                print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
    
    input("Press Enter to continue...")
    
    for i, rule in enumerate(filter_rules, 1):
        status = "Enabled" if rule.get("enabled", True) else "Disabled"
        status_color = Fore.GREEN if rule.get("enabled", True) else Fore.YELLOW
        print(f"{i}. Field: {rule['field']} | Value: \"{rule['value']}\" | Status: {status_color}{status}{ColorStyle
