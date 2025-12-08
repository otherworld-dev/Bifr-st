"""
Pytest configuration and shared fixtures for Bifrost tests
"""

import pytest
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def sample_firmware_positions():
    """Sample firmware position data from M114 response"""
    return {
        'X': 10.0,
        'Y': 20.0,
        'Z': 30.0,
        'U': 5.0,
        'V': 75.0,
        'W': 15.0
    }


@pytest.fixture
def home_position_firmware():
    """Firmware positions at home"""
    return {
        'X': 0.0,
        'Y': 0.0,
        'Z': 0.0,
        'U': 0.0,
        'V': 0.0,
        'W': 0.0
    }


@pytest.fixture
def sample_joint_angles():
    """Sample joint angles for testing"""
    return {
        'Art1': 0.0,
        'Art2': 90.0,
        'Art3': 45.0,
        'Art4': 0.0,
        'Art5': 30.0,
        'Art6': 45.0
    }


@pytest.fixture
def sample_m114_response():
    """Sample M114 response string"""
    return "X:10.500 Y:20.000 Z:-5.250 U:0.028 V:-110.000 W:-290.000"


@pytest.fixture
def sample_m119_response():
    """Sample M119 endstop response string"""
    return "Endstops - X: at min stop, Y: not stopped, Z: not stopped, U: not stopped, V: at min stop, W: at min stop"
