@echo off
REM =========================================
REM Log Collector Service Launcher for Windows
REM =========================================

setlocal EnableDelayedExpansion

REM Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Administrator privileges required.
    echo Please run this script as administrator.
    pause
    exit /b 1
)

REM Determine executable path
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Check if we're using the compiled executable or Python script
if exist "log_collector.exe" (
    set "EXECUTABLE=log_collector.exe"
) else (
    REM Find Python executable
    where python >nul 2>&1
    if %errorLevel% neq 0 (
        echo Python not found in PATH. Please install Python or add it to your PATH.
        pause
        exit /b 1
    )
    
    set "EXECUTABLE=python log_collector"
)

REM Command line arguments
set "ARGS=--no-interactive"

REM Path for PID file and log file
set "PID_FILE=%TEMP%\log_collector.pid"
set "LOG_FILE=%SCRIPT_DIR%log_collector_service.log"

echo ========================================
echo Log Collector Service Manager
echo ========================================
echo.
echo 1. Start Service
echo 2. Stop Service
echo 3. Check Status
echo 4. View Logs
echo 5. Exit
echo.

choice /c 12345 /n /m "Select an option (1-5): "

if errorlevel 5 goto :exit
if errorlevel 4 goto :viewlogs
if errorlevel 3 goto :checkstatus
if errorlevel 2 goto :stopservice
if errorlevel 1 goto :startservice

:startservice
echo.
echo Starting Log Collector service...

REM Check if already running
if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"
    
    REM Check if process is still running
    tasklist /fi "PID eq !PID!" | find "!PID!" >nul
    if !errorlevel! equ 0 (
        echo Service is already running with PID !PID!
        goto :end
    ) else (
        echo Previous instance (PID !PID!) is no longer running.
        del "%PID_FILE%" 2>nul
    )
)

REM Start the service with output redirected to log file
start /B "" cmd /c %EXECUTABLE% %ARGS% ^> "%LOG_FILE%" 2^>^&1

REM Get PID of the started process
for /f "tokens=2" %%a in ('tasklist /fi "IMAGENAME eq %EXECUTABLE:.* =%"^|find "%EXECUTABLE:.* =%"') do (
    set PID=%%a
    goto :gotpid
)

:gotpid
if defined PID (
    echo !PID! > "%PID_FILE%"
    echo Service started with PID !PID!
) else (
    echo Failed to get PID of started service.
)
goto :end

:stopservice
echo.
echo Stopping Log Collector service...

if not exist "%PID_FILE%" (
    echo No PID file found. Service might not be running.
    goto :end
)

set /p PID=<"%PID_FILE%"
echo Stopping process with PID !PID!...

taskkill /F /PID !PID! >nul 2>&1
if !errorlevel! equ 0 (
    echo Service stopped successfully.
    del "%PID_FILE%" 2>nul
) else (
    echo Failed to stop service. Process might have already ended.
    del "%PID_FILE%" 2>nul
)
goto :end

:checkstatus
echo.
echo Checking service status...

if not exist "%PID_FILE%" (
    echo Service is not running (no PID file found).
    goto :end
)

set /p PID=<"%PID_FILE%"
tasklist /fi "PID eq !PID!" | find "!PID!" >nul
if !errorlevel! equ 0 (
    echo Service is running with PID !PID!
) else (
    echo Service is not running (PID !PID! not found).
    del "%PID_FILE%" 2>nul
)
goto :end

:viewlogs
echo.
echo Log contents:
echo ========================================
if exist "%LOG_FILE%" (
    type "%LOG_FILE%"
) else (
    echo No log file found.
)
echo ========================================
goto :end

:exit
echo.
echo Exiting...
exit /b 0

:end
echo.
pause
cls
goto :eof
