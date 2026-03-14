"""
Bifrost Addon API

Public API surface exposed to addons. Wraps internal objects so addons
don't couple directly to implementation details.
"""

import logging
from pathlib import Path

import differential_kinematics as diff_kin
from command_builder import CommandBuilder

logger = logging.getLogger(__name__)


class BifrostAPI:
    """API provided to addons for interacting with the robot and application.

    Addons receive an instance of this class in their ``__init__``.
    All robot interaction should go through this API.
    """

    def __init__(self, robot_controller, command_sender, connection_manager,
                 gripper_controller, data_dir):
        """Initialise the API with references to internal components.

        This is called by BifrostGUI — addons should NOT construct this.
        """
        self._robot_controller = robot_controller
        self._command_sender = command_sender
        self._connection_manager = connection_manager
        self._gripper_controller = gripper_controller
        self._data_dir = Path(data_dir) if data_dir else Path(".")

        # Current robot state (updated via _emit_state_change)
        self._current_state = "Idle"

        # Simulation mode state (updated via _set_simulation_mode)
        self._simulation_mode = False
        self._simulation_move_callback = None

        # 3D visualizer reference (set via _set_position_canvas)
        self._position_canvas = None

        # Event listener lists
        self._position_listeners = []
        self._connection_listeners = []
        self._state_listeners = []

    # -----------------------------------------------------------------
    # Robot State (read-only)
    # -----------------------------------------------------------------

    def get_joint_positions(self):
        """Get current joint positions.

        Returns:
            dict: ``{'Art1': float, 'Art2': float, ..., 'Art6': float, 'Gripper': float}``
        """
        return dict(self._robot_controller.current_positions)

    def get_connection_status(self):
        """Check whether the robot is connected.

        Returns:
            bool: True if connected.
        """
        return self._connection_manager.is_connected

    def get_robot_state(self):
        """Get the current robot state string.

        Returns:
            str: One of ``"Idle"``, ``"Run"``, ``"Hold"``, ``"Alarm"``.
        """
        return self._current_state

    def is_simulation_mode(self):
        """Check whether the app is in simulation mode.

        In simulation mode, movement commands update the 3D visualization
        directly without requiring a serial connection.

        Returns:
            bool: True if simulation mode is active.
        """
        return self._simulation_mode

    # -----------------------------------------------------------------
    # Commands
    # -----------------------------------------------------------------

    def send_gcode(self, command):
        """Send a raw G-code command.

        Args:
            command: G-code string (e.g. ``"G1 X10 F1000"``).

        Returns:
            bool: True if sent successfully.
        """
        return self._command_sender.send_if_connected(command)

    def home(self):
        """Send the homing command (G28)."""
        return self._command_sender.send_if_connected("G28")

    def emergency_stop(self):
        """Send quick-stop (M410) to freeze motors in place."""
        return self._command_sender.send_if_connected("M410")

    def set_gripper(self, percent):
        """Move the gripper to a position.

        Args:
            percent: 0 (fully closed) to 100 (fully open). Clamped to 0-100.
        """
        if self._gripper_controller:
            clamped = max(0, min(100, percent))
            self._gripper_controller.move(clamped)

    def move_joints(self, q1, q2, q3, q4, q5, q6, gripper=None,
                    feedrate=1000, movement_type="G1", duration=0.5):
        """Move robot joints to specified angles.

        Works in both hardware and simulation mode:
        - Hardware: converts J5/J6 to differential V/W, sends G-code.
        - Simulation: calls the visualization callback directly.

        Args:
            q1-q6: Joint angles in degrees.
            gripper: Gripper position 0-100%. None to leave unchanged.
            feedrate: Feedrate in mm/min (hardware path only).
            movement_type: ``"G0"`` (rapid) or ``"G1"`` (linear).
            duration: Animation duration in seconds (simulation path only).

        Returns:
            bool: True if the command was sent/executed.
        """
        # Simulation path — no serial connection needed
        if self._simulation_mode and self._simulation_move_callback:
            grip_val = gripper if gripper is not None else 0
            try:
                self._simulation_move_callback(
                    q1, q2, q3, q4, q5, q6, grip_val, duration
                )
            except Exception:
                logger.exception("Error in simulation move callback")
                return False
            return True

        # Hardware path — requires connection
        if not self._connection_manager.is_connected:
            return False

        motor_v, motor_w = diff_kin.DifferentialKinematics.joint_to_motor(q5, q6)

        command = CommandBuilder.build_axis_command(
            movement_type,
            {"X": q1, "Y": q2, "Z": q3, "U": q4, "V": motor_v, "W": motor_w},
            f" F{feedrate}"
        )
        self._command_sender.send_if_connected(command)

        if gripper is not None and gripper > 0:
            self.set_gripper(gripper)

        return True

    def can_move(self):
        """Check if the robot can accept movement commands.

        Returns True if either connected to hardware or in simulation mode.

        Returns:
            bool: True if movement commands will be accepted.
        """
        if self._simulation_mode and self._simulation_move_callback:
            return True
        return self._connection_manager.is_connected

    # -----------------------------------------------------------------
    # Event Subscriptions
    # -----------------------------------------------------------------

    def on_position_update(self, callback):
        """Subscribe to position updates.

        Callbacks are invoked in the GUI thread — safe to update Qt widgets.

        Args:
            callback: Called with a dict of positions whenever the firmware
                      reports new joint positions (approx 3.3 Hz).
                      Keys include ``Art1``-``Art6`` plus firmware axes.
        """
        self._position_listeners.append(callback)

    def on_connection_change(self, callback):
        """Subscribe to connection state changes.

        Args:
            callback: Called with ``(is_connected: bool)`` on connect/disconnect.
        """
        self._connection_listeners.append(callback)

    def on_state_change(self, callback):
        """Subscribe to robot state changes.

        Args:
            callback: Called with ``(state: str)`` — "Idle", "Run", "Hold", or "Alarm".
        """
        self._state_listeners.append(callback)

    # -----------------------------------------------------------------
    # 3D Visualization
    # -----------------------------------------------------------------

    def set_trajectory_preview(self, tcp_points):
        """Display a trajectory preview in the 3D visualizer.

        Args:
            tcp_points: List of (x, y, z) tuples, or None to clear.
        """
        if self._position_canvas is not None:
            self._position_canvas.set_sequence_preview(tcp_points)

    def clear_trajectory_preview(self):
        """Clear any trajectory preview from the 3D visualizer."""
        if self._position_canvas is not None:
            self._position_canvas.set_sequence_preview(None)

    # -----------------------------------------------------------------
    # Addon Data
    # -----------------------------------------------------------------

    def get_addon_data_dir(self, addon_name):
        """Get a persistent data directory for the addon.

        Creates the directory if it doesn't exist.

        Args:
            addon_name: The addon's name (used as subdirectory name).

        Returns:
            Path: Path to the addon's data directory.
        """
        data_dir = self._data_dir / "addon_data" / addon_name
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    # -----------------------------------------------------------------
    # Internal — called by BifrostGUI, NOT by addons
    # -----------------------------------------------------------------

    def _emit_position_update(self, positions):
        """Dispatch position update to all registered listeners."""
        for cb in self._position_listeners:
            try:
                cb(positions)
            except Exception:
                logger.exception("Error in addon position listener")

    def _emit_connection_change(self, connected):
        """Dispatch connection state change to all registered listeners."""
        for cb in self._connection_listeners:
            try:
                cb(connected)
            except Exception:
                logger.exception("Error in addon connection listener")

    def _emit_state_change(self, state):
        """Dispatch robot state change to all registered listeners."""
        self._current_state = state
        for cb in self._state_listeners:
            try:
                cb(state)
            except Exception:
                logger.exception("Error in addon state listener")

    def _set_simulation_mode(self, enabled):
        """Update simulation mode state (called by BifrostGUI)."""
        self._simulation_mode = enabled

    def _set_simulation_callback(self, callback):
        """Set the simulation move callback (called by BifrostGUI)."""
        self._simulation_move_callback = callback

    def _set_position_canvas(self, canvas):
        """Set the 3D visualizer reference (called by BifrostGUI)."""
        self._position_canvas = canvas

    def _clear_all_listeners(self):
        """Remove all registered event listeners (called on app shutdown)."""
        self._position_listeners.clear()
        self._connection_listeners.clear()
        self._state_listeners.clear()
