"""
Sequence Playback

QTimer-driven sequence player that sends movements through the addon API.
Uses api.move_joints() which handles both hardware (G-code) and simulation
(direct visualization) paths automatically.
"""

import json
import time
import logging
from pathlib import Path

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from sequence_recorder import Sequence

logger = logging.getLogger(__name__)


class SequencePlayback(QObject):
    """Plays back sequence files through BifrostAPI."""

    playback_started = pyqtSignal(str)    # sequence name
    playback_finished = pyqtSignal()
    point_reached = pyqtSignal(int, int)  # current, total

    TIMER_INTERVAL_MS = 100

    def __init__(self, api):
        """
        Args:
            api: BifrostAPI instance for sending commands.
        """
        super().__init__()
        self._api = api
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)

        self._sequence = None
        self._current_index = 0
        self._last_move_time = 0.0
        self._is_playing = False

        # Movement settings (configurable from UI)
        self.movement_type = "G1"
        self.feedrate = 1000
        self.speed = 1.0

    @property
    def is_playing(self):
        return self._is_playing

    def load_sequence(self, filepath):
        """Load a sequence from a JSON file.

        Args:
            filepath: Path to the sequence .json file.

        Returns:
            Sequence or None on failure.
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            return Sequence.from_dict(data)
        except Exception:
            logger.exception(f"Failed to load sequence: {filepath}")
            return None

    def play(self, filepath):
        """Load and play a sequence file.

        Args:
            filepath: Path to the sequence .json file.

        Returns:
            bool: True if playback started.
        """
        if self._is_playing:
            logger.warning("Already playing a sequence")
            return False

        if not self._api.can_move():
            logger.warning("Cannot play sequence: not connected and not in simulation mode")
            return False

        state = self._api.get_robot_state()
        if state == "Alarm":
            logger.warning("Cannot play sequence: robot in Alarm state")
            return False

        sequence = self.load_sequence(filepath)
        if sequence is None or len(sequence.points) == 0:
            logger.warning(f"Sequence is empty or failed to load: {filepath}")
            return False

        self._sequence = sequence
        self._current_index = 0
        self._last_move_time = time.time()
        self._is_playing = True

        logger.info(
            f"Starting voice playback: '{sequence.name}' "
            f"({len(sequence.points)} points, {self.movement_type} F{self.feedrate})"
        )
        self.playback_started.emit(sequence.name)
        self._timer.start(self.TIMER_INTERVAL_MS)
        return True

    def stop(self):
        """Stop playback."""
        if self._is_playing:
            self._timer.stop()
            self._is_playing = False
            self._sequence = None
            logger.info("Voice playback stopped")
            self.playback_finished.emit()

    def _tick(self):
        """Called every TIMER_INTERVAL_MS by QTimer."""
        if not self._is_playing or self._sequence is None:
            self._timer.stop()
            return

        if self._current_index >= len(self._sequence.points):
            # Sequence complete
            self._timer.stop()
            self._is_playing = False
            logger.info(f"Voice playback complete: '{self._sequence.name}'")
            self._sequence = None
            self.playback_finished.emit()
            return

        point = self._sequence.points[self._current_index]

        # Check if delay has elapsed
        adjusted_delay = point.delay / self.speed if self.speed > 0 else point.delay
        elapsed = time.time() - self._last_move_time
        if elapsed < adjusted_delay:
            return  # Still waiting

        # Calculate duration for simulation interpolation
        duration = adjusted_delay if adjusted_delay > 0 else 0.5

        # Execute movement via API (handles both hardware and simulation)
        self._api.move_joints(
            point.q1, point.q2, point.q3,
            point.q4, point.q5, point.q6,
            gripper=point.gripper if point.gripper > 0 else None,
            feedrate=self.feedrate,
            movement_type=self.movement_type,
            duration=duration
        )

        self._last_move_time = time.time()
        self._current_index += 1
        self.point_reached.emit(self._current_index, len(self._sequence.points))

        logger.debug(
            f"Voice playback point {self._current_index}: "
            f"q1={point.q1:.1f} q2={point.q2:.1f} q3={point.q3:.1f} "
            f"q4={point.q4:.1f} q5={point.q5:.1f} q6={point.q6:.1f} "
            f"grip={point.gripper}"
        )
