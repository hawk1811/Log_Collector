# single_file_build.py
import os
import sys
import shutil
import platform
import subprocess

# First, run the cx_Freeze build
print("Running cx_Freeze build...")
os.system(f"{sys.executable} build_package.py build")

# Determine the PyInstaller command based on platform
is_windows = platform.system() == "Windows"
executable_name = "LogCollector.exe" if is_windows else "LogCollector"
onefile_executable = "LogCollector_Standalone.exe" if is_windows else "LogCollector_Standalone"

# Set path to the cx_Freeze built executable
exe_path = os.path.join("build", "exe", executable_name)

# Create a PyInstaller spec file
spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['{exe_path}'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='{onefile_executable}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""

with open("LogCollector.spec", "w") as f:
    f.write(spec_content)

# Run PyInstaller with the spec file
print("Creating single-file executable with PyInstaller...")
os.system(f"pyinstaller LogCollector.spec --onefile")

print(f"Single-file executable created: dist/{onefile_executable}")
