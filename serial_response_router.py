"""
Serial Response Router Module
Routes incoming serial data to appropriate handlers

This module provides:
- Response type identification
- Routing to position, endstop, and console handlers
- Homing completion detection
- Console output filtering logic
"""

import logging
import time
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum, auto

import parsing_patterns

logger = logging.getLogger(__name__)


class ResponseType(Enum):
    """Types of serial responses"""
    POSITION = auto()      # M114 response
    ENDSTOP = auto()       # M119 response
    OK = auto()            # Command acknowledgment
    DISCONNECT = auto()    # Serial disconnection
    OTHER = auto()         # Other/unknown response


@dataclass
class RoutingResult:
    """Result of routing a serial response"""
    response_type: ResponseType
    handled: bool
    show_in_console: bool
    data: Optional[Dict[str, Any]] = None


class SerialResponseRouter:
    """
    Routes incoming serial data to appropriate handlers.

    This class separates the routing logic from GUI concerns,
    using callbacks for all actions.
    """

    # Special disconnect marker from serial thread
    DISCONNECT_MARKER = "SERIAL-DISCONNECTED"

    def __init__(
        self,
        # Handlers for different response types
        position_handler: Optional[Callable[[str], None]] = None,
        endstop_handler: Optional[Callable[[str], None]] = None,
        disconnect_handler: Optional[Callable[[], None]] = None,
        # Homing state management
        get_is_homing: Optional[Callable[[], bool]] = None,
        set_homing_complete: Optional[Callable[[], None]] = None,
        # Post-homing actions
        request_position_update: Optional[Callable[[], None]] = None,
        set_sync_pending: Optional[Callable[[], None]] = None,
        trigger_sync: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize serial response router.

        Args:
            position_handler: Callback(data) to handle M114 position responses
            endstop_handler: Callback(data) to handle M119 endstop responses
            disconnect_handler: Callback() to handle serial disconnection
            get_is_homing: Callback() -> bool to check if homing in progress
            set_homing_complete: Callback() when homing completes (OK received)
            request_position_update: Callback() to request M114 after homing
            set_sync_pending: Callback() to flag sync pending
            trigger_sync: Callback() to trigger command sync to actual positions
        """
        self.position_handler = position_handler
        self.endstop_handler = endstop_handler
        self.disconnect_handler = disconnect_handler
        self.get_is_homing = get_is_homing
        self.set_homing_complete = set_homing_complete
        self.request_position_update = request_position_update
        self.set_sync_pending = set_sync_pending
        self.trigger_sync = trigger_sync

        # Manual command tracking for console output
        self._last_manual_command_time = 0.0
        self._manual_command_display_duration = 2.0  # seconds

    def identify_response_type(self, data: str) -> ResponseType:
        """
        Identify the type of serial response.

        Args:
            data: Raw serial response string

        Returns:
            ResponseType enum value
        """
        if data == self.DISCONNECT_MARKER:
            return ResponseType.DISCONNECT

        if parsing_patterns.is_m114_response(data):
            return ResponseType.POSITION

        if parsing_patterns.is_m119_response(data):
            return ResponseType.ENDSTOP

        if parsing_patterns.is_ok_response(data):
            return ResponseType.OK

        return ResponseType.OTHER

    def route_response(
        self,
        data: str,
        verbose_show: bool = False,
        ok_show: bool = False,
        sync_pending: bool = False
    ) -> RoutingResult:
        """
        Route serial response to appropriate handler.

        Args:
            data: Raw serial response string
            verbose_show: Whether to show verbose (M114) responses in console
            ok_show: Whether to show OK responses in console
            sync_pending: Whether command sync is pending (after homing)

        Returns:
            RoutingResult with handling details
        """
        response_type = self.identify_response_type(data)

        # Handle disconnection
        if response_type == ResponseType.DISCONNECT:
            return self._handle_disconnect()

        # Check for homing completion
        if response_type == ResponseType.OK:
            self._check_homing_completion()

        # Check if within manual command display window
        time_since_manual = time.time() - self._last_manual_command_time
        if time_since_manual < self._manual_command_display_duration:
            return RoutingResult(
                response_type=response_type,
                handled=False,
                show_in_console=True
            )

        # Route by response type
        if response_type == ResponseType.ENDSTOP:
            return self._handle_endstop(data)

        if response_type == ResponseType.POSITION:
            return self._handle_position(data, verbose_show, sync_pending)

        if response_type == ResponseType.OK:
            return RoutingResult(
                response_type=response_type,
                handled=True,
                show_in_console=ok_show
            )

        # Other responses - show in console
        return RoutingResult(
            response_type=ResponseType.OTHER,
            handled=False,
            show_in_console=True
        )

    def mark_manual_command_sent(self) -> None:
        """Mark that a manual command was just sent (for console display timing)."""
        self._last_manual_command_time = time.time()

    def _handle_disconnect(self) -> RoutingResult:
        """Handle serial disconnection."""
        if self.disconnect_handler:
            self.disconnect_handler()

        logger.warning("Serial Connection Lost")
        return RoutingResult(
            response_type=ResponseType.DISCONNECT,
            handled=True,
            show_in_console=False
        )

    def _handle_endstop(self, data: str) -> RoutingResult:
        """Handle M119 endstop response."""
        if self.endstop_handler:
            self.endstop_handler(data)

        return RoutingResult(
            response_type=ResponseType.ENDSTOP,
            handled=True,
            show_in_console=False
        )

    def _handle_position(
        self,
        data: str,
        verbose_show: bool,
        sync_pending: bool
    ) -> RoutingResult:
        """Handle M114 position response."""
        if self.position_handler:
            self.position_handler(data)

        # Trigger sync if pending (after homing)
        if sync_pending and self.trigger_sync:
            self.trigger_sync()

        return RoutingResult(
            response_type=ResponseType.POSITION,
            handled=True,
            show_in_console=verbose_show,
            data={'sync_triggered': sync_pending}
        )

    def _check_homing_completion(self) -> None:
        """Check if homing just completed (OK received while homing)."""
        is_homing = self.get_is_homing() if self.get_is_homing else False

        if is_homing:
            logger.info("Homing cycle completed")

            # Mark homing as complete
            if self.set_homing_complete:
                self.set_homing_complete()

            # Request position update
            if self.request_position_update:
                self.request_position_update()

            # Flag sync pending
            if self.set_sync_pending:
                self.set_sync_pending()


def create_serial_response_router(
    position_handler: Callable = None,
    endstop_handler: Callable = None,
    disconnect_handler: Callable = None,
    get_is_homing: Callable = None,
    set_homing_complete: Callable = None,
    request_position_update: Callable = None,
    set_sync_pending: Callable = None,
    trigger_sync: Callable = None
) -> SerialResponseRouter:
    """
    Create a SerialResponseRouter with handlers.

    Args:
        position_handler: Callback(data) for M114 responses
        endstop_handler: Callback(data) for M119 responses
        disconnect_handler: Callback() for disconnection
        get_is_homing: Callback() -> bool for homing state
        set_homing_complete: Callback() when homing completes
        request_position_update: Callback() to request position
        set_sync_pending: Callback() to flag sync pending
        trigger_sync: Callback() to trigger command sync

    Returns:
        Configured SerialResponseRouter instance
    """
    return SerialResponseRouter(
        position_handler=position_handler,
        endstop_handler=endstop_handler,
        disconnect_handler=disconnect_handler,
        get_is_homing=get_is_homing,
        set_homing_complete=set_homing_complete,
        request_position_update=request_position_update,
        set_sync_pending=set_sync_pending,
        trigger_sync=trigger_sync
    )
