@echo off
setlocal enabledelayedexpansion

echo Building LogCollector for Windows...
echo -----------------------------------

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    if %ERRORLEVEL% neq 0 (
        echo Failed to install PyInstaller. Exiting.
        exit /b 1
    )
)

REM Clean and build using PyInstaller
echo Running PyInstaller...
pyinstaller --clean --onefile --name LogCollector log_collector\main.py

if %ERRORLEVEL% neq 0 (
    echo Build failed. See above for errors.
    exit /b 1
)

echo Build completed successfully.

REM Get the current date and time for backup folders
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /format:list') do set datetime=%%I
set "timestamp=%datetime:~0,8%-%datetime:~8,6%"

REM Create or backup the data directory
cd dist
if exist data (
    echo Backing up existing data directory...
    rename data data-backup-%timestamp%
)
mkdir data

REM Create or backup the logs directory
if exist logs (
    echo Backing up existing logs directory...
    rename logs logs-backup-%timestamp%
)
mkdir logs

REM Create README.txt
echo Creating README.txt...
(
echo LogCollector Standalone Application
echo ======================================
echo This is a standalone version of the LogCollector application.
echo.
echo Getting Started:
echo 1. Run LogCollector executable to start the application
echo 2. Use 'LogCollector --service start'  to start the service
echo 3. Use 'LogCollector --service stop'  to stop the service
echo 4. Use 'LogCollector --service status'  to check service status
echo.
echo Data and logs are stored in the data/ and logs/ directories.
echo.
echo ^<Use 'LogCollector --h' for additional options^>
) > README.txt

REM Create zip file
echo Creating zip archive...
cd ..
powershell -command "Compress-Archive -Path dist\* -DestinationPath dist\LogCollector-Windows.zip -Force"

REM Get absolute path for the dist folder
set "current_dir=%cd%"
set "dist_path=%current_dir%\dist"

echo.
echo -----------------------------------------------------
echo Build successful! 
echo.
echo LogCollector application has been built successfully.
echo The executable and supporting files are located in:
echo %dist_path%
echo.
echo The files have also been zipped to:
echo %dist_path%\LogCollector-Windows.zip
echo.
echo README.txt Contents:
echo -----------------------------------------------------
type dist\README.txt
echo -----------------------------------------------------
echo.

endlocal
