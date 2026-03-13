# Bifrost Addons

Place addon packages in this directory. Each addon is a Python package (a folder
with an `__init__.py`).

## Addon Structure

```
addons/
  my_addon/
    __init__.py       # Must define: addon_class = MyAddon
    addon.py          # Your addon class (subclass of AddonBase)
    requirements.txt  # Optional: extra pip dependencies
```

## Minimal Example

**`addons/my_addon/__init__.py`**:
```python
from .addon import MyAddon
addon_class = MyAddon
```

**`addons/my_addon/addon.py`**:
```python
from addon_base import AddonBase
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout


class MyAddon(AddonBase):
    name = "My Addon"
    version = "1.0.0"
    description = "A simple example addon"
    icon = "🔌"

    def create_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("Hello from My Addon!"))
        return panel
```

## API Reference

Your addon receives a `BifrostAPI` instance as `self.api`. Available methods:

### Robot State
- `api.get_joint_positions()` - Returns dict of current joint angles
- `api.get_connection_status()` - Returns True if connected
- `api.get_robot_state()` - Returns "Idle", "Run", "Hold", or "Alarm"

### Commands
- `api.send_gcode(command)` - Send raw G-code string
- `api.home()` - Home all axes
- `api.emergency_stop()` - Quick-stop (M410)
- `api.set_gripper(percent)` - Move gripper (0-100)

### Events
- `api.on_position_update(callback)` - Subscribe to position updates (~3.3Hz)
- `api.on_connection_change(callback)` - Subscribe to connect/disconnect
- `api.on_state_change(callback)` - Subscribe to state changes

### Data Storage
- `api.get_addon_data_dir(addon_name)` - Get persistent data directory

## Lifecycle

1. `__init__(api)` - Addon instantiated with API access
2. `create_panel()` - Return QWidget for the mode tab (called once)
3. `on_activate()` - User switched to your tab
4. `on_deactivate()` - User switched away from your tab
5. `on_unload()` - App is shutting down, clean up resources
