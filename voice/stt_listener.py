"""
voice/stt_listener.py
─────────────────────
Real-time microphone capture + transcription using faster-whisper & sounddevice.

Dependencies:
    pip install faster-whisper sounddevice numpy
"""

from __future__ import annotations

import queue
import time
from collections import deque
from typing import Optional

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------

_SAMPLE_RATE: int = 16_000          # Hz – required by Whisper
_CHANNELS: int = 1                  # Mono
_DTYPE: str = "float32"             # sounddevice native float
_CHUNK_MS: int = 50                 # Audio chunk size in milliseconds
_CHUNK_SAMPLES: int = int(_SAMPLE_RATE * _CHUNK_MS / 1000)  # 800 samples

_PRE_SPEECH_MS: int = 500           # Rolling pre-speech buffer length (ms)
_PRE_SPEECH_CHUNKS: int = _PRE_SPEECH_MS // _CHUNK_MS       # 10 chunks


class STTListener:
    """Continuously captures microphone audio and transcribes detected speech.

    Parameters
    ----------
    model_size:
        Whisper model variant to load (e.g. ``"base.en"``, ``"small"``,
        ``"medium"``, ``"large-v3"``).
    device:
        Inference device – ``"cpu"`` or ``"cuda"``.
    compute_type:
        Quantisation format – ``"int8"``, ``"float16"``, ``"float32"``, etc.
        ``"int8"`` is fastest on CPU; ``"float16"`` is recommended for CUDA.
    energy_threshold:
        RMS amplitude level above which audio is considered speech.
        Raise this value in noisy environments; lower it in quiet rooms.
    silence_duration:
        Seconds of sub-threshold audio required to mark the end of an
        utterance and trigger transcription.
    input_device:
        ``sounddevice`` device index / name.  ``None`` uses the system
        default input device.
    """

    def __init__(
        self,
        model_size: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        energy_threshold: float = 0.015,
        silence_duration: float = 1.0,
        input_device: Optional[int | str] = None,
    ) -> None:
        self.energy_threshold = energy_threshold
        self.silence_duration = silence_duration
        self.input_device = input_device

        # Thread-safe queue filled by the sounddevice callback
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue()

        # Rolling pre-speech ring-buffer (deque of 1-D float32 arrays)
        self._pre_buffer: deque[np.ndarray] = deque(
            maxlen=_PRE_SPEECH_CHUNKS
        )

        print(
            f"[STTListener] Loading Whisper model '{model_size}' "
            f"on {device} ({compute_type}) …"
        )
        self._model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )
        print("[STTListener] Model ready.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rms(chunk: np.ndarray) -> float:
        """Return the Root Mean Square energy of a 1-D float32 array."""
        return float(np.sqrt(np.mean(chunk ** 2)))

    @staticmethod
    def _draw_meter(rms: float, threshold: float, state: str) -> None:
        """Render a live ASCII VU meter on the current terminal line.

        The bar is scaled so that ``4 * threshold`` = full bar.
        A ``|`` marker is drawn at the exact threshold position so you can
        see at a glance whether the signal is above or below the cut-off.

        Example output (overwritten each chunk)::

            MIC [#######|..............] RMS:0.0183  [SPEAKING ]
        """
        bar_width = 40
        # Clamp fill ratio to [0, 1]; full bar == 4x threshold
        fill = int(min(rms / (threshold * 4), 1.0) * bar_width)
        bar = list("#" * fill + "." * (bar_width - fill))
        # Threshold marker: threshold / (threshold*4) * bar_width == bar_width//4
        t_pos = bar_width // 4
        bar[t_pos] = "|"
        print(
            f"\r  MIC [{''.join(bar)}] RMS:{rms:.4f}  [{state:<8s}]",
            end="",
            flush=True,
        )

    def _sd_callback(
        self,
        indata: np.ndarray,
        frames: int,          # noqa: ARG002
        time_info: object,    # noqa: ARG002
        status: sd.CallbackFlags,
    ) -> None:
        """sounddevice callback – runs on a dedicated audio thread."""
        if status:
            print(f"[STTListener] sounddevice status: {status}", flush=True)
        # Flatten to 1-D and copy (indata is a view; buffer gets recycled)
        self._audio_queue.put_nowait(indata[:, 0].copy())

    def _collect_utterance(self) -> np.ndarray:
        """Block until a complete utterance is detected; return as float32 array.

        State machine:
        WAITING  --( RMS >= threshold )--> SPEAKING
        SPEAKING --( RMS < threshold, silence_duration exceeded )--> return utterance
        """
        speaking = False
        silence_start: Optional[float] = None
        utterance_chunks: list[np.ndarray] = []

        while True:
            chunk = self._audio_queue.get()
            rms = self._rms(chunk)

            # Live ASCII VU meter – overwrites the same terminal line each chunk
            state = "WAITING" if not speaking else "SPEAKING"
            self._draw_meter(rms, self.energy_threshold, state)

            if not speaking:
                # Always maintain the rolling pre-speech buffer
                self._pre_buffer.append(chunk)

                if rms >= self.energy_threshold:
                    # Speech onset – prepend pre-speech buffer to avoid clipping
                    speaking = True
                    silence_start = None
                    utterance_chunks = list(self._pre_buffer)  # include lead-in
            else:
                utterance_chunks.append(chunk)

                if rms < self.energy_threshold:
                    if silence_start is None:
                        silence_start = time.monotonic()
                    elif (time.monotonic() - silence_start) >= self.silence_duration:
                        # Sufficient silence -> utterance complete
                        break
                else:
                    # Voice resumed -> reset silence timer
                    silence_start = None

        print()  # Move past the VU meter line before printing the transcript
        return np.concatenate(utterance_chunks).astype(np.float32)

    def _transcribe(self, audio: np.ndarray) -> str:
        """Transcribe a float32 NumPy array directly (no temp file)."""
        segments, _info = self._model.transcribe(
            audio,
            language=None,      # auto-detect; set e.g. "en" to force English
            beam_size=5,
            vad_filter=True,    # faster-whisper built-in VAD as a second pass
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def listen_and_transcribe(self) -> str:
        """Capture one utterance from the microphone and return its transcript.

        Opens the audio stream, blocks until a complete utterance is detected,
        transcribes it, closes the stream, and returns the text.

        For continuous transcription, call this method in a loop (see the
        ``__main__`` block below).

        Returns
        -------
        str
            Transcribed text of the detected utterance (may be empty if
            Whisper produced no output).
        """
        with sd.InputStream(
            samplerate=_SAMPLE_RATE,
            channels=_CHANNELS,
            dtype=_DTYPE,
            blocksize=_CHUNK_SAMPLES,
            device=self.input_device,
            callback=self._sd_callback,
        ):
            print("[STTListener] Listening …", flush=True)
            # Clear any stale audio from a previous call
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break
            self._pre_buffer.clear()

            audio = self._collect_utterance()

        print(
            f"[STTListener] Utterance captured "
            f"({len(audio) / _SAMPLE_RATE:.2f}s). Transcribing …",
            flush=True,
        )
        return self._transcribe(audio)


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Real-time speech-to-text test using faster-whisper."
    )
    parser.add_argument(
        "--model", default="base.en",
        help="Whisper model size (default: base.en)"
    )
    parser.add_argument(
        "--device", default="cpu",
        help="Inference device: cpu | cuda (default: cpu)"
    )
    parser.add_argument(
        "--compute-type", default="int8",
        help="Quantisation format: int8 | float16 | float32 (default: int8)"
    )
    parser.add_argument(
        "--threshold", type=float, default=0.015,
        help="RMS energy threshold for VAD (default: 0.015)"
    )
    parser.add_argument(
        "--silence", type=float, default=1.0,
        help="Silence duration in seconds to end utterance (default: 1.0)"
    )
    args = parser.parse_args()

    listener = STTListener(
        model_size=args.model,
        device=args.device,
        compute_type=args.compute_type,
        energy_threshold=args.threshold,
        silence_duration=args.silence,
    )

    print("\n--- STT Listener running. Speak into your microphone. Ctrl+C to quit. ---\n")

    try:
        while True:
            text = listener.listen_and_transcribe()
            if text:
                print(f"[Transcript] {text}\n")
            else:
                print("[Transcript] (no speech detected)\n")
    except KeyboardInterrupt:
        print("\n[STTListener] Stopped.")
