#!/bin/bash

echo "Building LogCollector for Linux..."
echo "-----------------------------------"

# Check if PyInstaller is installed
if ! pip show pyinstaller > /dev/null 2>&1; then
    echo "PyInstaller not found. Installing..."
    pip install pyinstaller
    if [ $? -ne 0 ]; then
        echo "Failed to install PyInstaller. Exiting."
        exit 1
    fi
fi

# Clean and build using PyInstaller
echo "Running PyInstaller..."
pyinstaller --clean --onefile --name LogCollector log_collector/main.py

if [ $? -ne 0 ]; then
    echo "Build failed. See above for errors."
    exit 1
fi

echo "Build completed successfully."

# Get the current date and time for backup folders
timestamp=$(date +"%Y%m%d-%H%M%S")

# Create or backup the data directory
cd dist
if [ -d "data" ]; then
    echo "Backing up existing data directory..."
    mv data "data-backup-$timestamp"
fi
mkdir data

# Create or backup the logs directory
if [ -d "logs" ]; then
    echo "Backing up existing logs directory..."
    mv logs "logs-backup-$timestamp"
fi
mkdir logs

# Create README.txt
echo "Creating README.txt..."
cat > README.txt << EOL
LogCollector Standalone Application
======================================
This is a standalone version of the LogCollector application.

Getting Started:
1. Run LogCollector executable to start the application
2. Use 'LogCollector --service start'  to start the service
3. Use 'LogCollector --service stop'  to stop the service
4. Use 'LogCollector --service status'  to check service status

Data and logs are stored in the data/ and logs/ directories.

<Use 'LogCollector --h' for additional options>
EOL

# Create tar.gz archive instead of zip
echo "Creating tar.gz archive..."
cd ..
tar -czvf dist/LogCollector-Linux.tar.gz -C dist .

# Get absolute path for the dist folder
dist_path=$(realpath dist)

echo ""
echo "-----------------------------------------------------"
echo "Build successful!"
echo ""
echo "LogCollector application has been built successfully."
echo "The executable and supporting files are located in:"
echo "$dist_path"
echo ""
echo "The files have also been archived to:"
echo "$dist_path/LogCollector-Linux.tar.gz"
echo ""
echo "README.txt Contents:"
echo "-----------------------------------------------------"
cat dist/README.txt
echo "-----------------------------------------------------"
echo ""

# Make the executable file executable
chmod +x dist/LogCollector
