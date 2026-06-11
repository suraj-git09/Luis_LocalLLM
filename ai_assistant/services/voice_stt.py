import os
import sys
import queue
import json
import asyncio
import numpy as np
import sounddevice as sd
from vosk import Model, KaldiRecognizer


class OfflineSTTService:
    """
    Offline Speech-to-Text service with accent support and sound level visualizer.

    1. Vosk — Used only for wake-word ("assistant") detection (low CPU, streaming).
    2. Faster-Whisper — Used for transcribing commands. Excellent at handling accents,
       such as Indian English, fully offline.
    """

    # Spinner frames for wake-word loop
    SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(
        self,
        vosk_model_path=None,
        whisper_model_size="tiny",
        sample_rate=16000,
    ):
        if vosk_model_path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            default_path = os.path.join(project_root, "data", "vosk-model-small-en-us-0.15")
            vosk_model_path = os.getenv("VOSK_MODEL_DIR", default_path)

        # --- Vosk setup (wake word only) ---
        if not os.path.exists(vosk_model_path):
            raise FileNotFoundError(
                f"Vosk model not found at '{vosk_model_path}'.\n"
                "Download a model from https://alphacephei.com/vosk/models\n"
                "  e.g. vosk-model-small-en-us-0.15 (~40 MB)\n"
                "and extract it to that path."
            )
        self._print_status("🔄", "Loading speech models...")
        self.vosk_model = Model(vosk_model_path)
        self.sample_rate = sample_rate

        # --- Faster-Whisper setup (conversational input) ---
        self._whisper_model = None
        self._whisper_model_size = whisper_model_size

        # Queue for capturing audio stream
        self._audio_queue: queue.Queue = queue.Queue()
        self._spinner_idx = 0

    # ------------------------------------------------------------------ #
    #  Visual and Helper functions
    # ------------------------------------------------------------------ #
    @staticmethod
    def _print_status(emoji, message):
        print(f"  {emoji}  {message}", flush=True)

    def _print_inline(self, text):
        """Overwrite the current line on the console, padding with spaces to clear old text, then resetting cursor to start."""
        sys.stdout.write(f"\r  {text:<95}\r")
        sys.stdout.flush()

    def _next_spinner(self):
        frame = self.SPINNER[self._spinner_idx % len(self.SPINNER)]
        self._spinner_idx += 1
        return frame

    def _get_whisper_model(self):
        if self._whisper_model is None:
            from faster_whisper import WhisperModel
            self._print_status("🔄", f"Loading Whisper model '{self._whisper_model_size}' (first use)...")
            # Run on CPU with int8 quantization for speed
            self._whisper_model = WhisperModel(
                self._whisper_model_size,
                device="cpu",
                compute_type="int8",
            )
            self._print_status("✅", "Speech models loaded.")
        return self._whisper_model

    def _audio_callback(self, indata, frames, time_info, status):
        """Pushes raw float32/int16 data blocks into the queue."""
        self._audio_queue.put(indata.copy())

    def _drain_queue(self):
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

    # ------------------------------------------------------------------ #
    #  Wake-word detection (Vosk)
    # ------------------------------------------------------------------ #
    async def listen_for_wake_word(self, wake_word: str = "assistant") -> bool:
        """
        Listens continuously in a lightweight loop for the wake word.
        Shows an animated spinner on screen.
        """
        # Vosk expects 16-bit PCM (int16)
        recognizer = KaldiRecognizer(self.vosk_model, self.sample_rate)
        self._drain_queue()

        def int16_callback(indata, frames, time, status):
            self._audio_queue.put(bytes(indata))

        stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=4000,
            dtype="int16",
            channels=1,
            callback=int16_callback,
        )

        wake_lower = wake_word.lower()

        with stream:
            while True:
                frame = self._next_spinner()
                self._print_inline(f"{frame}  🎧 Waiting for wake word \"{wake_word}\"... (say \"{wake_word}\" to activate)")
                await asyncio.sleep(0.15)

                while not self._audio_queue.empty():
                    data = self._audio_queue.get()
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        if wake_lower in result.get("text", ""):
                            self._print_inline("")
                            print("\r  🔔  System Awakened!                                ", flush=True)
                            self._drain_queue()
                            return True
                    else:
                        partial = json.loads(recognizer.PartialResult())
                        if wake_lower in partial.get("partial", ""):
                            self._print_inline("")
                            print("\r  🔔  System Awakened!                                ", flush=True)
                            self._drain_queue()
                            return True

    # ------------------------------------------------------------------ #
    #  Accent-Tolerant Record + Transcribe with Level Meter & Silence VAD
    # ------------------------------------------------------------------ #
    async def record_and_transcribe_whisper(self, max_duration: float = 60.0, silence_timeout: float = 4.0) -> str:
        """
        Records user audio with a dynamic noise calibration and silence threshold.
        - Calibrates background noise in the first 300ms to set a noise gate.
        - Stops if no speech exceeds the noise gate for 4.0s.
        - Stops if 4.0s of silence occurs after speaking.
        """
        self._drain_queue()

        # Whisper processes float32 audio
        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
        )

        audio_blocks = []
        silence_frames = 0
        max_silence_frames = int(silence_timeout / 0.1)  # e.g., 4.0s -> 40 frames
        
        # Timeout for initial voice activity (4.0s)
        initial_timeout_frames = int(4.0 / 0.1)  # 40 frames
        max_total_frames = int(max_duration / 0.1)

        heard_voice = False
        frame_count = 0

        with stream:
            # --- Dynamic Noise Calibration (first 300ms) ---
            self._print_inline("🎙️  Calibrating noise floor (stay quiet)...")
            ambient_blocks = []
            for _ in range(3):
                await asyncio.sleep(0.1)
                while not self._audio_queue.empty():
                    ambient_blocks.append(self._audio_queue.get())
            
            if ambient_blocks:
                # Flatten blocks and subtract mean to remove DC offset for noise floor calibration
                flattened_ambient = [b.flatten() for b in ambient_blocks]
                zero_mean_ambient = [b - np.mean(b) for b in flattened_ambient]
                concat = np.concatenate(zero_mean_ambient)
                ambient_rms = np.sqrt(np.mean(concat**2)) if len(concat) > 0 else 0.0
                # Set noise gate: 2.2x higher than ambient, minimum 0.012 to block fan/noise
                silence_threshold = max(ambient_rms * 2.2, 0.012)
                audio_blocks.extend(flattened_ambient)
            else:
                silence_threshold = 0.012

            self._drain_queue()
            self._print_inline("🎙️  Listening...")

            # --- Main Recording Loop ---
            while frame_count < max_total_frames:
                await asyncio.sleep(0.1)
                frame_count += 1

                current_blocks = []
                while not self._audio_queue.empty():
                    current_blocks.append(self._audio_queue.get())

                if not current_blocks:
                    continue

                block_data = np.concatenate(current_blocks)
                audio_blocks.append(block_data.flatten())

                # Calculate Root Mean Square (RMS) volume level with DC offset removed
                block_zero_mean = block_data.flatten() - np.mean(block_data)
                rms = np.sqrt(np.mean(block_zero_mean**2)) if len(block_zero_mean) > 0 else 0.0

                # Sound level bar visualization normalized to the threshold
                bar_len = 15
                normalized_rms = max(0.0, rms - silence_threshold)
                filled = int(min(normalized_rms * 30, 1.0) * bar_len)
                meter = "█" * filled + "░" * (bar_len - filled)

                is_active = rms > silence_threshold

                if is_active:
                    heard_voice = True
                    silence_frames = 0
                    self._print_inline(f"🎙️  Listening: [{meter}]  (Speaking...)")
                else:
                    if heard_voice:
                        silence_frames += 1
                        self._print_inline(f"🎙️  Listening: [{meter}]  (Waiting...)")
                    else:
                        self._print_inline(f"🎙️  Listening: [{meter}]  (Waiting for speech — 4s timeout)")

                # Initial silence timeout (no speech detected at all within 4 seconds)
                if not heard_voice and frame_count >= initial_timeout_frames:
                    self._print_inline("🎙️  No speech detected (initial 4s timeout).")
                    break

                # Auto silence stop once speech has started
                if heard_voice and silence_frames >= max_silence_frames:
                    self._print_inline("🎙️  Finished speaking (auto-detected silence).")
                    break

        print("", flush=True)  # new line

        if not audio_blocks or not heard_voice:
            # Clear line and reset cursor
            self._print_inline("")
            return ""

        # Concatenate all recorded float32 audio samples
        audio_data = np.concatenate(audio_blocks)

        # Transcribe offline with Whisper
        whisper = self._get_whisper_model()

        def _transcribe():
            segments, _ = whisper.transcribe(audio_data, beam_size=2)
            return " ".join(seg.text for seg in segments).strip()

        self._print_inline("🧠  Processing speech with Whisper model...")
        sys.stdout.flush()

        text = await asyncio.to_thread(_transcribe)

        # Clear processing line
        self._print_inline("")
        return text
