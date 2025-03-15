"""
Status dashboard module for Log Collector.
Provides real-time monitoring of system resources and log collection activity.
"""
import time
import threading
import psutil
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
    clear()
    print_header()
    print(f"{Fore.CYAN}=== Live System Status ==={ColorStyle.RESET_ALL}")
    print(f"{Fore.YELLOW}Press any key to return to main menu...{ColorStyle.RESET_ALL}")
    
    # Main status display loop
    running = True
    refresh_interval = 1.0  # Refresh every second
    update_count = 0
    old_settings = None
    
    try:
        # Setup terminal for non-blocking input
        old_settings = setup_terminal()
        
        while running:
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
            
            # Move cursor to beginning and clear screen
            print("\033[H\033[J", end="")
            
            # Print header
            print_header()
            print(f"{Fore.CYAN}=== Live System Status ==={ColorStyle.RESET_ALL}")
            print(f"{Fore.YELLOW}Press any key to return to main menu...{ColorStyle.RESET_ALL}")
            print(f"\nLast updated: {current_time} (refresh #{update_count})")
            
            # System Resources
            print(f"\n{Fore.CYAN}System Resources:{ColorStyle.RESET_ALL}")
            
            # CPU
            cpu_bar = get_bar(cpu_percent)
            print(f"CPU Usage:    {cpu_bar} {cpu_percent}%")
            
            # Memory
            mem_bar = get_bar(memory.percent)
            print(f"Memory Usage: {mem_bar} {memory.percent}% ({format_bytes(memory.used)} / {format_bytes(memory.total)})")
            
            # Disk
            disk_bar = get_bar(disk.percent)
            print(f"Disk Usage:   {disk_bar} {disk.percent}% ({format_bytes(disk.used)} / {format_bytes(disk.total)})")
            
            # Network
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
                header = f"{'Source Name':<25} {'Status':<10} {'Queue':<10} {'Threads':<10} {'Processed Logs':<15} {'Last Activity':<20}"
                print(f"\n{Fore.GREEN}{header}{ColorStyle.RESET_ALL}")
                print("-" * len(header))
                
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
                    status_color = Fore.GREEN if listener_active else Fore.RED
                    status_text = "Active" if listener_active else "Inactive"
                    
                    # Print source info as a table row
                    source_name = source['source_name'][:23] + '..' if len(source['source_name']) > 25 else source['source_name']
                    print(f"{source_name:<25} {status_color}{status_text:<10}{ColorStyle.RESET_ALL} {queue_size:<10} {active_processors:<10} {processed_count:<15} {last_activity:<20}")
                
                # More detailed source information
                print(f"\n{Fore.CYAN}Source Details:{ColorStyle.RESET_ALL}")
                for source_id, source in sources.items():
                    print(f"\n{Fore.YELLOW}{source['source_name']}{ColorStyle.RESET_ALL}")
                    print(f"  IP: {source['source_ip']}")
                    print(f"  Port: {source['listener_port']} ({source['protocol']})")
                    print(f"  Target: {source['target_type']}")
                    if source['target_type'] == 'FOLDER':
                        print(f"  Folder Path: {source.get('folder_path', 'Not specified')}")
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

def print_header():
    """Print application header."""
    print(f"{Fore.CYAN}======================================")
    print("         LOG COLLECTOR")
    print("======================================")
    print(f"Version: 1.0.0{ColorStyle.RESET_ALL}")
    print()
