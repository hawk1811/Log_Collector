"""
Windows Service implementation for Log Collector.
Requires the pywin32 package: pip install pywin32
"""
import sys
import os
import time
import logging
import win32service
import win32serviceutil
import win32event
import servicemanager
import socket

# Import Log Collector components
from log_collector.source_manager import SourceManager
from log_collector.processor import ProcessorManager
from log_collector.listener import LogListener
from log_collector.health_check import HealthCheck
from log_collector.aggregation_manager import AggregationManager
from log_collector.filter_manager import FilterManager
from log_collector.config import logger

class LogCollectorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "LogCollector"
    _svc_display_name_ = "Log Collector Service"
    _svc_description_ = "High-performance log collection and processing system"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_running = False
        
        # Setup logger to write to Windows event log
        logging.basicConfig(
            filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'service.log'),
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('LogCollectorService')

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False
        self.logger.info('Service stop pending...')
        
        # Shutdown Log Collector components
        self.logger.info("Shutting down Log Collector components...")
        try:
            if hasattr(self, 'health_check') and self.health_check.running:
                self.health_check.stop()
            if hasattr(self, 'processor_manager'):
                self.processor_manager.stop()
            if hasattr(self, 'listener_manager'):
                self.listener_manager.stop()
            self.logger.info("All components stopped successfully")
        except Exception as e:
            self.logger.error(f"Error stopping components: {e}")

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.is_running = True
        self.logger.info('Service starting...')
        
        try:
            # Initialize Log Collector components
            self.logger.info("Initializing Log Collector components...")
            auth_manager = None  # No auth in service mode
            source_manager = SourceManager()
            aggregation_manager = AggregationManager()
            filter_manager = FilterManager()
            
            self.processor_manager = ProcessorManager(source_manager, aggregation_manager, filter_manager)
            self.listener_manager = LogListener(source_manager, self.processor_manager)
            self.health_check = HealthCheck(source_manager, self.processor_manager)
            
            # Start all services
            self.processor_manager.start()
            self.listener_manager.start()
            
            # Start health check if configured
            if hasattr(self.health_check, 'config') and self.health_check.config is not None:
                if self.health_check.start():
                    self.logger.info("Health check monitoring started")
            
            self.logger.info("Log Collector service started successfully")
            
            # Main service loop
            while self.is_running:
                # Check if stop signal received
                if win32event.WaitForSingleObject(self.hWaitStop, 5000) == win32event.WAIT_OBJECT_0:
                    break
                
                # Perform periodic tasks or health checks here if needed
            
            self.logger.info("Service main loop exited")
            
        except Exception as e:
            self.logger.error(f"Error in service: {e}", exc_info=True)
            self.SvcStop()

def main():
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(LogCollectorService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(LogCollectorService)

if __name__ == '__main__':
    main()