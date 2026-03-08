# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for clash_cli.
#
# Bundles:
#   - All clash_cli Python modules
#   - The mihomo binary (vendor/mihomo) → placed at root of the bundle
#     so that sys._MEIPASS/mihomo is found by launcher.find_mihomo()
#
# Build inside Docker (Dockerfile.build):
#   pyinstaller clash_cli.spec --clean --noconfirm
#
# The mihomo binary must exist at vendor/mihomo relative to this spec file
# before running PyInstaller.  The Dockerfile.build handles this download.

import os
from pathlib import Path

# vendor/mihomo must exist at build time (downloaded by Dockerfile.build)
MIHOMO_BIN = Path(SPECPATH) / "vendor" / "mihomo"
if not MIHOMO_BIN.exists():
    raise FileNotFoundError(
        f"mihomo binary not found at {MIHOMO_BIN}\n"
        "Run: make download-mihomo   or use: make build (via Docker)"
    )

a = Analysis(
    ["clash_cli_entry.py"],
    pathex=[],
    binaries=[
        # Bundle mihomo into the root of the one-file extraction dir (sys._MEIPASS)
        (str(MIHOMO_BIN), "."),
    ],
    datas=[],
    hiddenimports=[
        "clash_cli",
        "clash_cli.cli",
        "clash_cli.config",
        "clash_cli.errors",
        "clash_cli.formatters",
        "clash_cli.daemon",
        "clash_cli.daemon.client",
        "clash_cli.daemon.launcher",
        "clash_cli.daemon.registry",
        "clash_cli.commands",
        "clash_cli.commands.start",
        "clash_cli.commands.profile",
        "clash_cli.commands.mode",
        "clash_cli.commands.proxy",
        "clash_cli.commands.rule",
        "clash_cli.commands.conn",
        "clash_cli.commands.log",
        "clash_cli.commands.dns",
        # Runtime deps
        "requests",
        "yaml",
        "keyring",
        "keyring.backends",
        "keyring.backends.SecretService",
        "keyring.backends.fail",
        "keyring.backends.null",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "email", "xml", "pdb", "doctest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="clash",
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
