"""
Command Matcher

Maps spoken transcripts to sequence files by scanning a sequences directory.
Filename (minus .json) = voice command name.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class CommandMatcher:
    """Maps voice transcripts to sequence files.

    Scans a directory of .json sequence files and matches spoken text
    to filenames using exact and substring matching.
    """

    # Always recognized regardless of sequence files
    SPECIAL_COMMANDS = {"stop"}

    def __init__(self, sequences_dir):
        """
        Args:
            sequences_dir: Path to directory containing sequence .json files.
        """
        self._sequences_dir = Path(sequences_dir)
        self._commands = {}  # normalized_name -> filepath
        self.refresh()

    def refresh(self):
        """Rescan the sequences directory for .json files."""
        self._commands.clear()

        if not self._sequences_dir.is_dir():
            logger.info(f"Sequences directory does not exist: {self._sequences_dir}")
            return

        for f in sorted(self._sequences_dir.glob("*.json")):
            name = f.stem.lower().strip()
            if name:
                self._commands[name] = f
                logger.debug(f"Registered voice command: '{name}' -> {f.name}")

        logger.info(f"Loaded {len(self._commands)} voice command(s)")

    def match(self, transcript):
        """Match a transcript to a sequence file.

        Matching priority:
        1. Exact match (case-insensitive)
        2. Transcript contains a command name
        3. Command name contains the transcript

        Args:
            transcript: Recognized speech text.

        Returns:
            tuple: (command_name, filepath) or None if no match.
        """
        text = transcript.lower().strip()
        if not text:
            return None

        # Special commands
        if text in self.SPECIAL_COMMANDS:
            return (text, None)

        # Exact match
        if text in self._commands:
            return (text, self._commands[text])

        # Transcript contains a command name (e.g., "run pick up please")
        for name, path in self._commands.items():
            if name in text:
                return (name, path)

        # Command name contains the transcript (e.g., said "pick" matches "pick up")
        for name, path in self._commands.items():
            if text in name:
                return (name, path)

        return None

    def get_available_commands(self):
        """Return list of (command_name, filename) tuples, sorted."""
        return [(name, path.name) for name, path in sorted(self._commands.items())]

    def is_special_command(self, command_name):
        """Check if a command name is a special built-in command."""
        return command_name in self.SPECIAL_COMMANDS
