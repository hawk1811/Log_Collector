import sys
import time
import servicemanager
from win32service import win32service, win32serviceutil
from log_collector import main  # Import your log_collector logic here

class LogCollectorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "LogCollectorService"
    _svc_display_name_ = "Log Collector Service"
    _svc_description_ = "This service collects logs in the background."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.halt = False

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.halt = True

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        while not self.halt:
            # Run your log_collector logic here
            main()  # Call your main log_collector logic
            time.sleep(10)

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(LogCollectorService)
