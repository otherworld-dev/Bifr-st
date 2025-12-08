"""
Movement Controller Module
Handles robot movement commands and kinematics calculations

This module provides:
- FK (Forward Kinematics) joint movement commands
- Differential kinematics for wrist joints (Art5/Art6)
- Gripper control
- Special commands (homing, zero position, emergency stop)
"""

import logging
from typing import Dict, Tuple, Optional, Callable
from dataclasses import dataclass

import config
import differential_kinematics as diff_kin
import inverse_kinematics as ik
from command_builder import CommandBuilder
from robot_controller import RobotController

logger = logging.getLogger(__name__)


@dataclass
class MovementParams:
    """Parameters for movement commands"""
    movement_type: str  # "G0" (rapid) or "G1" (linear)
    feedrate: str  # Feedrate suffix (e.g., " F1000") or empty string


@dataclass
class IKResult:
    """Result of IK calculation"""
    valid: bool
    q1: float = 0.0
    q2: float = 0.0
    q3: float = 0.0
    q4: float = 0.0
    q5: float = 0.0
    q6: float = 0.0
    error_msg: str = ""


class MovementController:
    """
    Controls robot movements and command generation.

    This class handles the logic of movement calculations and command building,
    separate from GUI concerns. It works with RobotController for state tracking.
    """

    # Joint configuration (maps joint names to firmware axes)
    JOINT_CONFIG = {
        'Art1': {'axis': 'X', 'type': 'simple', 'log_name': 'Art1 (Joint 1)'},
        'Art2': {'axis': 'Y', 'type': 'coupled', 'log_name': 'Art2 (Joint 2 - COUPLED)', 'drives': '1+2'},
        'Art3': {'axis': 'Z', 'type': 'simple', 'log_name': 'Art3 (Joint 3)'},
        'Art4': {'axis': 'U', 'type': 'simple', 'log_name': 'Art4 (Joint 4)'},
        'Art5': {'axis': 'V+W', 'type': 'differential', 'log_name': 'Art5 (DIFFERENTIAL)'},
        'Art6': {'axis': 'V+W', 'type': 'differential', 'log_name': 'Art6 (DIFFERENTIAL)'},
    }

    def __init__(self, robot_controller: RobotController, command_sender=None):
        """
        Initialize movement controller.

        Args:
            robot_controller: RobotController instance for state tracking
            command_sender: Optional command sender for direct execution
        """
        self.robot_controller = robot_controller
        self.command_sender = command_sender

    def build_joint_move_command(
        self,
        joint_name: str,
        joint_value: float,
        movement_params: MovementParams
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Build command for moving a single joint.

        Args:
            joint_name: Name of joint ('Art1' through 'Art6')
            joint_value: Target angle in degrees
            movement_params: Movement type and feedrate

        Returns:
            Tuple of (command_string, log_message) or (None, error_message)
        """
        if joint_name not in self.JOINT_CONFIG:
            return None, f"Unknown joint: {joint_name}"

        joint_config = self.JOINT_CONFIG[joint_name]
        joint_type = joint_config['type']

        if joint_type in ('simple', 'coupled'):
            return self._build_simple_move(joint_name, joint_value, joint_config, movement_params)
        elif joint_type == 'differential':
            return self._build_differential_move(joint_name, joint_value, joint_config, movement_params)
        else:
            return None, f"Unknown joint type: {joint_type}"

    def _build_simple_move(
        self,
        joint_name: str,
        joint_value: float,
        joint_config: Dict,
        movement_params: MovementParams
    ) -> Tuple[str, str]:
        """Build command for simple or coupled joint."""
        axis = joint_config['axis']
        log_name = joint_config['log_name']

        # Build log message
        if joint_config['type'] == 'coupled':
            log_msg = f"{log_name} commanded to: {joint_value}° -> Axis: {axis} (Drives {joint_config['drives']})"
        else:
            log_msg = f"{log_name} commanded to: {joint_value}° -> Axis: {axis}"

        # Build command
        command = CommandBuilder.build_single_axis_command(
            movement_params.movement_type,
            axis,
            joint_value,
            movement_params.feedrate
        )

        return command, log_msg

    def _build_differential_move(
        self,
        joint_name: str,
        joint_value: float,
        joint_config: Dict,
        movement_params: MovementParams
    ) -> Tuple[str, str]:
        """Build command for differential joint (Art5/Art6)."""
        # Check if differential system is initialized
        if not self.robot_controller.check_differential_initialized():
            logger.warning("No position feedback received yet - differential control may be inaccurate!")

        # Calculate motor positions
        motor_v, motor_w, kept_value = self.robot_controller.calculate_differential_move(
            joint_name, joint_value
        )

        # Update controller state
        self.robot_controller.update_differential_motors(motor_v, motor_w)

        # Build log message
        kept_joint = 'Art6' if joint_name == 'Art5' else 'Art5'
        log_msg = (
            f"{joint_config['log_name']} commanded to: {joint_value}° "
            f"-> Motors: V={motor_v:.2f}° W={motor_w:.2f}° ({kept_joint} kept at {kept_value:.2f}°)"
        )

        # Build command
        command = CommandBuilder.build_axis_command(
            movement_params.movement_type,
            {"V": motor_v, "W": motor_w},
            movement_params.feedrate
        )

        return command, log_msg

    def build_move_all_command(
        self,
        joint_values: Dict[str, float],
        movement_params: MovementParams
    ) -> Tuple[str, str]:
        """
        Build command to move all joints simultaneously.

        Args:
            joint_values: Dictionary with Art1-Art6 values in degrees
            movement_params: Movement type and feedrate

        Returns:
            Tuple of (command_string, log_message)
        """
        art5 = joint_values.get('Art5', 0.0)
        art6 = joint_values.get('Art6', 0.0)

        # Calculate differential motor positions
        motor_v, motor_w = diff_kin.DifferentialKinematics.joint_to_motor(art5, art6)

        log_msg = f"MoveAll: Art5={art5}° Art6={art6}° -> Differential: V={motor_v:.2f}° W={motor_w:.2f}°"

        # Build command with all axes
        command = CommandBuilder.build_axis_command(
            movement_params.movement_type,
            {
                "X": joint_values.get('Art1', 0.0),
                "Y": joint_values.get('Art2', 0.0),
                "Z": joint_values.get('Art3', 0.0),
                "U": joint_values.get('Art4', 0.0),
                "V": motor_v,
                "W": motor_w
            },
            movement_params.feedrate
        )

        return command, log_msg

    def build_gripper_command(self, percent: float) -> Tuple[str, str]:
        """
        Build command for gripper movement.

        Args:
            percent: Gripper position 0-100%

        Returns:
            Tuple of (command_string, log_message)
        """
        # Convert percent to PWM value
        pwm_value = (config.GRIPPER_PWM_MAX / config.GRIPPER_PERCENT_MAX) * percent

        # Map PWM to servo angle for RRF M280 command
        servo_angle = int((pwm_value / 255.0) * 180.0)

        command = f"M280 P0 S{servo_angle}"
        log_msg = f"Gripper: {percent}% -> PWM={pwm_value:.0f} -> Servo={servo_angle}°"

        return command, log_msg

    def build_homing_command(self) -> str:
        """Build G28 homing command."""
        return "G28"

    def build_zero_position_command(self) -> str:
        """Build command to move all axes to zero."""
        return CommandBuilder.build_axis_command(
            "G0",
            {"X": 0, "Y": 0, "Z": 0, "U": 0, "V": 0, "W": 0}
        )

    def build_kill_alarm_command(self) -> str:
        """Build M999 reset command."""
        return "M999"

    def build_pause_command(self) -> str:
        """Build M410 quick stop command."""
        return "M410"

    def build_emergency_stop_command(self) -> str:
        """Build M112 emergency stop command."""
        return "M112"

    def calculate_ik(
        self,
        x: float,
        y: float,
        z: float,
        roll: float = 0,
        pitch: float = -1.5708,  # -π/2 (tool down)
        yaw: float = 0
    ) -> IKResult:
        """
        Calculate inverse kinematics for target position.

        Args:
            x, y, z: Target position in mm
            roll, pitch, yaw: Target orientation in radians

        Returns:
            IKResult with joint angles or error
        """
        solution = ik.solve_ik_full(x, y, z, roll=roll, pitch=pitch, yaw=yaw)

        if solution.valid:
            return IKResult(
                valid=True,
                q1=solution.q1,
                q2=solution.q2,
                q3=solution.q3,
                q4=solution.q4,
                q5=solution.q5,
                q6=solution.q6
            )
        else:
            return IKResult(
                valid=False,
                error_msg=solution.error_msg
            )

    def execute_command(
        self,
        command: str,
        error_callback: Optional[Callable] = None
    ) -> bool:
        """
        Execute a command via the command sender.

        Args:
            command: G-code command string
            error_callback: Optional callback for connection errors

        Returns:
            True if sent successfully, False otherwise
        """
        if self.command_sender is None:
            logger.warning("No command sender configured")
            return False

        return self.command_sender.send_if_connected(command, error_callback=error_callback)


def get_movement_params_from_gui(gui) -> MovementParams:
    """
    Extract movement parameters from GUI widgets.

    This is a helper function to bridge GUI state to MovementController.

    Args:
        gui: GUI instance with G0/G1 radio buttons and feedrate input

    Returns:
        MovementParams with movement type and feedrate
    """
    if gui.G0MoveRadioButton.isChecked():
        return MovementParams(movement_type="G0", feedrate="")
    else:
        feedrate = gui.FeedRateInput.text()
        return MovementParams(
            movement_type="G1",
            feedrate=f" F{feedrate}" if feedrate else ""
        )
