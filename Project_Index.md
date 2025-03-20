# Log Collector Project Index

This document provides a detailed index of all files in the Log Collector project with explanations of each function's purpose.

## Core Files

### log_collector/main.py
Application entry point for the Log Collector application.

- `signal_handler(signum, frame)`: Handles termination signals for clean shutdowns
- `parse_args()`: Parses command line arguments for the application
- `main()`: Main entry point that initializes all components and starts the application

### log_collector/__init__.py
Package initialization file that exports key classes and functions.

- No specific functions, but exports important classes and version information

### log_collector/config.py
Configuration module for application-wide settings and constants.

- `load_sources()`: Loads source configurations from JSON file
- `save_sources(sources)`: Saves source configurations to JSON file

### log_collector/utils.py
Utility functions for cross-platform terminal handling and formatting.

- `setup_terminal()`: Sets up terminal for non-blocking input
- `restore_terminal(old_settings)`: Restores terminal settings
- `is_key_pressed()`: Checks if a key has been pressed without blocking
- `read_key()`: Reads a keypress
- `format_timestamp(timestamp)`: Formats timestamps for display
- `get_bar(percentage, width)`: Generates a visual bar for percentage display
- `format_bytes(bytes_value)`: Formats byte values into human-readable format
- `strip_ansi(text)`: Removes ANSI color codes from text
- `get_terminal_size()`: Gets terminal size in a cross-platform way
- `get_version()`: Gets application version

## Core Services

### log_collector/source_manager.py
Manages log sources configuration and validation.

- `get_sources()`: Gets all configured sources
- `get_source(source_id)`: Gets a specific source by ID
- `add_source(source_data)`: Adds a new log source
- `update_source(source_id, updated_data)`: Updates an existing log source
- `delete_source(source_id)`: Deletes a log source
- `validate_source(source_data)`: Validates source configuration

### log_collector/listener.py
Manages network listeners for log collection.

- `start()`: Starts all configured listeners
- `stop()`: Stops all listeners
- `update_listeners()`: Updates listeners based on current source configuration
- `_start_listener(port, sources)`: Starts a listener for a specific port
- `_udp_listener(port, sources)`: UDP listener implementation
- `_tcp_listener(port, sources)`: TCP listener implementation
- `_handle_tcp_client(client_socket, addr, ip_map)`: Handles TCP client connection
- `_process_log(data, source_id)`: Processes a received log message

### log_collector/processor.py
Manages log processing queues and worker threads.

- `start()`: Starts all processor threads
- `stop()`: Stops all processor threads
- `get_metrics()`: Gets current metrics for all sources
- `queue_log(log_str, source_id)`: Queues a log for processing
- `update_processors()`: Updates processors based on current source configuration
- `_ensure_processor(source_id)`: Ensures a processor exists for the given source
- `_processor_worker(processor_id, source_id)`: Worker thread for processing logs
- `_process_batch(batch, source)`: Processes a batch of logs
- `_deliver_to_folder(batch, source)`: Delivers a batch of logs to a folder with optional compression
- `_deliver_to_hec(batch, source)`: Delivers a batch of logs to HEC

### log_collector/health_check.py
Manages system health monitoring and reporting.

- `configure(hec_url, hec_token, interval)`: Configures health check settings
- `start()`: Starts health check monitoring
- `stop()`: Stops health check monitoring
- `_test_connection()`: Tests connection to HEC endpoint
- `_monitor_thread()`: Background thread for periodic health monitoring
- `_collect_health_data()`: Collects system health data
- `_send_health_data(health_data)`: Sends health data to HEC

### log_collector/aggregation_manager.py
Manages log aggregation policies and processing.

- `ensure_template(source_id, processor_manager)`: Ensures a log template exists for a source
- `store_log_template(source_id, log_content)`: Stores a log template for a source
- `_extract_fields(log_content)`: Extracts fields from log content
- `_extract_fields_from_dict(data, fields, prefix)`: Recursively extracts fields from dictionary
- `_extract_key_value_pairs(log_content, fields)`: Extracts fields from key=value pairs format
- `_add_key_value_field(key, value, fields)`: Helper method to add a key-value pair to fields with type detection
- `_extract_delimited(log_content, delimiter, fields)`: Extracts fields from a delimited string
- `_extract_colon_separated(log_content, fields)`: Extracts fields from colon-separated format
- `_extract_space_separated(log_content, fields)`: Extracts fields from space-separated values
- `create_policy(source_id, selected_fields)`: Creates or updates an aggregation policy
- `update_policy(source_id, updates)`: Updates an existing policy
- `delete_policy(source_id)`: Deletes an aggregation policy
- `delete_template(source_id)`: Deletes a log template
- `get_policy(source_id)`: Gets an aggregation policy
- `get_template(source_id)`: Gets a log template
- `get_all_policies()`: Gets all aggregation policies
- `aggregate_batch(batch, source_id)`: Aggregates a batch of logs based on policy
- `_extract_aggregation_key(log_str, agg_fields)`: Extracts aggregation key from a log

### log_collector/filter_manager.py
Manages log filter policy management and processing.

- `get_all_filters()`: Gets all filter policies
- `get_source_filters(source_id)`: Gets filters for a specific source
- `add_filter(source_id, field_name, filter_value)`: Adds a new filter rule
- `remove_filter(source_id, field_name)`: Removes a filter rule
- `toggle_filter(source_id, field_name)`: Toggles a filter rule on/off
- `clear_filters(source_id)`: Clears all filters for a source
- `apply_filters(log_str, source_id)`: Applies filters to decide if a log should be filtered out
- `_extract_log_data(log_str)`: Extracts data from log for filtering

