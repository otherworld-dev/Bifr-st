"""
Serial Thread Module
Background thread for serial I/O and position polling

This thread handles:
- Non-blocking reads from serial port
- Processing command queue (actual writes)
- Periodic position requests (M114)
- Periodic endstop status requests (M119)
- Detection of blocking commands (G28, G29, M999)
"""

import time
import logging
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal
import serial

import config

logger = logging.getLogger(__name__)


class SerialThread(QThread):
    """
    Background thread for serial communication.

    Emits serialSignal with received data strings.
    Special signal value "SERIAL-DISCONNECTED" indicates connection lost.
    """

    serialSignal = pyqtSignal(str)

    # Blocking commands that pause status polling
    BLOCKING_COMMANDS = ['G28', 'G29', 'M999']

    def __init__(self, serial_manager, parent=None):
        """
        Initialize serial thread.

        Args:
            serial_manager: SerialManager instance for I/O
            parent: Optional Qt parent object
        """
        super().__init__(parent)
        self.serial_manager = serial_manager
        self.running = True
        self.elapsed_time = time.time()
        self.endstop_check_time = time.time()
        self.status_polling_paused = False
        self.blocking_command_start_time = 0.0

    def stop(self) -> None:
        """Gracefully stop the thread."""
        self.running = False

    def run(self) -> None:
        """Main thread loop with non-blocking reads and command queue processing."""
        while self.running:
            if not self.serial_manager.isOpen():
                time.sleep(0.1)
                continue

            try:
                # Check if connection is still alive
                try:
                    bytes_available = self.serial_manager.inWaiting()
                except (OSError, serial.SerialException):
                    self.serialSignal.emit("SERIAL-DISCONNECTED")
                    logger.warning("Lost Serial connection!")
                    break

                current_time = time.time()

                # Process command queue
                self._process_command_queue(current_time)

                # Check for timeout on paused polling
                self._check_polling_timeout(current_time)

                # Send periodic status requests
                self._send_status_requests(current_time)

                # Read available data
                self._read_serial_data(bytes_available, current_time)

                # Small sleep to prevent busy-waiting
                time.sleep(config.SERIAL_THREAD_SLEEP)

            except Exception as e:
                logger.exception("Unexpected error in serial thread")
                time.sleep(0.1)

        logger.info("Serial thread stopped")

    def _process_command_queue(self, current_time: float) -> None:
        """Process next command from queue if available."""
        command = self.serial_manager.get_next_command()
        if command:
            success = self.serial_manager._write_internal(command)
            if not success:
                self.serialSignal.emit("SERIAL-DISCONNECTED")
                self.running = False
                return

            # Check if this is a blocking command
            command_str = command.decode('UTF-8', errors='replace').strip().upper()
            for block_cmd in self.BLOCKING_COMMANDS:
                if command_str.startswith(block_cmd):
                    self.status_polling_paused = True
                    self.blocking_command_start_time = current_time
                    logger.info(f"Pausing status polling for blocking command: {command_str}")
                    break

    def _check_polling_timeout(self, current_time: float) -> None:
        """Check for timeout on paused polling and force resume if needed."""
        if self.status_polling_paused:
            time_paused = current_time - self.blocking_command_start_time
            if time_paused >= config.BLOCKING_COMMAND_MAX_PAUSE:
                self.status_polling_paused = False
                logger.warning(
                    f"Forcing resume of status polling after {time_paused:.1f}s timeout "
                    f"(max: {config.BLOCKING_COMMAND_MAX_PAUSE}s)"
                )
                # Request immediate position update
                self._request_immediate_status()

    def _send_status_requests(self, current_time: float) -> None:
        """Send periodic M114 and M119 requests if not paused."""
        if self.status_polling_paused:
            return

        # Position request (M114)
        if current_time - self.elapsed_time > config.SERIAL_STATUS_REQUEST_INTERVAL:
            self.elapsed_time = current_time
            try:
                self.serial_manager.write(b"M114\n", priority=True)
            except Exception as e:
                logger.error(f"Error queuing status request: {e}")

        # Endstop request (M119)
        if current_time - self.endstop_check_time > config.SERIAL_ENDSTOP_REQUEST_INTERVAL:
            self.endstop_check_time = current_time
            try:
                self.serial_manager.write(b"M119\n", priority=True)
            except Exception as e:
                logger.error(f"Error queuing endstop request: {e}")

    def _read_serial_data(self, bytes_available: int, current_time: float) -> None:
        """Read and emit available serial data."""
        if bytes_available == 0:
            return

        try:
            # Batch processing: estimate lines available
            estimated_lines = max(1, min(10, bytes_available // 30))

            for _ in range(estimated_lines):
                if self.serial_manager.inWaiting() == 0:
                    break

                data_bytes = self.serial_manager.readline()
                if data_bytes:
                    data_str = data_bytes.decode('UTF-8', errors='replace').strip()
                    if data_str:
                        self.serialSignal.emit(data_str)
                        self._check_blocking_command_complete(data_str, current_time)

        except (OSError, serial.SerialException) as e:
            logger.error(f"Error reading from serial: {e}")
            self.serialSignal.emit("SERIAL-DISCONNECTED")
            self.running = False

    def _check_blocking_command_complete(self, data: str, current_time: float) -> None:
        """Check if blocking command has completed and resume polling."""
        if not self.status_polling_paused:
            return

        if "ok" not in data.lower():
            return

        time_elapsed = current_time - self.blocking_command_start_time
        if time_elapsed >= config.BLOCKING_COMMAND_MIN_PAUSE:
            self.status_polling_paused = False
            logger.info(
                f"Resuming status polling after blocking command completed "
                f"({time_elapsed:.1f}s elapsed)"
            )
            self._request_immediate_status()
        else:
            logger.debug(
                f"Received 'ok' but only {time_elapsed:.1f}s elapsed "
                f"(need {config.BLOCKING_COMMAND_MIN_PAUSE}s), waiting..."
            )

    def _request_immediate_status(self) -> None:
        """Request immediate position and endstop status."""
        self.serial_manager.write(b"M114\n", priority=True)
        self.serial_manager.write(b"M119\n", priority=True)


# Backwards compatibility alias
SerialThreadClass = SerialThread
