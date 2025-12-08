"""
Gripper Controller Module
Handles gripper/servo control logic

This module provides:
- Gripper position control (0-100%)
- Percent to PWM to servo angle conversion
- Preset positions (open/close)
- Slider/spinbox synchronization via callbacks
"""

import logging
from typing import Optional, Callable
from dataclasses import dataclass

import config

logger = logging.getLogger(__name__)


@dataclass
class GripperState:
    """Container for gripper state"""
    position_percent: float = 0.0
    pwm_value: float = 0.0
    servo_angle: int = 0

    @staticmethod
    def from_percent(percent: float) -> 'GripperState':
        """Create state from percentage value"""
        pwm = GripperController.percent_to_pwm(percent)
        angle = GripperController.pwm_to_servo_angle(pwm)
        return GripperState(
            position_percent=percent,
            pwm_value=pwm,
            servo_angle=angle
        )


class GripperController:
    """
    Controls gripper/servo operations.

    This class handles gripper control logic, using callbacks
    for all GUI updates to maintain decoupling.
    """

    # Preset values
    PRESET_CLOSED = 0
    PRESET_OPEN = 100

    def __init__(
        self,
        command_sender=None,
        spinbox_update_callback: Optional[Callable[[float], None]] = None,
        slider_update_callback: Optional[Callable[[int], None]] = None,
        no_connection_callback: Optional[Callable[[], None]] = None
    ):
        """
        Initialize gripper controller.

        Args:
            command_sender: CommandSender for sending gripper commands
            spinbox_update_callback: Callback(value) to update spinbox
            slider_update_callback: Callback(value) to update slider
            no_connection_callback: Callback() when serial not connected
        """
        self.command_sender = command_sender
        self.spinbox_update_callback = spinbox_update_callback
        self.slider_update_callback = slider_update_callback
        self.no_connection_callback = no_connection_callback

        # Current state
        self._current_position = 0.0

        # Jog mode state (synced from main controller)
        self.jog_mode_enabled = False

    @property
    def current_position(self) -> float:
        """Get current gripper position (0-100%)"""
        return self._current_position

    def set_jog_mode(self, enabled: bool) -> None:
        """Set jog mode state"""
        self.jog_mode_enabled = enabled
        logger.debug(f"Gripper jog mode {'enabled' if enabled else 'disabled'}")

    @staticmethod
    def percent_to_pwm(percent: float) -> float:
        """
        Convert gripper percentage (0-100) to PWM value using calibrated range.

        Args:
            percent: Gripper position as percentage (0-100)
                    0% = closed, 100% = open

        Returns:
            PWM value within calibrated range (GRIPPER_PWM_CLOSED to GRIPPER_PWM_OPEN)
        """
        # Linear interpolation between closed and open PWM values
        pwm_closed = config.GRIPPER_PWM_CLOSED
        pwm_open = config.GRIPPER_PWM_OPEN
        return pwm_closed + (percent / 100.0) * (pwm_open - pwm_closed)

    @staticmethod
    def pwm_to_servo_angle(pwm_value: float) -> int:
        """
        Convert PWM value to servo angle for M280 command.

        Args:
            pwm_value: PWM value (0-255)

        Returns:
            Servo angle (0-180)
        """
        return int((pwm_value / 255.0) * 180.0)

    @staticmethod
    def percent_to_servo_angle(percent: float) -> int:
        """
        Convert percentage directly to servo angle.

        Args:
            percent: Gripper position as percentage (0-100)

        Returns:
            Servo angle (0-180)
        """
        pwm = GripperController.percent_to_pwm(percent)
        return GripperController.pwm_to_servo_angle(pwm)

    def get_state(self, percent: float) -> GripperState:
        """
        Get gripper state for a given percentage.

        Args:
            percent: Gripper position as percentage

        Returns:
            GripperState with all converted values
        """
        return GripperState.from_percent(percent)

    def build_command(self, percent: float) -> str:
        """
        Build M280 servo command for gripper position.

        Args:
            percent: Gripper position as percentage (0-100)

        Returns:
            G-code command string
        """
        servo_angle = self.percent_to_servo_angle(percent)
        return f"M280 P0 S{servo_angle}"

    def move(self, percent: float) -> bool:
        """
        Move gripper to specified position.

        Args:
            percent: Target position as percentage (0-100)

        Returns:
            True if command sent, False otherwise
        """
        self._current_position = percent

        command = self.build_command(percent)

        logger.info(f"Gripper move: {percent}% -> {command}")

        if not self.command_sender:
            logger.warning("No command sender configured")
            return False

        return self.command_sender.send_if_connected(
            command,
            error_callback=self.no_connection_callback
        )

    def move_to_preset(self, preset: str) -> bool:
        """
        Move gripper to preset position.

        Args:
            preset: 'open' or 'closed'

        Returns:
            True if command sent, False otherwise
        """
        if preset.lower() == 'open':
            position = self.PRESET_OPEN
        elif preset.lower() in ('closed', 'close'):
            position = self.PRESET_CLOSED
        else:
            logger.warning(f"Unknown gripper preset: {preset}")
            return False

        logger.info(f"Gripper preset: {preset.capitalize()} ({position}%)")

        # Update GUI via callback
        if self.spinbox_update_callback:
            self.spinbox_update_callback(position)

        return self.move(position)

    def adjust(self, delta: float, current_value: float) -> float:
        """
        Calculate new gripper value after adjustment.

        Args:
            delta: Amount to add (positive or negative)
            current_value: Current gripper percentage

        Returns:
            New gripper percentage (clamped to 0-100)
        """
        new_value = current_value + delta
        # Clamp to valid range
        new_value = max(0.0, min(100.0, new_value))
        return new_value

    def slider_changed(self, slider_value: int) -> None:
        """
        Handle slider value change - update spinbox.

        Args:
            slider_value: Slider value (typically same as percentage for gripper)
        """
        if self.spinbox_update_callback:
            self.spinbox_update_callback(float(slider_value))

    def spinbox_changed(self, spinbox_value: float) -> None:
        """
        Handle spinbox value change - update slider.

        Args:
            spinbox_value: Spinbox value (0-100)
        """
        if self.slider_update_callback:
            self.slider_update_callback(int(spinbox_value))


def create_gripper_command(percent: float) -> str:
    """
    Create gripper command for given percentage.

    Args:
        percent: Gripper position as percentage (0-100)

    Returns:
        M280 G-code command string
    """
    servo_angle = GripperController.percent_to_servo_angle(percent)
    return f"M280 P0 S{servo_angle}"
