# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['startup.py'],
    pathex=[],
    binaries=[],
    datas=[('log_collector', 'log_collector'), ('log_collector_service.py', '.')],
    hiddenimports=['win32timezone', 'prompt_toolkit', 'colorama', 'psutil', 'requests'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Log_Collector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Log_Collector',
)
