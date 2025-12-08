"""
Position History Manager Module
Handles position history export and management

This module provides:
- Position history export to CSV
- History clearing with confirmation
- Default filename generation
- Export result handling
"""

import logging
from datetime import datetime
from typing import Callable, Optional
from dataclasses import dataclass
from enum import Enum, auto

logger = logging.getLogger(__name__)


class ExportResult(Enum):
    """Result of export operation"""
    SUCCESS = auto()
    NO_DATA = auto()
    CANCELLED = auto()
    FAILED = auto()


@dataclass
class ExportInfo:
    """Information about an export operation"""
    result: ExportResult
    filename: str = ""
    snapshot_count: int = 0
    error_message: str = ""


class PositionHistoryManager:
    """
    Manages position history export and clearing operations.

    This class separates business logic from GUI concerns,
    using callbacks for file dialogs and messages.
    """

    # Default CSV filename format
    FILENAME_FORMAT = "position_history_{timestamp}.csv"
    TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

    def __init__(
        self,
        position_history=None,
        # Callbacks for GUI interactions
        get_save_filename: Optional[Callable[[str], Optional[str]]] = None,
        show_warning: Optional[Callable[[str, str], None]] = None,
        show_info: Optional[Callable[[str, str], None]] = None,
        show_error: Optional[Callable[[str, str], None]] = None,
        confirm_action: Optional[Callable[[str, str], bool]] = None,
    ):
        """
        Initialize position history manager.

        Args:
            position_history: Position history object to manage
            get_save_filename: Callback(default_name) -> filename or None
            show_warning: Callback(message, title) for warning dialogs
            show_info: Callback(message, title) for info dialogs
            show_error: Callback(message, title) for error dialogs
            confirm_action: Callback(message, title) -> bool for confirmation
        """
        self.position_history = position_history
        self.get_save_filename = get_save_filename
        self.show_warning = show_warning
        self.show_info = show_info
        self.show_error = show_error
        self.confirm_action = confirm_action

    @property
    def history_count(self) -> int:
        """Get number of snapshots in history"""
        if self.position_history is None:
            return 0
        return len(self.position_history)

    @property
    def has_data(self) -> bool:
        """Check if there is any history data"""
        return self.history_count > 0

    def generate_default_filename(self) -> str:
        """
        Generate default filename for export.

        Returns:
            Filename with timestamp, e.g., 'position_history_20240115_143022.csv'
        """
        timestamp = datetime.now().strftime(self.TIMESTAMP_FORMAT)
        return self.FILENAME_FORMAT.format(timestamp=timestamp)

    def export_to_csv(self, filename: Optional[str] = None) -> ExportInfo:
        """
        Export position history to CSV file.

        Args:
            filename: Target filename, or None to prompt for filename

        Returns:
            ExportInfo with result details
        """
        # Check if there's data to export
        if not self.has_data:
            logger.warning("No position history to export")
            if self.show_warning:
                self.show_warning("No position history to export.", "No Data")
            return ExportInfo(result=ExportResult.NO_DATA)

        # Get filename if not provided
        if filename is None:
            if self.get_save_filename:
                default_name = self.generate_default_filename()
                filename = self.get_save_filename(default_name)

        # Check if user cancelled
        if not filename:
            logger.debug("Export cancelled by user")
            return ExportInfo(result=ExportResult.CANCELLED)

        # Perform export
        try:
            success = self.position_history.export_to_csv(filename)

            if success:
                count = self.history_count
                logger.info(f"Position history exported to {filename} ({count} snapshots)")

                if self.show_info:
                    self.show_info(
                        f"Position history exported successfully to:\n{filename}\n\n{count} snapshots saved.",
                        "Export Successful"
                    )

                return ExportInfo(
                    result=ExportResult.SUCCESS,
                    filename=filename,
                    snapshot_count=count
                )
            else:
                logger.error(f"Failed to export position history to {filename}")
                if self.show_error:
                    self.show_error("Failed to export position history.", "Export Failed")

                return ExportInfo(
                    result=ExportResult.FAILED,
                    filename=filename,
                    error_message="Export returned False"
                )

        except Exception as e:
            logger.error(f"Exception during export: {e}")
            if self.show_error:
                self.show_error(f"Failed to export: {e}", "Export Failed")

            return ExportInfo(
                result=ExportResult.FAILED,
                filename=filename or "",
                error_message=str(e)
            )

    def clear_history(self, skip_confirmation: bool = False) -> bool:
        """
        Clear all position history.

        Args:
            skip_confirmation: If True, skip confirmation dialog

        Returns:
            True if history was cleared, False if cancelled
        """
        if not self.has_data:
            logger.debug("No history to clear")
            return False

        # Confirm with user unless skipped
        if not skip_confirmation and self.confirm_action:
            message = f"Clear all position history?\n\nThis will delete {self.history_count} recorded snapshots."
            if not self.confirm_action(message, "Clear History"):
                logger.debug("Clear history cancelled by user")
                return False

        # Clear history
        self.position_history.clear()
        logger.info("Position history cleared by user")

        if self.show_info:
            self.show_info("Position history cleared.", "Cleared")

        return True

    def get_export_info(self) -> dict:
        """
        Get information about current history for display.

        Returns:
            Dictionary with history information
        """
        return {
            'count': self.history_count,
            'has_data': self.has_data,
            'default_filename': self.generate_default_filename()
        }


def create_position_history_manager(
    position_history=None,
    get_save_filename: Callable = None,
    show_warning: Callable = None,
    show_info: Callable = None,
    show_error: Callable = None,
    confirm_action: Callable = None
) -> PositionHistoryManager:
    """
    Create a PositionHistoryManager with callbacks.

    Args:
        position_history: Position history object
        get_save_filename: Callback(default_name) -> filename
        show_warning: Callback(message, title) for warnings
        show_info: Callback(message, title) for info
        show_error: Callback(message, title) for errors
        confirm_action: Callback(message, title) -> bool

    Returns:
        Configured PositionHistoryManager instance
    """
    return PositionHistoryManager(
        position_history=position_history,
        get_save_filename=get_save_filename,
        show_warning=show_warning,
        show_info=show_info,
        show_error=show_error,
        confirm_action=confirm_action
    )
