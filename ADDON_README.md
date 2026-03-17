# Bifrost Addon System

The addon system lets you extend Bifrost with new features without modifying the core application. Each addon gets its own tab in the mode bar and full access to the robot through the `BifrostAPI`.

## Quick Start

1. Create a folder inside `addons/` with your addon name
2. Add an `__init__.py` that exposes your addon class
3. Add your addon class (subclass of `AddonBase`)
4. Restart Bifrost — your tab appears automatically

### Minimal Example

```
addons/
  my_addon/
    __init__.py
    addon.py
```

**`addons/my_addon/__init__.py`**

```python
from .addon import MyAddon
addon_class = MyAddon
```

**`addons/my_addon/addon.py`**

```python
from addon_base import AddonBase
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout


class MyAddon(AddonBase):
    name = "My Addon"
    version = "1.0.0"
    description = "A short description of what this addon does"
    icon = "🔌"  # Emoji shown on the mode tab

    def create_panel(self):
        """Build and return the QWidget for your tab."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("Hello from My Addon!"))
        return panel
```

That's it. Bifrost discovers the package, imports `addon_class`, calls `create_panel()`, and registers the returned widget as a new mode tab.

---

## Addon Structure

| File | Purpose |
|------|---------|
| `__init__.py` | **Required.** Must define `addon_class = YourAddonClass` |
| `addon.py` | Your addon class (subclass of `AddonBase`) |
| `requirements.txt` | Optional. Lists pip dependencies your addon needs |
| Any other files | Your addon can have as many modules as needed |

### Package Naming

