"""
Status dashboard module for Log Collector.
Provides real-time monitoring of system resources, log collection activity, and service status.
"""
import time
import threading
import psutil
import os
import json
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
from log_collector.config import DATA_DIR

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
            
            # Get service status information
            service_status = get_service_status()
            
            # Move cursor to beginning and clear screen
            print("\033[H\033[J", end="")
            
            # Print header
            print_header()
            print(f"{Fore.CYAN}=== Live System Status ==={ColorStyle.RESET_ALL}")
            print(f"{Fore.YELLOW}Press any key to return to main menu...{ColorStyle.RESET_ALL}")
            print(f"\nLast updated: {current_time} (refresh #{update_count})")
            
            # Service Status
            print(f"\n{Fore.CYAN}Service Status:{ColorStyle.RESET_ALL}")
            if service_status["running"]:
                print(f"Status: {Fore.GREEN}Running{ColorStyle.RESET_ALL} (PID: {service_status.get('pid', 'Unknown')})")
                print(f"Uptime: {format_uptime(service_status.get('start_time', time.time()))}")
                print(f"Listener: {'Running' if service_status.get('listener_running', False) else 'Stopped'}")
                print(f"Processor: {'Running' if service_status.get('processor_running', False) else 'Stopped'}")
                print(f"Last Status Update: {datetime.fromtimestamp(service_status.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"Status: {Fore.RED}Not Running{ColorStyle.RESET_ALL}")
                print("The service must be running to collect logs.")
                print("You can start it from the Service Management menu.")
            
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
                header = f"{'Source Name':<25} {'Type':<10} {'Protocol':<8} {'Port':<6} {'Processed Logs':<15} {'Last Activity':<20}"
                print(f"\n{Fore.GREEN}{header}{ColorStyle.RESET_ALL}")
                print("-" * len(header))
                
                for source_id, source in sources.items():
                    # Determine source status based on service status
                    status_active = service_status["running"] and service_status.get("listener_running", False)
                    
                    # Get processed logs count
                    processed_count = processed_logs_count.get(source_id, 0)
                    
                    # Get last processed timestamp
                    last_timestamp = last_processed_timestamp.get(source_id)
                    last_activity = format_timestamp(last_timestamp)
                    
                    # Source information
                    source_name = source['source_name'][:23] + '..' if len(source['source_name']) > 25 else source['source_name']
                    target_type = source['target_type']
                    protocol = source['protocol']
                    port = source['listener_port']
                    
                    print(f"{source_name:<25} {target_type:<10} {protocol:<8} {port:<6} {processed_count:<15} {last_activity:<20}")
                
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

def get_service_status():
    """Get current service status."""
    # Default status (not running)
    status = {
        "running": False,
        "sources_count": 0,
        "processor_running": False,
        "listener_running": False,
        "health_check_running": False,
        "timestamp": time.time(),
        "pid": None,
        "start_time": None
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
            
            # Get process start time
            try:
                process = psutil.Process(pid)
                status["start_time"] = process.create_time()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
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

def format_uptime(start_time):
    """Format uptime from start timestamp."""
    if not start_time:
        return "Unknown"
    
    uptime_seconds = time.time() - start_time
    
    # Calculate days, hours, minutes, seconds
    days, remainder = divmod(uptime_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # Format string
    components = []
    if days > 0:
        components.append(f"{int(days)}d")
    if hours > 0 or days > 0:
        components.append(f"{int(hours)}h")
    if minutes > 0 or hours > 0 or days > 0:
        components.append(f"{int(minutes)}m")
    components.append(f"{int(seconds)}s")
    
    return " ".join(components)

def print_header():
    """Print application header."""
    print(f"{Fore.CYAN}======================================")
    print("         LOG COLLECTOR")
    print("======================================")
    print(f"Version: 1.0.0{ColorStyle.RESET_ALL}")
    print()
