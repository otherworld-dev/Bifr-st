"""
Addon Base Class

All Bifrost addons must subclass AddonBase and override the required
metadata attributes and create_panel() method.
"""

import logging

logger = logging.getLogger(__name__)


class AddonBase:
    """Base class for Bifrost addons.

    Subclass this and set the class-level metadata attributes.
    The addon's __init__.py must expose the subclass as ``addon_class``.

    Example::

        # addons/my_addon/__init__.py
        from .addon import MyAddon
        addon_class = MyAddon

        # addons/my_addon/addon.py
        from addon_base import AddonBase
        class MyAddon(AddonBase):
            name = "My Addon"
            version = "1.0.0"
            description = "Does something cool"
            icon = "🔌"

            def create_panel(self):
                from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
                panel = QWidget()
                layout = QVBoxLayout(panel)
                layout.addWidget(QLabel("Hello from My Addon"))
                return panel
    """

    # -- Required metadata (override in subclass) --
    name: str = "Unnamed Addon"
    version: str = "0.0.0"
    description: str = ""
    icon: str = ""  # Emoji shown on the mode tab button

    def __init__(self, api):
        """Initialise addon with a BifrostAPI instance.

        Args:
            api: BifrostAPI providing access to robot state, commands, and events.
        """
        self.api = api

    def create_panel(self):
        """Return a QWidget to display in this addon's mode tab.

        Called once during addon loading. The returned widget is added
        to the mode stack and shown when the user clicks the tab.

        Returns:
            QWidget: The panel widget for this addon.
        """
        raise NotImplementedError(
            f"Addon '{self.name}' must implement create_panel()"
        )

    def on_activate(self):
        """Called when the user switches to this addon's tab."""
        pass

    def on_deactivate(self):
        """Called when the user switches away from this addon's tab."""
        pass

    def on_unload(self):
        """Called on application shutdown. Release resources here."""
        pass