### log_collector/auth.py
Manages user authentication and password security.

- `authenticate(username, password)`: Authenticates a user
- `_record_failed_attempt(username)`: Records a failed login attempt
- `_is_locked_out(username)`: Checks if a user is locked out
- `validate_password(password)`: Validates a password against security requirements
- `change_password(username, old_password, new_password)`: Changes a user's password
- `reset_password(username, new_password)`: Resets a user's password to a default value or specified password

### log_collector/updater.py
Update module for checking for updates, pulling from git, and upgrading the package.

- `check_for_updates(cli)`: Checks for updates and performs upgrade if available
- `_is_git_installed()`: Checks if git is installed and available in PATH
- `_is_git_repo()`: Checks if the current directory is a git repository
- `_get_current_branch()`: Gets the name of the current git branch
- `_has_local_changes()`: Checks if there are uncommitted local changes
- `_git_fetch()`: Fetches updates from remote repository
- `_updates_available(branch)`: Checks if updates are available for the current branch
- `_show_commit_log(branch)`: Displays the commit log of changes that will be applied
- `_git_pull(branch)`: Pulls updates from remote repository
- `_pip_install_upgrade()`: Upgrades the package using pip
- `restart_application()`: Restarts the current application

## CLI Modules

### log_collector/cli_main.py
Command Line Interface main module with the core CLI class and main menu functions.

- `start()`: Starts CLI interface
- `_print_header()`: Prints application header
- `_show_main_menu()`: Displays main menu and handles commands
- `_exit_application()`: Exits the application cleanly
- `_clean_exit()`: Cleans up resources before exiting

### log_collector/cli_utils.py
Command Line Interface utility functions for terminal handling and formatting.

- `setup_terminal()`: Sets up terminal for non-blocking input while preserving normal input mode
- `is_key_pressed()`: Checks if a key is pressed without blocking
- `read_key()`: Reads a key press
- `restore_terminal(old_settings)`: Restores terminal settings
- `safe_setup_terminal()`: Safely sets up terminal for non-blocking input with state tracking
- `safe_restore_terminal(old_settings)`: Safely restores terminal settings with state tracking
- `format_timestamp(timestamp)`: Formats timestamp for display
- `get_bar(percentage, width)`: Generates a visual bar representation of a percentage
- `format_bytes(bytes_value)`: Formats bytes into human-readable format
- `strip_ansi(text)`: Removes ANSI color codes from text
- `get_terminal_size()`: Gets terminal size in a cross-platform way
- `calculate_content_width(text)`: Calculates the display width of a string considering ANSI codes

### log_collector/cli_sources.py
Source management module for adding, updating, and deleting log sources.

- `add_source(source_manager, processor_manager, listener_manager, cli)`: Adds a new log source
- `edit_source(source_id, source_manager, processor_manager, listener_manager, cli)`: Edits a source configuration
- `delete_source(source_id, source_manager, processor_manager, listener_manager)`: Deletes a source
- `view_template_fields(source_id, source_manager, aggregation_manager, cli)`: Views all fields in a log template
- `delete_template(source_id, source_manager, aggregation_manager, cli)`: Deletes a log template
- `delete_aggregation_rule(source_id, source_manager, aggregation_manager, cli)`: Deletes an aggregation rule
- `manage_source(source_id, source_manager, processor_manager, listener_manager, cli, aggregation_manager, filter_manager)`: Manages a specific source
- `manage_sources(source_manager, processor_manager, listener_manager, cli, aggregation_manager, filter_manager)`: Manages existing sources

### log_collector/cli_health.py
Health check configuration module for configuring and managing health check monitoring.

- `configure_health_check(health_check, cli)`: Configures health check monitoring
- `update_health_check(health_check, cli)`: Updates health check configuration

### log_collector/cli_status.py
Status dashboard module for real-time monitoring of system resources and log collection activity.

- `view_status(source_manager, processor_manager, listener_manager, health_check, aggregation_manager, current_user)`: Views system and sources status in real-time until key press
- `print_ascii_header()`: Prints application header using fixed-width ASCII for better Linux compatibility
- `print_header()`: Prints application header

### log_collector/cli_auth.py
CLI authentication module for handling login and password management.

- `login_screen(auth_manager, cli)`: Displays login screen and handles authentication
- `change_password_screen(auth_manager, username, force_change, cli)`: Displays the change password screen

### log_collector/cli_aggregation.py
CLI module for managing log aggregation rules.

- `manage_aggregation_rules(source_manager, processor_manager, aggregation_manager, cli)`: Manages log aggregation rules
- `create_aggregation_rule(source_manager, processor_manager, aggregation_manager, cli)`: Creates a new aggregation rule
- `edit_aggregation_rule(source_manager, processor_manager, aggregation_manager, cli)`: Edits an existing aggregation rule
- `delete_aggregation_rule(source_manager, processor_manager, aggregation_manager, cli)`: Deletes an aggregation rule

### log_collector/cli_filters.py
CLI module for managing log filter rules.

- `manage_filter_rules(source_manager, aggregation_manager, filter_manager, cli)`: Manages filter rules for all sources
- `add_filter_rule(source_manager, aggregation_manager, filter_manager, cli)`: Adds a new filter rule
- `edit_filter_rule(source_manager, aggregation_manager, filter_manager, cli)`: Edits an existing filter rule
- `remove_filter_rule(source_manager, aggregation_manager, filter_manager, cli)`: Removes a filter rule

## Package Configuration Files

### setup.py
Package setup configuration for installation.

- Package metadata and dependency management

### pyproject.toml
Python project configuration using modern standards.

- Build system requirements
