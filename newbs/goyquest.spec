# PyInstaller spec — tuned to reduce antivirus false positives.
# - onedir (not onefile): avoids temp-folder extraction heuristics
# - no UPX compression: UPX is a common AV trigger
# - version metadata: helps Windows identify the binary

import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH).resolve()
repo = root.parent

a = Analysis(
    [str(root / "goyquest_gui.py")],
    pathex=[str(repo)],
    binaries=[],
    datas=[(str(repo / "react_http.py"), ".")],
    hiddenimports=[
        "react_http",
        "requests",
        "urllib3",
        "certifi",
        "charset_normalizer",
        "idna",
        "websocket",
        "websocket._app",
        "websocket._core",
        "websocket._exceptions",
        "websocket._handshake",
        "websocket._http",
        "websocket._logging",
        "websocket._socket",
        "websocket._ssl_compat",
        "websocket._url",
        "websocket._utils",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(root / "utf8_runtime_hook.py")],
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
    [],
    exclude_binaries=True,
    name="Goyquest",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(root / "version_info.txt"),
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Goyquest",
)