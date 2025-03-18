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

def view_status(source_manager, processor_manager, listener_manager, health_check, aggregation_manager=None, current_user=None):
    """View system and sources status in real-time until key press.
    
    Args:
        source_manager: Source manager instance
        processor_manager: Processor manager instance
        listener_manager: Listener manager instance
        health_check: Health check instance
        aggregation_manager: Optional aggregation manager instance
        current_user: Currently logged in username, if available
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
            
            # Print header with fixed width
            print_ascii_header()
            
            # Status title
            print(f"{Fore.CYAN}=== Live System Status ==={ColorStyle.RESET_ALL}")
            print(f"{Fore.YELLOW}Press any key to return to main menu...{ColorStyle.RESET_ALL}")
            
            # Last updated line
            print(f"\nLast updated: {current_time} (refresh #{update_count})")
            
            # Display logged in user if available
            if current_user:
                print(f"Logged in as: {Fore.GREEN}{current_user}{ColorStyle.RESET_ALL}")
            
            # System Resources section
            print(f"\n{Fore.CYAN}System Resources:{ColorStyle.RESET_ALL}")
            
            # CPU with fixed width
            cpu_bar = get_bar(cpu_percent)
            print(f"CPU Usage:    {cpu_bar} {cpu_percent:.1f}%")
            
            # Memory with fixed width
            mem_bar = get_bar(memory.percent)
            memory_text = f"Memory Usage: {mem_bar} {memory.percent:.1f}% ({format_bytes(memory.used)} / {format_bytes(memory.total)})"
            print(memory_text)
            
            # Disk with fixed width
            disk_bar = get_bar(disk.percent)
            disk_text = f"Disk Usage:   {disk_bar} {disk.percent:.1f}% ({format_bytes(disk.used)} / {format_bytes(disk.total)})"
            print(disk_text)
            
            # Network with better structure for Linux
            network_text = f"Network:      ↑ {format_bytes(net_io.bytes_sent)} sent | ↓ {format_bytes(net_io.bytes_recv)} received"
            print(network_text)
            
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
                
                # Create a fixed-width table (simpler for Linux compatibility)
                header_line = f"{'Source Name':<20} {'Status':<12} {'Queue':<8} {'Threads':<8} {'Processed':<10} {'Last Activity':<19} {'Template/Agg'}"
                print(f"\n{Fore.GREEN}{header_line}{ColorStyle.RESET_ALL}")
                print("-" * 100)  # Fixed width separator
                
                for source_id, source in sources.items():
                    # Get queue size
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
                    
                    # Format source name (truncate if needed)
                    source_name = source['source_name']
                    if len(source_name) > 18:
                        source_name = source_name[:16] + '..'
                    
                    # Format status display
                    status_display = f"{Fore.GREEN}Active{ColorStyle.RESET_ALL}" if listener_active else f"{Fore.RED}Inactive{ColorStyle.RESET_ALL}"
                    
                    # Add template status if aggregation manager is available
                    template_status = ""
                    if aggregation_manager and source_id in aggregation_manager.templates:
                        # Get field count
                        template = aggregation_manager.get_template(source_id)
                        if template and "fields" in template:
                            field_count = len(template["fields"])
                            template_status = f" [T:{field_count}]"
                    
                    # Check if aggregation is enabled
                    aggregation_status = ""
                    if aggregation_manager:
                        policy = aggregation_manager.get_policy(source_id)
                        if policy and policy.get("enabled", False):
                            aggregation_status = f" {Fore.GREEN}[A]{ColorStyle.RESET_ALL}"
                    
                    # Simpler fixed-width row for Linux compatibility
                    print(f"{source_name:<20} {status_display:<12} {queue_size:<8} {active_processors:<8} {processed_count:<10} {last_activity:<19}{template_status}{aggregation_status}")
                
                # Legend for abbreviations
                if aggregation_manager:
                    print(f"\n{Fore.CYAN}Legend:{ColorStyle.RESET_ALL}")
                    print(f"  [T:N] - Template exists with N fields extracted")
                    print(f"  [A] - Aggregation enabled for this source")
                
                # Source details
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

def print_ascii_header():
    """Print application header using fixed-width ASCII for better Linux compatibility."""
    print(f"{Fore.CYAN}======================================")
    print("         LOG COLLECTOR")
    print("======================================{ColorStyle.RESET_ALL}")
    print(f"Version: 1.0.0")

def print_header():
    """Print application header."""
    print_ascii_header()
