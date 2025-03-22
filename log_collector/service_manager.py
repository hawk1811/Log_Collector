# Replace this section in the WindowsService class __init__ method:

def __init__(self, args):
    win32serviceutil.ServiceFramework.__init__(self, args)
    self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
    socket.setdefaulttimeout(60)
    
    # Get log file path from environment if available, otherwise use default
    if "LOG_COLLECTOR_LOG_FILE" in os.environ:
        log_file = os.environ["LOG_COLLECTOR_LOG_FILE"]
    else:
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'service.log')
    
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    self.logger = setup_logging(log_file)
    self.logger.info(f"Windows service initialized with log file: {log_file}")
    
    # Register PID file location for cleanup
    if "LOG_COLLECTOR_PID_FILE" in os.environ:
        pid_file = os.environ["LOG_COLLECTOR_PID_FILE"]
        # Ensure PID directory exists
        pid_dir = os.path.dirname(pid_file)
        if pid_dir and not os.path.exists(pid_dir):
            os.makedirs(pid_dir, exist_ok=True)
        # Write PID file
        try:
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))
            self.logger.info(f"Wrote PID file to {pid_file}")
        except Exception as e:
            self.logger.error(f"Failed to write PID file: {e}")
    
    # Create service instance
    self.service = LogCollectorService(self.logger)
