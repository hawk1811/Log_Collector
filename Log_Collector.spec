# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path

# Root directory of the project
root_dir = os.path.dirname(os.path.abspath(SPECPATH))

# Define the base name of the executable
app_name = "Log_Collector"

# Platform-specific adjustments
is_windows = sys.platform.startswith('win')
is_linux = sys.platform.startswith('linux')
is_macos = sys.platform.startswith('darwin')

# Create empty data directories to ensure they exist in the bundle
data_dir = os.path.join(root_dir, 'data')
logs_dir = os.path.join(root_dir, 'logs')
os.makedirs(data_dir, exist_ok=True)
os.makedirs(logs_dir, exist_ok=True)

a = Analysis(
    # Main script that starts the application
    [os.path.join(root_dir, 'log_collector', 'main.py')],
    
    # Path to search for modules
    pathex=[root_dir],
    
    # Binary dependencies
    binaries=[],
    
    # Data files and directories to include
    datas=[
        # Include the entire log_collector package
        (os.path.join(root_dir, 'log_collector'), 'log_collector'),
        
        # Include the service script
        (os.path.join(root_dir, 'log_collector_service.py'), '.'),
        
        # Include empty data and logs directories
        (data_dir, 'data'),
        (logs_dir, 'logs'),
    ],
    
    # Hidden imports that PyInstaller might miss
    hiddenimports=[
        # CLI components
        'log_collector.cli.cli_main',
        'log_collector.cli.cli_utils',
        'log_collector.cli.cli_sources',
        'log_collector.cli.cli_status',
        'log_collector.cli.cli_health',
        'log_collector.cli.cli_auth',
        'log_collector.cli.cli_service',
        'log_collector.cli.cli_aggregation',
        'log_collector.cli.cli_filters',
        
        # Core components
        'log_collector.main',
        'log_collector.config',
        'log_collector.utils',
        'log_collector.source_manager',
        'log_collector.listener',
        'log_collector.processor',
        'log_collector.health_check',
        'log_collector.auth',
        'log_collector.aggregation_manager',
        'log_collector.filter_manager',
        'log_collector.service_manager',
        'log_collector.updater',
        
        # Common libraries that might be imported dynamically
        'json',
        'csv',
        'threading',
        'queue',
        'socket',
        'ssl',
        'logging',
        'multiprocessing',
        
        # Third-party packages
        'requests',
        'requests.auth',
        'psutil',
        'colorama',
        'prompt_toolkit',
        'prompt_toolkit.shortcuts',
        'prompt_toolkit.styles',
        'prompt_toolkit.formatted_text',
    ],
    
    # Extra runtime hooks (scripts to execute before the app)
    hookspath=[],
    
    # Runtime hooks
    runtime_hooks=[],
    
    # Modules to explicitly exclude from the build
    excludes=['tkinter', 'matplotlib', 'PyQt5', 'PySide2', 'IPython', 'test'],
    
    # Don't try to find unresolvable dynamic modules
    noarchive=False,
)

# Add Windows-specific imports if on Windows
if is_windows:
    a.hiddenimports.extend([
        'win32api',
        'win32con',
        'win32service',
        'win32serviceutil',
        'win32event',
        'servicemanager',
        'winreg',
        'win32timezone',  # Often missed but needed by pywin32
    ])

# Add platform-specific libraries based on requirements
if is_linux:
    a.hiddenimports.append('pwd')  # User management

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Create the executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # Avoid stripping symbols to prevent issues with some libraries
    upx=True,  # Enable UPX compression
    upx_exclude=[],  # Libraries to exclude from UPX compression
    runtime_tmpdir=None,  # Use a temporary directory during runtime
    console=True,  # Keep the console to see error output
    icon=None,  # Add your icon file here if you have one
    version_info={
        'FileVersion': '1.0.0',
        'ProductVersion': '1.0.0',
        'ProductName': 'Log Collector',
        'FileDescription': 'High-performance log collection and processing system',
        'InternalName': 'LogCollector',
        'OriginalFilename': 'Log_Collector.exe' if is_windows else 'Log_Collector',
        'CompanyName': 'K.G - The Hawk',
    }
)

# Create a separate service executable for Windows
if is_windows:
    service_a = Analysis(
        [os.path.join(root_dir, 'log_collector_service.py')],
        pathex=[root_dir],
        binaries=[],
        datas=[
            (os.path.join(root_dir, 'log_collector'), 'log_collector'),
            (data_dir, 'data'),
            (logs_dir, 'logs'),
        ],
        hiddenimports=a.hiddenimports,  # Reuse the same hidden imports
        hookspath=[],
        runtime_hooks=[],
        excludes=['tkinter', 'matplotlib', 'PyQt5', 'PySide2', 'IPython', 'test'],
        noarchive=False,
    )
    
    service_pyz = PYZ(service_a.pure, service_a.zipped_data, cipher=None)
    
    service_exe = EXE(
        service_pyz,
        service_a.scripts,
        service_a.binaries,
        service_a.zipfiles,
        service_a.datas,
        [],
        name='log_collector_service',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=True,
        icon=None,
    )
