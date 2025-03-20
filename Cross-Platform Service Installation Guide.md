# Log Collector Cross-Platform Service Guide

This guide explains how to install and manage the Log Collector service on both Windows and Linux systems using the cross-platform service script.

## Setup

1. Save the cross-platform service implementation as `log_collector_service.py` in your project directory.

2. Make the script executable (Linux/macOS only):
   ```bash
   chmod +x log_collector_service.py
   ```

3. Install required dependencies:
   - On Windows: `pip install pywin32`
   - On Linux: No additional dependencies required

## Windows Installation

### Method 1: Using the Script Directly

1. Open Command Prompt as Administrator.

2. Install the service:
   ```
   python log_collector_service.py install
   ```

3. Start the service:
   ```
   python log_collector_service.py start
   ```

4. Other commands:
   - Stop the service: `python log_collector_service.py stop`
   - Restart the service: `python log_collector_service.py restart`
   - Check status: Open Windows Services Manager (services.msc)
   - Remove service: `python log_collector_service.py remove`

### Method 2: Using Windows Services Manager

1. After installing the service with `python log_collector_service.py install`:

2. Open Windows Services Manager:
   - Press `Win+R`, type `services.msc` and press Enter
   
3. Find "Log Collector Service" in the list.

4. Right-click and select:
   - Start
   - Stop
   - Restart
   - Properties (to configure startup type)

## Linux Installation

### Method 1: Using the Script Directly

1. Start the service:
   ```bash
   sudo ./log_collector_service.py start
   ```

2. Check status:
   ```bash
   sudo ./log_collector_service.py status
   ```

3. Stop the service:
   ```bash
   sudo ./log_collector_service.py stop
   ```

4. Restart the service:
   ```bash
   sudo ./log_collector_service.py restart
   ```

### Method 2: Using Systemd (Recommended)

1. Create a new systemd service file:
   ```bash
   sudo nano /etc/systemd/system/log_collector.service
   ```

2. Add the following content:
   ```
   [Unit]
   Description=Log Collector Service
   After=network.target

   [Service]
   Type=forking
   ExecStart=/path/to/log_collector_service.py start --pid-file=/var/run/log_collector.pid --log-file=/var/log/log_collector/service.log
   ExecStop=/path/to/log_collector_service.py stop --pid-file=/var/run/log_collector.pid
   PIDFile=/var/run/log_collector.pid
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

3. Reload systemd:
   ```bash
   sudo systemctl daemon-reload
   ```

4. Enable and start the service:
   ```bash
   sudo systemctl enable log_collector
   sudo systemctl start log_collector
   ```

5. Other commands:
   - Check status: `sudo systemctl status log_collector`
   - Stop the service: `sudo systemctl stop log_collector`
   - Restart the service: `sudo systemctl restart log_collector`
   - View logs: `sudo journalctl -u log_collector`

## Troubleshooting

### Windows

1. Check the service log:
   - Look for `service.log` in the application directory

2. Check Windows Event Viewer:
   - Press `Win+R`, type `eventvwr.msc`, press Enter
   - Look in "Windows Logs" > "Application" for events from "Log Collector"

3. Verify pywin32 is installed:
   ```
   pip show pywin32
   ```

### Linux

1. Check the service log:
   ```bash
   sudo tail -f /var/log/log_collector/service.log
   ```

2. Check systemd logs:
   ```bash
   sudo journalctl -u log_collector -e
   ```

3. Check for permission issues:
   ```bash
   ls -la /var/log/log_collector
   ls -la /var/run/log_collector.pid
   ```

4. Verify the process is running:
   ```bash
   ps aux | grep log_collector
   ```

## Common Issues

1. **Service fails to start**:
   - Check logs for detailed error messages
   - Verify all dependencies are installed
   - Ensure file permissions are correct

2. **PID file issues**:
   - If a stale PID file is preventing startup, manually remove it:
     - Windows: Delete the PID file mentioned in logs
     - Linux: `sudo rm /var/run/log_collector.pid`

3. **Permission denied errors (Linux)**:
   - Run the script with sudo
   - Check permissions on log and PID directories

4. **Windows service not found**:
   - Reinstall the service: `python log_collector_service.py --startup auto install`

5. **Service stops unexpectedly**:
   - Check logs for errors
   - Increase the log level for more detailed information
   - On Linux, check system logs for OOM (Out of Memory) events
