# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files

pulp_datas = collect_data_files("pulp")
curl_cffi_datas, curl_cffi_binaries, curl_cffi_hiddenimports = collect_all("curl_cffi")


a = Analysis(
    ["desktop_main.py"],
    pathex=[],
    binaries=curl_cffi_binaries,
    datas=[
        ("templates", "templates"),
        ("static", "static"),
        ("data", "data"),
        ("config.yaml", "."),
    ] + pulp_datas + curl_cffi_datas,
    hiddenimports=curl_cffi_hiddenimports + ["_cffi_backend"],
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
    name="CardOptimiser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    name="CardOptimiser",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="CardOptimiser.app",
        icon=None,
        bundle_identifier="com.cardoptimiser.app",
    )
