# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification file for dav2mkv.

Generate ``file_version_info.txt`` before building:
    python scripts/generate_file_version_info.py

This spec file includes optimizations to reduce antivirus false positives:
- Version information resource for legitimacy
- Disabled UPX compression (--noupx) which triggers heuristic detection
- Console application metadata
- Company and product information
"""

block_cipher = None

a = Analysis(
    ["src/dav2mkv/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("pyproject.toml", "."),
    ],
    hiddenimports=["dav2mkv"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="dav2mkv",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version="file_version_info.txt",
)
