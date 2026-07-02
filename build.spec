# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for CoDrifter
# Run: pyinstaller build.spec

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Collect full packages that use dynamic imports
elevenlabs_datas,  elevenlabs_bins,  elevenlabs_hidden  = collect_all("elevenlabs")
anthropic_datas,   anthropic_bins,   anthropic_hidden   = collect_all("anthropic")
xgboost_datas,     xgboost_bins,     xgboost_hidden     = collect_all("xgboost")
sklearn_hidden = collect_submodules("sklearn")
scipy_datas,       scipy_bins,       scipy_hidden       = collect_all("scipy")
sd_datas,          sd_bins,          sd_hidden          = collect_all("sounddevice")
cffi_datas,        cffi_bins,        cffi_hidden        = collect_all("cffi")
miniaudio_datas,   miniaudio_bins,   miniaudio_hidden   = collect_all("miniaudio")

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=elevenlabs_bins + anthropic_bins + xgboost_bins + scipy_bins + sd_bins + cffi_bins + miniaudio_bins,
    datas=[
        # App assets — land next to the exe (root of dist/CoDrifter/)
        ("driftline.ico",           "."),
        ("driftlinewordmark.png",   "."),
        ("version.py",              "."),
        # Bundled data
        ("data/corner_map.json",    "data"),
        # Package data
        *elevenlabs_datas,
        *anthropic_datas,
        *xgboost_datas,
        *scipy_datas,
        *sd_datas,
        *cffi_datas,
        *miniaudio_datas,
    ],
    hiddenimports=[
        # Qt
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.sip",
        # ML
        *xgboost_hidden,
        *sklearn_hidden,
        *scipy_hidden,
        "sklearn.neighbors._partition_nodes",
        # Voice / API
        *elevenlabs_hidden,
        *anthropic_hidden,
        "httpx",
        "httpcore",
        "anyio",
        "sniffio",
        "tokenizers",
        # Audio
        *sd_hidden,
        *cffi_hidden,
        *miniaudio_hidden,
        "sounddevice",
        "soundfile",
        "miniaudio",
        "_cffi_backend",
        # Windows
        "win32api",
        "win32con",
        "win32gui",
        "pywintypes",
        "ctypes",
        "ctypes.wintypes",
        "mmap",
        # Stdlib
        "csv",
        "queue",
        "threading",
        "pickle",
        "json",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "IPython",
        "notebook",
        "pytest",
        "tkinter",
        "_tkinter",
        "wx",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CoDrifter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # no terminal window — GUI only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="driftline.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CoDrifter",    # output: dist/CoDrifter/
)
