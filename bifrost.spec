# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Bifrost robot control application.

Produces a single portable exe. External folders live next to the exe:
  bifrost.exe
  addons/          <- addon packages (discovered at runtime)
  calibration/     <- writable config JSONs (created on first launch)
"""

import sys
import sysconfig
from pathlib import Path

block_cipher = None
src_dir = Path(SPECPATH)
site_packages = Path(sysconfig.get_paths()['purelib'])

# Resources bundled INSIDE the exe (extracted to temp dir at runtime)
# - STLs are read-only 3D models
# - Default configs are copied to calibration/ on first launch
datas = [
    (str(src_dir / 'STLs'), 'STLs'),
    (str(src_dir / 'dh_parameters.json'), '.'),
    (str(src_dir / 'gripper_calibration.json'), '.'),
    (str(src_dir / 'coordinate_frames.json'), '.'),
]

# Add optional config files if they exist
for optional in ['home_position.json', 'park_position.json']:
    if (src_dir / optional).exists():
        datas.append((str(src_dir / optional), '.'))

# Native DLLs for voice_control addon (vosk + sounddevice)
# These MUST be added as binaries with explicit destination — adding as datas
# causes PyInstaller to reclassify them and then drop them as "system" DLLs.
# vosk.__init__ expects DLLs in the vosk/ package directory; the runtime hook
# (pyi_rth_vosk.py) copies them there from wherever they end up.
binaries = []
vosk_dir = site_packages / 'vosk'
for dll in vosk_dir.glob('*.dll'):
    binaries.append((str(dll), '.'))

sd_data_dir = site_packages / '_sounddevice_data' / 'portaudio-binaries'
for dll in sd_data_dir.glob('*.dll'):
    binaries.append((str(dll), '.'))

a = Analysis(
    ['bifrost.py'],
    pathex=[str(src_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'OpenGL.platform.win32',
        'OpenGL.arrays.vbo',
        'OpenGL.arrays.numpymodule',
        'OpenGL.arrays.arraydatatype',
        'OpenGL.arrays.formathandler',
        'OpenGL.converters',
        'scipy.spatial.transform._rotation',
        'scipy._cyutility',
        # Used by addons (external, not analysed by PyInstaller)
        'PyQt5.QtNetwork',
        'vosk',
        'vosk.vosk_cffi',
        'sounddevice',
        '_sounddevice_data',
        'srt',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(src_dir / 'pyi_rth_vosk.py')],
    excludes=[
        'OpenGL_accelerate',
        'scipy.integrate',
        'scipy.stats',
        'scipy.optimize',
        'scipy.interpolate',
        'scipy.signal',
        'scipy.ndimage',
        'scipy.io',
        'scipy.fft',
        'pytest',
        'setuptools',
        '_pytest',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='bifrost',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
