"""Centralised path resolution for Bifrost.

Handles the difference between running from source and running as a
frozen PyInstaller executable:

  Frozen layout (next to bifrost.exe):
    bifrost.exe
    addons/          <- addon packages (discovered at runtime)
    calibration/     <- writable config JSONs (created on first launch)

  Dev layout (project root):
    bifrost.py
    addons/
    *.json           <- configs live in project root directly
"""
import sys
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Files that get copied to the calibration dir on first launch
_DEFAULT_CONFIGS = [
    'dh_parameters.json',
    'gripper_calibration.json',
    'coordinate_frames.json',
    'home_position.json',
    'park_position.json',
]


def is_frozen() -> bool:
    """True when running as a PyInstaller bundle."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_exe_dir() -> Path:
    """Directory containing the executable (or project root in dev).

    Use this for resolving external folders that live next to the exe
    (addons/, calibration/).
    """
    if is_frozen():
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_bundle_dir() -> Path:
    """Read-only bundled resources (STLs, default configs).

    - Frozen: PyInstaller temp extraction directory
    - Dev: project root (directory containing this file)
    """
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def get_data_dir() -> Path:
    """Writable config/data directory.

    - Frozen: calibration/ folder next to the exe
    - Dev: project root (no change from current behaviour)
    """
    if is_frozen():
        return get_exe_dir() / 'calibration'
    return Path(__file__).parent


def initialize_data_dir() -> None:
    """Create the data directory and populate with default configs.

    Only copies files that don't already exist, so user edits are preserved.
    """
    if not is_frozen():
        return  # Nothing to do in dev mode

    data_dir = get_data_dir()
    data_dir.mkdir(exist_ok=True)

    bundle_dir = get_bundle_dir()
    for filename in _DEFAULT_CONFIGS:
        src = bundle_dir / filename
        dst = data_dir / filename
        if not dst.exists() and src.exists():
            shutil.copy2(src, dst)
            logger.info(f"Copied default config: {filename}")
