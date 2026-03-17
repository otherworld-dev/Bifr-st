"""
Voice Listener Thread

Runs vosk speech recognition on a background QThread.
Captures audio via sounddevice and emits Qt signals for recognized speech.
"""

import json
import logging
import queue
import threading
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

# Lazy imports — these are addon dependencies, not always installed
vosk = None
sd = None


def _ensure_imports():
    """Import vosk and sounddevice on first use."""
    global vosk, sd
    if vosk is None:
        import vosk as _vosk
        vosk = _vosk
        vosk.SetLogLevel(-1)  # Suppress vosk's own logging
    if sd is None:
        import sounddevice as _sd
        sd = _sd


class ListenerThread(QThread):
    """Background thread for continuous speech recognition.

    Captures audio from the microphone and feeds it to a vosk recognizer.
    Emits Qt signals (thread-safe) when speech is recognized.
    """

    partial_result = pyqtSignal(str)
    command_recognized = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    SAMPLE_RATE = 16000
    BLOCK_SIZE = 4000  # ~250ms of audio at 16kHz

    def __init__(self, model_path):
        """
        Args:
            model_path: Path to the vosk model directory.
        """
        super().__init__()
        self._model_path = str(model_path)
        self._stop_event = threading.Event()
        self._audio_queue = queue.Queue()

    def stop(self):
        """Request the thread to stop and wait for it."""
        self._stop_event.set()
        self.wait(3000)

    def run(self):
        """Main recognition loop (runs on background thread)."""
        try:
            _ensure_imports()
        except ImportError as e:
            self.error_occurred.emit(
                f"Missing dependency: {e}. "
                f"Install with: pip install vosk sounddevice"
            )
            return

        # Load vosk model
        try:
            model = vosk.Model(self._model_path)
        except Exception as e:
            self.error_occurred.emit(f"Failed to load vosk model: {e}")
            return

        recognizer = vosk.KaldiRecognizer(model, self.SAMPLE_RATE)

        # Audio callback pushes chunks to the queue
        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"Audio status: {status}")
            self._audio_queue.put(bytes(indata))

        # Open microphone stream
        try:
            stream = sd.RawInputStream(
                samplerate=self.SAMPLE_RATE,
                blocksize=self.BLOCK_SIZE,
                dtype="int16",
                channels=1,
                callback=audio_callback
            )
        except Exception as e:
            self.error_occurred.emit(f"Microphone error: {e}")
            return

        logger.info("Voice listener started")

        with stream:
            while not self._stop_event.is_set():
                try:
                    data = self._audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    # Final result — utterance complete (silence detected)
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        logger.info(f"Voice recognized: '{text}'")
                        self.command_recognized.emit(text)
                else:
                    # Partial result — still speaking
                    partial = json.loads(recognizer.PartialResult())
                    text = partial.get("partial", "").strip()
                    if text:
                        self.partial_result.emit(text)

        # Drain queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        logger.info("Voice listener stopped")


def check_dependencies():
    """Check if vosk and sounddevice are installed.

    Returns:
        tuple: (available: bool, error_message: str or None)
    """
    try:
        _ensure_imports()
        return True, None
    except ImportError as e:
        return False, str(e)


def check_model(model_path):
    """Check if the vosk model exists.

    Args:
        model_path: Path to the model directory.

    Returns:
        bool: True if the model directory exists and looks valid.
    """
    model_dir = Path(model_path)
    # A valid vosk model has at least these files
    return model_dir.is_dir() and (
        (model_dir / "am" / "final.mdl").exists() or
        (model_dir / "graph" / "Gr.fst").exists() or
        # Some models have different structures
        any(model_dir.iterdir())
    )
