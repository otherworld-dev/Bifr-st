"""
Addon Manager

Discovers, loads, and manages the lifecycle of Bifrost addons.
Addons are Python packages in the addons/ directory.
"""

import importlib
import logging
import sys
from pathlib import Path

from addon_base import AddonBase

logger = logging.getLogger(__name__)


class AddonManager:
    """Discovers and manages Bifrost addons.

    Scans the addons/ directory for Python packages that expose an
    ``addon_class`` attribute (a subclass of :class:`AddonBase`).
    """

    def __init__(self, addons_dir, api):
        """
        Args:
            addons_dir: Path to the addons/ directory.
            api: BifrostAPI instance passed to each addon.
        """
        self.addons_dir = Path(addons_dir)
        self.api = api
        self.loaded_addons = {}   # name -> AddonBase instance
        self.addon_panels = []    # [(name, icon, widget), ...]

    def discover_and_load(self):
        """Scan addons/ directory and load all valid addon packages."""
        if not self.addons_dir.is_dir():
            logger.info(f"Addons directory does not exist: {self.addons_dir}")
            return

        # Add addons/ to sys.path so addon packages can be imported
        addons_path = str(self.addons_dir)
        if addons_path not in sys.path:
            sys.path.append(addons_path)

        candidates = sorted(
            p for p in self.addons_dir.iterdir()
            if p.is_dir() and (p / "__init__.py").exists()
        )

        if not candidates:
            logger.info("No addons found")
            return

        for package_dir in candidates:
            self._load_addon(package_dir.name)

        logger.info(
            f"Addon loading complete: {len(self.loaded_addons)} loaded, "
            f"{len(candidates) - len(self.loaded_addons)} skipped"
        )

    def _load_addon(self, package_name):
        """Import and instantiate a single addon package.

        Args:
            package_name: Name of the package directory (e.g. ``"voice_control"``).
        """
        try:
            module = importlib.import_module(package_name)
        except Exception:
            logger.exception(f"Failed to import addon '{package_name}'")
            return

        addon_class = getattr(module, "addon_class", None)
        if addon_class is None:
            logger.warning(
                f"Addon '{package_name}' has no 'addon_class' attribute — skipping"
            )
            return

        if not (isinstance(addon_class, type) and issubclass(addon_class, AddonBase)):
            logger.warning(
                f"Addon '{package_name}': addon_class is not a subclass of AddonBase — skipping"
            )
            return

        # Instantiate
        try:
            instance = addon_class(self.api)
        except Exception:
            logger.exception(f"Failed to instantiate addon '{package_name}'")
            return

        # Create panel
        try:
            panel = instance.create_panel()
        except Exception:
            logger.exception(f"Failed to create panel for addon '{package_name}'")
            return

        if panel is None:
            logger.warning(f"Addon '{package_name}' create_panel() returned None — skipping")
            return

        self.loaded_addons[instance.name] = instance
        self.addon_panels.append((instance.name, instance.icon, panel))
        logger.info(
            f"Loaded addon: {instance.name} v{instance.version} "
            f"({instance.description})"
        )

    def get_panels(self):
        """Return loaded addon panels for mode tab registration.

        Returns:
            list of (name, icon, widget) tuples.
        """
        return list(self.addon_panels)

    def notify_activate(self, addon_name):
        """Notify an addon that its tab has been selected."""
        addon = self.loaded_addons.get(addon_name)
        if addon:
            try:
                addon.on_activate()
            except Exception:
                logger.exception(f"Error in on_activate for addon '{addon_name}'")

    def notify_deactivate(self, addon_name):
        """Notify an addon that the user switched away from its tab."""
        addon = self.loaded_addons.get(addon_name)
        if addon:
            try:
                addon.on_deactivate()
            except Exception:
                logger.exception(f"Error in on_deactivate for addon '{addon_name}'")

    def unload_all(self):
        """Call on_unload for all loaded addons (app shutdown)."""
        for name, addon in self.loaded_addons.items():
            try:
                addon.on_unload()
                logger.info(f"Unloaded addon: {name}")
            except Exception:
                logger.exception(f"Error unloading addon '{name}'")
        self.loaded_addons.clear()
        self.addon_panels.clear()
        self.api._clear_all_listeners()
