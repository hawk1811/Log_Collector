"""
Status dashboard module for Log Collector.
Provides real-time monitoring of system resources and log collection activity.
"""
import time
import threading
import platform
import psutil
import os
from datetime import datetime
from prompt_toolkit.shortcuts import clear
from colorama import Fore, Style as ColorStyle

from log_collector.cli_utils import (
    setup_terminal, 
    restore_terminal, 
    is_key_pressed, 
    read_key,
    format_timestamp,
    get_bar,
    format_bytes
)

def view_status(source_manager, processor_manager, listener_manager, health_check):
    """View system and sources status in real-time until key press.
    
    Args:
        source_manager: Source manager instance
        processor_manager: Processor manager instance
        listener_manager: Listener manager instance
        health_check: Health check instance
    """
    # Detect platform for platform-specific display adjustments
    is_windows = platform.system() == "Windows"
    
    # Main status display loop
    running = True
    refresh_interval = 1.0  # Refresh every second
    update_count = 0
    old_settings = None
    
    try:
        # Setup terminal for non-blocking input
        old_settings = setup_terminal()
        
        while running:
            # Clear screen in a platform-compatible way
            clear()
            
            # Get current timestamp
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Get system information
            cpu_percent = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net_io = psutil.net_io_counters()
            
            # Thread information
            thread_count = threading.active_count()
            
            # Get processor metrics
            metrics = processor_manager.get_metrics()
            processed_logs_count = metrics["processed_logs_count"]
            last_processed_timestamp = metrics["last_processed_timestamp"]
            
            # Get sources information
            sources = source_manager.get_sources()
            
            # Print header
            print_header()
            print(f"{Fore.CYAN}=== Live System Status ==={ColorStyle.RESET_ALL}")
            print(f"{Fore.YELLOW}Press any key to return to main menu...{ColorStyle.RESET_ALL}")
            print(f"\nLast updated: {current_time} (refresh #{update_count})")
            
            # System Resources
            print(f"\n{Fore.CYAN}System Resources:{ColorStyle.RESET_ALL}")
            
            # CPU
            cpu_bar = get_bar(cpu_percent)
            print(f"CPU Usage:    {cpu_bar} {cpu_percent:.1f}%")
            
            # Memory
            mem_bar = get_bar(memory.percent)
            print(f"Memory Usage: {mem_bar} {memory.percent:.1f}% ({format_bytes(memory.used)} / {format_bytes(memory.total)})")
            
            # Disk
            disk_bar = get_bar(disk.percent)
            print(f"Disk Usage:   {disk_bar} {disk.percent:.1f}% ({format_bytes(disk.used)} / {format_bytes(disk.total)})")
            
            # Network (with better formatting)
            print(f"Network:      ↑ {format_bytes(net_io.bytes_sent)} sent | ↓ {format_bytes(net_io.bytes_recv)} received")
            
            # Thread count
            print(f"Active Threads: {thread_count}")
            
            # Health check status
            print(f"\n{Fore.CYAN}Health Check Status:{ColorStyle.RESET_ALL}")
            is_configured = hasattr(health_check, 'config') and health_check.config is not None
            is_running = is_configured and health_check.running
            
            if is_configured:
                print(f"  Status: {'Running' if is_running else 'Stopped'}")
                if is_running:
                    print(f"  Interval: {health_check.config['interval']} seconds")
            else:
                print(f"  Not Configured")
            
            # Sources information
            if sources:
                print(f"\n{Fore.CYAN}Active Sources:{ColorStyle.RESET_ALL}")
                
                # Create a table header
                print("\n" + format_table_row("Source Name", "Status", "Queue", "Threads", "Processed Logs", "Last Activity", header=True))
                print("-" * 100)  # Fixed width separator
                
                for source_id, source in sources.items():
                    # Get queue size if available
                    queue_size = 0
                    if source_id in processor_manager.queues:
                        queue_size = processor_manager.queues[source_id].qsize()
                    
                    # Count active processors
                    active_processors = sum(1 for p_id, p_thread in processor_manager.processors.items()
                                          if p_id.startswith(f"{source_id}:") and p_thread.is_alive())
                    
                    # Check if listener is active
                    listener_port = source["listener_port"]
                    listener_protocol = source["protocol"]
                    listener_key = f"{listener_protocol}:{listener_port}"
                    listener_active = listener_key in listener_manager.listeners and listener_manager.listeners[listener_key].is_alive()
                    
                    # Get processed logs count
                    processed_count = processed_logs_count.get(source_id, 0)
                    
                    # Get last processed timestamp
                    last_timestamp = last_processed_timestamp.get(source_id)
                    last_activity = format_timestamp(last_timestamp)
                    
                    # Determine status color
                    status_text = "Active" if listener_active else "Inactive"
                    status_display = f"{Fore.GREEN}{status_text}{ColorStyle.RESET_ALL}" if listener_active else f"{Fore.RED}{status_text}{ColorStyle.RESET_ALL}"
                    
                    # Print source info as a table row
                    source_name = source['source_name']
                    if len(source_name) > 20:
                        source_name = source_name[:18] + '..'
                    
                    # Print formatted row
                    print(format_table_row(
                        source_name, 
                        status_display, 
                        str(queue_size), 
                        str(active_processors), 
                        str(processed_count), 
                        last_activity
                    ))
                
                # More detailed source information
                print(f"\n{Fore.CYAN}Source Details:{ColorStyle.RESET_ALL}")
                for source_id, source in sources.items():
                    print(f"\n{Fore.YELLOW}{source['source_name']}{ColorStyle.RESET_ALL}")
                    print(f"  IP: {source['source_ip']}")
                    print(f"  Port: {source['listener_port']} ({source['protocol']})")
                    print(f"  Target: {source['target_type']}")
                    if source['target_type'] == 'FOLDER':
                        print(f"  Folder Path: {source.get('folder_path', 'Not specified')}")
                        
                        # Display compression settings
                        compression_enabled = source.get('compression_enabled', 'Default')
                        if compression_enabled is True:
                            compression_level = source.get('compression_level', 'Default')
                            print(f"  Compression: Enabled (Level {compression_level})")
                        elif compression_enabled is False:
                            print(f"  Compression: Disabled")
                        else:
                            print(f"  Compression: Default")
                    elif source['target_type'] == 'HEC':
                        print(f"  HEC URL: {source.get('hec_url', 'Not specified')}")
                    print(f"  Batch Size: {source.get('batch_size', 'Default')}")
            else:
                print(f"\n{Fore.YELLOW}No sources configured.{ColorStyle.RESET_ALL}")
            
            # Check for keypress
            if is_key_pressed():
                read_key()  # Consume the keypress
                running = False
                break
            
            # Increment update counter
            update_count += 1
            
            # Sleep for refresh interval
            time.sleep(refresh_interval)
    
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        pass
    except Exception as e:
        print(f"{Fore.RED}Error in status view: {e}{ColorStyle.RESET_ALL}")
    finally:
        # Always restore terminal settings
        restore_terminal(old_settings)
    
    # Clear screen once more before returning to menu
    clear()
    time.sleep(0.5)  # Brief pause before returning to menu

