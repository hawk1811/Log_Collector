@echo off
echo Stopping LogCollector service...
LogCollector.exe --service stop
echo.
echo Service stop command sent. Check logs for details.
pause
