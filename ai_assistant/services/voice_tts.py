import pyttsx3
import asyncio


class OfflineTTSService:
    """
    Offline Text-to-Speech engine using the Windows native SAPI5 backend (pyttsx3).
    No network calls — runs entirely on local system voices.
    """

    def __init__(self, voice_id=None, rate=175, volume=1.0):
        self.voice_id = voice_id
        self.rate = rate
        self.volume = volume

    def _speak_sync(self, text: str):
        """Blocking speech call initialized entirely inside this thread."""
        try:
            # Initialize pyttsx3 locally inside the worker thread to prevent COM freezes
            engine = pyttsx3.init()
            engine.setProperty('rate', self.rate)
            engine.setProperty('volume', self.volume)

            voices = engine.getProperty('voices')
            if self.voice_id is not None and self.voice_id < len(voices):
                engine.setProperty('voice', voices[self.voice_id].id)
            elif voices:
                # Try to pick a clear female voice (Zira) on Windows, fallback to first
                for voice in voices:
                    if "zira" in voice.name.lower():
                        engine.setProperty('voice', voice.id)
                        break

            engine.say(text)
            engine.runAndWait()
            # Delete the reference to release the SAPI COM objects cleanly
            del engine
        except Exception as e:
            # Fail gracefully in console if audio output fails
            print(f"\n[TTS Warning] Speech output failed: {e}", flush=True)

    async def speak(self, text: str):
        """Non-blocking async wrapper — offloads speech to a thread."""
        await asyncio.to_thread(self._speak_sync, text)