def format_table_row(col1, col2, col3, col4, col5, col6, header=False):
    """Format a table row with consistent spacing, handling color codes.
    
    Args:
        col1-col6: Column content
        header: Whether this is a header row
        
    Returns:
        str: Formatted row
    """
    # For columns with color codes, we need to account for invisible characters
    # when calculating display width
    
    # For the status column which contains color codes
    if not header and Fore.GREEN in col2 or Fore.RED in col2:
        # We need to handle the invisible color codes for proper alignment
        status_text = "Active" if "Active" in col2 else "Inactive"
        col2_display_width = len(status_text)
    else:
        col2_display_width = len(col2)
    
    # Define column widths
    col_widths = [20, 10, 10, 10, 15, 20]
    
    # Create the formatted row
    if header:
        return f"{Fore.GREEN}{col1:<{col_widths[0]}} {col2:<{col_widths[1]}} {col3:<{col_widths[2]}} {col4:<{col_widths[3]}} {col5:<{col_widths[4]}} {col6:<{col_widths[5]}}{ColorStyle.RESET_ALL}"
    else:
        # For non-header rows, handle status column specially
        return f"{col1:<{col_widths[0]}} {col2} {col3:>{col_widths[2]-2}} {col4:>{col_widths[3]-2}} {col5:>{col_widths[4]-2}} {col6:<{col_widths[5]}}"

def print_header():
    """Print application header."""
    print(f"{Fore.CYAN}======================================")
    print("         LOG COLLECTOR")
    print("======================================")
    print(f"Version: 1.0.0{ColorStyle.RESET_ALL}")
    print()
