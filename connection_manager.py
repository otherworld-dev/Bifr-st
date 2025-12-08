"""
Connection Manager Module
Handles serial port connection lifecycle with Qt signals for GUI updates

This module provides:
- Thread-safe serial connection/disconnection
- Qt signals for connection state changes
- Port enumeration and auto-detection
"""

import logging
import threading
from typing import Optional, Callable

from PyQt5.QtCore import QObject, pyqtSignal

import config
import serial_port_finder as spf
from serial_manager import SerialManager

logger = logging.getLogger(__name__)


class ConnectionState:
    """Connection state constants"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class ConnectionManager(QObject):
    """
    Manages serial port connection lifecycle.

    Emits Qt signals for state changes that the GUI can connect to.
    Connection is performed in a background thread to avoid GUI freeze.

    Signals:
        state_changed(str): Emitted when connection state changes
        connected(str, str): Emitted on successful connection (port, baudrate)
        disconnected(): Emitted when disconnected
        error(str): Emitted on connection error with message
    """

    # Signals for GUI updates (thread-safe)
    state_changed = pyqtSignal(str)  # ConnectionState value
    connected = pyqtSignal(str, str)  # port, baudrate
    disconnected = pyqtSignal()
    error = pyqtSignal(str)  # error message

    def __init__(self, serial_manager: SerialManager, parent=None):
        """
        Initialize connection manager.

        Args:
            serial_manager: SerialManager instance to use for connections
            parent: Optional Qt parent object
        """
        super().__init__(parent)
        self.serial_manager = serial_manager
        self._state = ConnectionState.DISCONNECTED
        self._current_port = None
        self._current_baudrate = None
        self._serial_thread = None
        self._serial_thread_class = None  # Class to instantiate for serial thread

    @property
    def state(self) -> str:
        """Get current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._state == ConnectionState.CONNECTED and self.serial_manager.isOpen()

    @property
    def current_port(self) -> Optional[str]:
        """Get currently connected port name."""
        return self._current_port if self.is_connected else None

    @property
    def current_baudrate(self) -> Optional[str]:
        """Get currently connected baudrate."""
        return self._current_baudrate if self.is_connected else None

    def set_serial_thread_class(self, thread_class) -> None:
        """
        Set the serial thread class to use for connections.

        Args:
            thread_class: Class to instantiate (must have start(), stop(), wait() methods)
        """
        self._serial_thread_class = thread_class

    def get_serial_thread(self):
        """Get the current serial thread instance."""
        return self._serial_thread

    def get_available_ports(self) -> list:
        """
        Get list of available serial ports.

        Returns:
            List of port names
        """
        return spf.serial_ports()

    def get_recommended_port(self) -> Optional[str]:
        """
        Get auto-detected robot port.

        Returns:
            Port name if detected, None otherwise
        """
        return spf.get_robot_port()

    def connect(self, port: str, baudrate: str, gui_instance=None) -> None:
        """
        Initiate connection to serial port (non-blocking).

        Connection is performed in a background thread. Listen to signals
        for connection result.

        Args:
            port: Serial port name (e.g., "COM3")
            baudrate: Baud rate as string (e.g., "115200")
            gui_instance: Optional GUI instance to pass to serial thread
        """
        if not port:
            self.error.emit("No serial port specified")
            return

        if not baudrate:
            self.error.emit("No baud rate specified")
            return

        # If already connected, disconnect first
        if self.is_connected:
            self.disconnect()

        # Update state
        self._set_state(ConnectionState.CONNECTING)

        # Run connection in background thread
        connection_thread = threading.Thread(
            target=self._connect_worker,
            args=(port, baudrate, gui_instance),
            daemon=True
        )
        connection_thread.start()

    def disconnect(self) -> None:
        """Disconnect from serial port."""
        try:
            # Stop serial thread
            if self._serial_thread and hasattr(self._serial_thread, 'isRunning'):
                if self._serial_thread.isRunning():
                    self._serial_thread.stop()
                    self._serial_thread.wait(config.SERIAL_THREAD_SHUTDOWN_TIMEOUT)

            # Close serial port
            self.serial_manager.close()

            # Clear state
            self._serial_thread = None
            self._current_port = None
            self._current_baudrate = None

            # Update state and emit signal
            self._set_state(ConnectionState.DISCONNECTED)
            self.disconnected.emit()

            logger.info("Disconnected from serial port")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            self._set_state(ConnectionState.ERROR)
            self.error.emit(str(e))

    def _connect_worker(self, port: str, baudrate: str, gui_instance=None) -> None:
        """
        Worker thread for serial connection.

        Args:
            port: Serial port name
            baudrate: Baud rate as string
            gui_instance: Optional GUI instance for serial thread
        """
        try:
            # Stop existing thread if running
            if self._serial_thread and hasattr(self._serial_thread, 'isRunning'):
                if self._serial_thread.isRunning():
                    self._serial_thread.stop()
                    self._serial_thread.wait(2000)

            # Close existing connection
            self.serial_manager.close()

            # Configure serial port
            self.serial_manager.port = port
            self.serial_manager.baudrate = int(baudrate)
            self.serial_manager.timeout = config.SERIAL_TIMEOUT

            # Open connection (this can block on Windows)
            self.serial_manager.open()

            # Clear stale data
            self.serial_manager.reset_input_buffer()
            logger.debug("Cleared serial input buffer")

            # Create serial thread if class is set
            if self._serial_thread_class:
                self._serial_thread = self._serial_thread_class(gui_instance=gui_instance)
                self._serial_thread.start()

            # Store connection info
            self._current_port = port
            self._current_baudrate = baudrate

            # Emit success (thread-safe via Qt signal)
            self._set_state(ConnectionState.CONNECTED)
            self.connected.emit(port, baudrate)

            logger.info(f"Connected to {port} at {baudrate} baud")

        except Exception as e:
            logger.exception("Serial connection error")
            self._set_state(ConnectionState.ERROR)
            self.error.emit(str(e))

    def _set_state(self, state: str) -> None:
        """Update state and emit signal."""
        self._state = state
        self.state_changed.emit(state)

    def request_position_update(self) -> None:
        """Request position and endstop status from firmware."""
        if self.serial_manager.isOpen():
            self.serial_manager.write(b"M114\n", priority=True)
            self.serial_manager.write(b"M119\n", priority=True)
            logger.debug("Requested position (M114) and endstop status (M119)")
