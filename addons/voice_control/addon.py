"""
Voice Control Addon

Play recorded sequences by voice command. Say a command name and the robot
plays back the matching sequence file from the sequences directory.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QListWidget, QListWidgetItem, QRadioButton,
    QSpinBox, QDoubleSpinBox, QButtonGroup, QCheckBox, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer

from addon_base import AddonBase
from .listener import ListenerThread, check_dependencies, check_model
from .playback import SequencePlayback
from .matcher import CommandMatcher

logger = logging.getLogger(__name__)


class VoiceControlAddon(AddonBase):
    name = "Voice Control"
    version = "1.0.0"
    description = "Play sequences by voice command"
    icon = "\U0001f3a4"  # microphone emoji

    def __init__(self, api):
        super().__init__(api)
        self._listener = None
        self._playback = None
        self._matcher = None
        self._is_listening = False

        # Wake word state
        self._wake_word_active = False
        self._wake_word_time = 0.0
        self._wake_word_timeout = 5.0  # seconds to wait for command after wake word

    def create_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # --- Check dependencies ---
        deps_ok, deps_error = check_dependencies()
        if not deps_ok:
            error_label = QLabel(
                f"Voice Control requires additional packages.\n\n"
                f"Install with:\n  pip install vosk sounddevice\n\n"
                f"Error: {deps_error}"
            )
            error_label.setWordWrap(True)
            error_label.setStyleSheet("color: red; padding: 20px;")
            layout.addWidget(error_label)
            layout.addStretch()
            return panel

        # --- Check vosk model ---
        model_path = self._get_model_path()
        if not check_model(model_path):
            error_label = QLabel(
                f"Vosk speech model not found.\n\n"
                f"Expected at:\n  {model_path}\n\n"
                f"Download vosk-model-small-en-us-0.15 from:\n"
                f"  https://alphacephei.com/vosk/models\n\n"
                f"Extract into the path above."
            )
            error_label.setWordWrap(True)
            error_label.setStyleSheet("color: red; padding: 20px;")
            layout.addWidget(error_label)
            layout.addStretch()
            return panel

        # --- Sequences directory ---
        self._sequences_dir = self._get_sequences_dir()
        self._sequences_dir.mkdir(parents=True, exist_ok=True)

        # --- Initialize components ---
        self._matcher = CommandMatcher(self._sequences_dir)
        self._playback = SequencePlayback(self.api)

        # Connect playback signals
        self._playback.playback_started.connect(self._on_playback_started)
        self._playback.playback_finished.connect(self._on_playback_finished)
        self._playback.point_reached.connect(self._on_point_reached)

        # === CONTROLS GROUP ===
        controls_group = QGroupBox("Controls")
        controls_layout = QVBoxLayout(controls_group)

        # Buttons row
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Start Listening")
        self._start_btn.setMinimumHeight(35)
        self._start_btn.clicked.connect(self._start_listening)
        btn_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop Listening")
        self._stop_btn.setMinimumHeight(35)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_listening)
        btn_row.addWidget(self._stop_btn)
        controls_layout.addLayout(btn_row)

        # Status
        self._status_label = QLabel("Status: Idle")
        self._status_label.setStyleSheet("font-weight: bold; padding: 5px;")
        controls_layout.addWidget(self._status_label)

        # Transcript
        self._transcript_label = QLabel("")
        self._transcript_label.setWordWrap(True)
        self._transcript_label.setStyleSheet(
            "background-color: #f5f5f5; padding: 8px; border: 1px solid #ddd; "
            "border-radius: 3px; min-height: 30px; font-family: monospace;"
        )
        controls_layout.addWidget(self._transcript_label)

        # Last match
        self._match_label = QLabel("")
        self._match_label.setStyleSheet("color: #666; padding: 2px;")
        controls_layout.addWidget(self._match_label)

        layout.addWidget(controls_group)

        # === AVAILABLE COMMANDS GROUP ===
        commands_group = QGroupBox("Available Commands")
        commands_layout = QVBoxLayout(commands_group)

        self._commands_list = QListWidget()
        self._commands_list.setMaximumHeight(150)
        commands_layout.addWidget(self._commands_list)

        cmd_btn_row = QHBoxLayout()
        open_folder_btn = QPushButton("Open Sequences Folder")
        open_folder_btn.clicked.connect(self._open_sequences_folder)
        cmd_btn_row.addWidget(open_folder_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_commands)
        cmd_btn_row.addWidget(refresh_btn)
        commands_layout.addLayout(cmd_btn_row)

        layout.addWidget(commands_group)

        # === SETTINGS GROUP ===
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_group)

        # Wake word
        wake_row = QHBoxLayout()
        self._wake_word_checkbox = QCheckBox("Wake word:")
        self._wake_word_checkbox.setChecked(True)
        self._wake_word_checkbox.toggled.connect(self._on_wake_word_toggled)
        wake_row.addWidget(self._wake_word_checkbox)

        self._wake_word_input = QLineEdit("hi thor")
        self._wake_word_input.setPlaceholderText("e.g. hi thor")
        self._wake_word_input.setMaximumWidth(200)
        wake_row.addWidget(self._wake_word_input)
        wake_row.addStretch()
        settings_layout.addLayout(wake_row)

        # Movement type
        move_row = QHBoxLayout()
        move_row.addWidget(QLabel("Movement type:"))
        self._g1_radio = QRadioButton("G1 Linear")
        self._g0_radio = QRadioButton("G0 Rapid")
        self._g1_radio.setChecked(True)
        move_group = QButtonGroup(panel)
        move_group.addButton(self._g1_radio)
        move_group.addButton(self._g0_radio)
        move_row.addWidget(self._g1_radio)
        move_row.addWidget(self._g0_radio)
        move_row.addStretch()
        settings_layout.addLayout(move_row)

        # Feedrate
        feed_row = QHBoxLayout()
        feed_row.addWidget(QLabel("Feedrate:"))
        self._feedrate_spin = QSpinBox()
        self._feedrate_spin.setRange(100, 10000)
        self._feedrate_spin.setValue(1000)
        self._feedrate_spin.setSuffix(" mm/min")
        feed_row.addWidget(self._feedrate_spin)
        feed_row.addStretch()
        settings_layout.addLayout(feed_row)

        # Speed
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Playback speed:"))
        self._speed_spin = QDoubleSpinBox()
        self._speed_spin.setRange(0.1, 5.0)
        self._speed_spin.setValue(1.0)
        self._speed_spin.setSingleStep(0.1)
        self._speed_spin.setSuffix("x")
        speed_row.addWidget(self._speed_spin)
        speed_row.addStretch()
        settings_layout.addLayout(speed_row)

        layout.addWidget(settings_group)

        layout.addStretch()

        # Populate commands list
        self._refresh_commands()

        return panel

    # -----------------------------------------------------------------
    # Listening control
    # -----------------------------------------------------------------

    def _start_listening(self):
        if self._is_listening:
            return

        model_path = self._get_model_path()
        self._listener = ListenerThread(model_path)
        self._listener.partial_result.connect(self._on_partial_result)
        self._listener.command_recognized.connect(self._on_command_recognized)
        self._listener.error_occurred.connect(self._on_listener_error)

        self._listener.start()
        self._is_listening = True

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._set_status("Listening...", "green")
        self._transcript_label.setText("")

    def _stop_listening(self):
        if not self._is_listening:
            return

        if self._playback and self._playback.is_playing:
            self._playback.stop()

        if self._listener:
            self._listener.stop()
            self._listener = None

        self._is_listening = False
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._set_status("Idle", "black")

    # -----------------------------------------------------------------
    # Signal handlers
    # -----------------------------------------------------------------

    def _on_partial_result(self, text):
        self._transcript_label.setText(text)
        self._transcript_label.setStyleSheet(
            "background-color: #f5f5f5; padding: 8px; border: 1px solid #ddd; "
            "border-radius: 3px; min-height: 30px; font-family: monospace; "
            "color: #999;"
        )

    def _on_command_recognized(self, text):
        self._transcript_label.setText(text)
        self._transcript_label.setStyleSheet(
            "background-color: #f5f5f5; padding: 8px; border: 1px solid #ddd; "
            "border-radius: 3px; min-height: 30px; font-family: monospace; "
            "color: black;"
        )

        # "stop" always bypasses wake word during playback
        if self._playback and self._playback.is_playing and text.strip().lower() == "stop":
            self._playback.stop()
            self._match_label.setText("Stopped by voice command")
            self._match_label.setStyleSheet("color: orange; padding: 2px;")
            self._wake_word_active = False
            return

        # Wake word gating
        command_text = self._extract_command(text)
        if command_text is None:
            return  # Wake word not detected, ignore

        result = self._matcher.match(command_text)

        if result is None:
            self._match_label.setText(f"No match: \"{text}\"")
            self._match_label.setStyleSheet("color: #999; padding: 2px;")
            return

        command_name, filepath = result

        # Handle "stop" command
        if self._matcher.is_special_command(command_name):
            if command_name == "stop" and self._playback.is_playing:
                self._playback.stop()
                self._match_label.setText("Stopped by voice command")
                self._match_label.setStyleSheet("color: orange; padding: 2px;")
            return

        # Ignore new commands while playing
        if self._playback.is_playing:
            self._match_label.setText(f"Busy — ignored: \"{text}\"")
            self._match_label.setStyleSheet("color: #999; padding: 2px;")
            return

        # Check connection or simulation mode
        if not self.api.can_move():
            self._match_label.setText(f"Not connected — ignored: \"{command_name}\"")
            self._match_label.setStyleSheet("color: red; padding: 2px;")
            return

        # Apply current settings to playback
        self._playback.movement_type = "G1" if self._g1_radio.isChecked() else "G0"
        self._playback.feedrate = self._feedrate_spin.value()
        self._playback.speed = self._speed_spin.value()

        # Play the sequence
        self._match_label.setText(f"\"{text}\" -> {filepath.name}")
        self._match_label.setStyleSheet("color: green; padding: 2px;")

        if not self._playback.play(filepath):
            self._match_label.setText(f"Failed to play: {filepath.name}")
            self._match_label.setStyleSheet("color: red; padding: 2px;")

    def _on_listener_error(self, error_msg):
        logger.error(f"Voice listener error: {error_msg}")
        self._set_status(f"Error: {error_msg}", "red")
        self._is_listening = False
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._listener = None

    def _on_playback_started(self, name):
        self._set_status(f"Playing: {name}", "blue")

    def _on_playback_finished(self):
        if self._is_listening:
            self._set_status("Listening...", "green")
        else:
            self._set_status("Idle", "black")

    def _on_point_reached(self, current, total):
        if self._is_listening:
            self._set_status(f"Playing ({current}/{total})...", "blue")

    # -----------------------------------------------------------------
    # UI helpers
    # -----------------------------------------------------------------

    def _extract_command(self, text):
        """Extract the command portion from recognized text, applying wake word logic.

        Returns:
            str: The command text to match, or None if the utterance should be ignored.
        """
        # Wake word disabled — pass everything through
        if not self._wake_word_checkbox.isChecked():
            return text

        wake_word = self._wake_word_input.text().strip().lower()
        if not wake_word:
            return text  # Empty wake word = disabled

        text_lower = text.lower().strip()

        # Check if wake word was previously activated and hasn't timed out
        if self._wake_word_active:
            elapsed = time.time() - self._wake_word_time
            if elapsed <= self._wake_word_timeout:
                self._wake_word_active = False
                self._set_status("Listening...", "green")
                # "stop" should always work even as a follow-up
                return text
            else:
                # Timed out
                self._wake_word_active = False
                self._set_status("Listening...", "green")

        # Check if text starts with wake word
        if text_lower.startswith(wake_word):
            remainder = text[len(wake_word):].strip()
            if remainder:
                # "hi thor pick up" — wake word + command in one utterance
                return remainder
            else:
                # Just the wake word — activate and wait for next utterance
                self._wake_word_active = True
                self._wake_word_time = time.time()
                self._match_label.setText(f"Wake word detected — listening for command...")
                self._match_label.setStyleSheet("color: blue; padding: 2px;")
                self._set_status("Awaiting command...", "blue")
                return None

        # No wake word detected
        return None

    def _on_wake_word_toggled(self, enabled):
        self._wake_word_active = False
        self._wake_word_input.setEnabled(enabled)

    def _set_status(self, text, color="black"):
        self._status_label.setText(f"Status: {text}")
        self._status_label.setStyleSheet(
            f"font-weight: bold; padding: 5px; color: {color};"
        )

    def _refresh_commands(self):
        if self._matcher:
            self._matcher.refresh()
        self._commands_list.clear()
        if self._matcher:
            for name, filename in self._matcher.get_available_commands():
                self._commands_list.addItem(f"{name}  —  {filename}")
        if self._commands_list.count() == 0:
            self._commands_list.addItem("(no sequences found)")

    def _open_sequences_folder(self):
        path = str(self._sequences_dir)
        self._sequences_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    # -----------------------------------------------------------------
    # Paths
    # -----------------------------------------------------------------

    def _get_model_path(self):
        """Path to the bundled vosk model."""
        return Path(__file__).parent / "model"

    def _get_sequences_dir(self):
        """Path to the sequences directory in addon data."""
        data_dir = self.api.get_addon_data_dir(self.name)
        return data_dir / "sequences"

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    def on_activate(self):
        # Refresh commands in case files were added
        self._refresh_commands()

    def on_unload(self):
        self._stop_listening()