Your addon folder name is used as the Python package name. Avoid names that clash with standard library or common third-party modules (e.g., don't name your addon `logging`, `serial`, `config`, etc.).

---

## AddonBase Class

All addons must subclass `AddonBase` from `addon_base.py`.

### Required Metadata

Set these as class attributes:

```python
class MyAddon(AddonBase):
    name = "My Addon"           # Display name (shown in logs)
    version = "1.0.0"           # Semantic version
    description = "What it does" # Short description
    icon = "🔌"                  # Emoji prefix for the mode tab button
```

### Lifecycle Methods

| Method | When Called | Purpose |
|--------|-----------|---------|
| `__init__(self, api)` | Addon instantiated | Store `self.api` reference. Don't create UI here. |
| `create_panel(self)` | After `__init__` | **Required.** Return a `QWidget` for your mode tab. |
| `on_activate(self)` | User clicks your tab | Resume updates, start timers, etc. |
| `on_deactivate(self)` | User leaves your tab | Pause expensive work if needed. |
| `on_unload(self)` | App is shutting down | Clean up threads, close files, release resources. |

### Lifecycle Order

```
__init__(api)  →  create_panel()  →  [on_activate / on_deactivate]*  →  on_unload()
```

---

## BifrostAPI Reference

Your addon receives a `BifrostAPI` instance as `self.api`. This is your interface to the robot.

### Reading Robot State

```python
# Current joint angles as a dict
positions = self.api.get_joint_positions()
# Returns: {'Art1': 0.0, 'Art2': 45.0, ..., 'Art6': 0.0, 'Gripper': 50.0}

# Is the robot connected?
connected = self.api.get_connection_status()
# Returns: True or False

# Current robot state
state = self.api.get_robot_state()
# Returns: "Idle", "Run", "Hold", or "Alarm"
```

### Sending Commands

```python
# Send any raw G-code command
self.api.send_gcode("G1 X45 F1000")  # Move Art1 to 45 degrees
self.api.send_gcode("M114")           # Request position report

# Convenience methods
self.api.home()                # Home all axes (G28)
self.api.emergency_stop()      # Quick-stop, freeze motors (M410)
self.api.set_gripper(75)       # Move gripper to 75% open (clamped 0-100)
```

`send_gcode()` returns `True` if sent, `False` if the robot is not connected. The command is sent exactly as provided — refer to the [RepRapFirmware G-code reference](https://docs.duet3d.com/en/User_manual/Reference/Gcodes) for available commands.

### Subscribing to Events

All event callbacks are invoked in the **GUI thread**, so it's safe to update Qt widgets directly.

```python
# Position updates (~3.3 Hz while connected)
def on_position(positions):
    art1 = positions['Art1']
    art2 = positions['Art2']
    # Also available: Art3-Art6, X, Y, Z, U, V, W

self.api.on_position_update(on_position)

# Connection state changes
def on_connection(is_connected):
    if is_connected:
        print("Robot connected")

self.api.on_connection_change(on_connection)

# Robot state changes (Idle/Run/Hold/Alarm)
def on_state(state):
    if state == "Alarm":
        print("Robot alarm!")

self.api.on_state_change(on_state)
```

### Persistent Data Storage

Each addon gets its own data directory for saving settings, logs, or other files:

```python
data_dir = self.api.get_addon_data_dir(self.name)
# Returns a Path object, e.g. <app_root>/addon_data/My Addon/
# The directory is created automatically if it doesn't exist.

# Save/load addon settings
import json
settings_file = data_dir / "settings.json"
settings_file.write_text(json.dumps({"volume": 0.8}))
```

---

## Position Dict Keys

The position dict passed to `on_position_update` callbacks contains both joint-space and firmware-space keys:

| Key | Description |
|-----|-------------|
| `Art1` | Joint 1 angle (base rotation) |
| `Art2` | Joint 2 angle (shoulder) |
| `Art3` | Joint 3 angle (elbow) |
| `Art4` | Joint 4 angle (wrist roll) |
| `Art5` | Joint 5 angle (wrist pitch, computed from differential) |
| `Art6` | Joint 6 angle (wrist yaw, computed from differential) |
| `X` | Firmware axis X (same as Art1) |
| `Y` | Firmware axis Y (same as Art2) |
| `Z` | Firmware axis Z (same as Art3) |
| `U` | Firmware axis U (same as Art4) |
| `V` | Firmware motor V (differential, not a joint angle) |
| `W` | Firmware motor W (differential, not a joint angle) |

Use `Art1`-`Art6` for joint angles. Only use `V`/`W` if you need raw differential motor positions.

---

## Error Handling

The addon system isolates failures so a broken addon doesn't crash Bifrost:

- If your addon fails to **import**, it is skipped and an error is logged
- If `create_panel()` **throws**, the addon is skipped
- If an **event callback** throws, the exception is caught and logged — other listeners and the main app are unaffected
- If `on_unload()` **throws**, it is logged and the shutdown continues

Check the Bifrost log file (`bifrost_debug.log`) for addon-related errors.

---

## Complete Example

Here's a more complete addon that tracks joint positions and provides a "go to zero" button:

```python
from addon_base import AddonBase
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QGroupBox)
from PyQt5.QtCore import Qt


class ZeroPositionAddon(AddonBase):
    name = "Zero Position"
    version = "1.0.0"
    description = "Display positions and return robot to zero"
    icon = "🎯"

    def create_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Position display
        pos_group = QGroupBox("Current Joint Positions")
        pos_layout = QVBoxLayout(pos_group)
        self._labels = {}
        for i in range(1, 7):
            label = QLabel(f"A{i}: --")
            label.setStyleSheet("font-family: monospace; font-size: 14px;")
            pos_layout.addWidget(label)
            self._labels[f"Art{i}"] = label
        layout.addWidget(pos_group)

        # Connection status
        self._status = QLabel("Disconnected")
        self._status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status)

        # Action button
        self._zero_btn = QPushButton("Move All Joints to Zero")
        self._zero_btn.setMinimumHeight(40)
        self._zero_btn.clicked.connect(self._go_to_zero)
        self._zero_btn.setEnabled(False)
        layout.addWidget(self._zero_btn)

        layout.addStretch()

        # Subscribe to events
        self.api.on_position_update(self._update_positions)
        self.api.on_connection_change(self._update_connection)

        return panel

    def _update_positions(self, positions):
        for joint, label in self._labels.items():
            val = positions.get(joint, 0)
            label.setText(f"{joint}: {val:+8.2f} deg")

    def _update_connection(self, connected):
        self._zero_btn.setEnabled(connected)
        self._status.setText("Connected" if connected else "Disconnected")
        self._status.setStyleSheet(
            "color: green; font-weight: bold;"
            if connected else "color: red;"
        )

    def _go_to_zero(self):
        if self.api.get_connection_status():
            self.api.send_gcode("G1 X0 Y0 Z0 U0 F1000")
            self.api.send_gcode("G1 V0 W0 F1000")

    def on_unload(self):
        pass  # Nothing to clean up
```

---

## Tips

- **Keep imports inside `create_panel()`** if they're heavy or optional — this prevents import errors from blocking addon discovery
- **Use `on_activate` / `on_deactivate`** to pause expensive polling or timers when your tab isn't visible
- **Use `on_unload`** to stop background threads, close network connections, or save state
- **Log with `logging.getLogger(__name__)`** — output appears in `bifrost_debug.log`
- **Test in simulation mode** — check the Simulation checkbox in Bifrost to test without hardware
- **Don't modify `self.api` internals** — only use the public methods documented above. Internal `_`-prefixed methods may change without notice.
