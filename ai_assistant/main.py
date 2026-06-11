import argparse
import asyncio
import logging
import sys

from dotenv import load_dotenv

from app.bootstrap import build_application
from config.settings import get_settings

logger = logging.getLogger("ai_assistant.main")


async def text_mode(assistant):
    print("\n--- Text Mode ---")
    print("Type 'exit' to quit.\n")

    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit"}:
                print("Shutting down assistant...")
                break

            response = await assistant.handle_input(user_input)
            print(f"Assistant: {response}\n")
    except KeyboardInterrupt:
        print("\nInterrupted by user.")


async def voice_mode(assistant, settings):
    try:
        from services.voice_stt import OfflineSTTService
        from services.voice_tts import OfflineTTSService
    except ImportError as exc:
        print(f"\n[Error] Voice dependencies missing: {exc}")
        print("Install them with: pip install -r requirements.txt")
        return

    stt = OfflineSTTService(
        vosk_model_path=str(settings.vosk_model_dir),
        whisper_model_size=settings.whisper_model_size,
    )
    tts = OfflineTTSService(rate=settings.tts_rate, volume=settings.tts_volume)
    wake_word = settings.wake_word

    print("\n--- Voice Mode (Offline) ---")
    await tts.speak(f"Voice assistant is ready. Say '{wake_word}' to begin.")

    async def type_response(text: str, wpm: int = 150):
        words = text.split(" ")
        delay = 60.0 / wpm
        sys.stdout.write("Assistant: ")
        sys.stdout.flush()
        for word in words:
            sys.stdout.write(word + " ")
            sys.stdout.flush()
            await asyncio.sleep(delay)
        sys.stdout.write("\n\n")
        sys.stdout.flush()

    async def handle_input_with_thinking(user_input: str) -> str:
        spinner = ["|", "/", "-", "\\"]
        task = asyncio.create_task(assistant.handle_input(user_input))
        idx = 0
        while not task.done():
            sys.stdout.write(f"\r  Thinking... {spinner[idx % len(spinner)]}  ")
            sys.stdout.flush()
            idx += 1
            await asyncio.sleep(0.1)
        sys.stdout.write("\r" + " " * 40 + "\r")
        sys.stdout.flush()
        return await task

    try:
        while True:
            await stt.listen_for_wake_word(wake_word)
            await tts.speak("Yes? I am listening.")

            session_active = True
            consecutive_silence = 0

            while session_active:
                user_input = await stt.record_and_transcribe_whisper(
                    max_duration=60.0,
                    silence_timeout=4.0,
                )
                user_input_clean = (
                    user_input.lower()
                    .strip()
                    .replace(".", "")
                    .replace(",", "")
                    .replace("?", "")
                    .replace("!", "")
                )

                if not user_input or len(user_input.strip()) < 2:
                    consecutive_silence += 1
                    if consecutive_silence >= 2:
                        await tts.speak("I'll go back to sleep now. Let me know if you need anything.")
                        print("\nSleeping... (waiting for wake word)", flush=True)
                        session_active = False
                    else:
                        await tts.speak("Sorry, I didn't catch that. Are you still there?")
                    continue

                consecutive_silence = 0
                print(f'  You: "{user_input}"', flush=True)

                if user_input_clean in {
                    "exit",
                    "quit",
                    "stop",
                    "goodbye",
                    "stop voice",
                    "go to sleep",
                    "bye",
                    "cancel",
                }:
                    await tts.speak("Goodbye! I will be waiting for your wake word.")
                    print("\nSleeping... (waiting for wake word)", flush=True)
                    session_active = False
                    break

                response = await handle_input_with_thinking(user_input)
                speak_task = asyncio.create_task(tts.speak(response))
                await type_response(response)
                await speak_task
                print("  Ready for your next query...", flush=True)
    except KeyboardInterrupt:
        print("\nVoice mode interrupted.")


def parse_args():
    parser = argparse.ArgumentParser(description="Production AI Assistant")
    parser.add_argument(
        "--mode",
        choices=["text", "voice", "web"],
        help="Interaction mode. If omitted, prompts at startup.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Web server host (web mode)")
    parser.add_argument("--port", type=int, default=5000, help="Web server port (web mode)")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override LOG_LEVEL from environment.",
    )
    return parser.parse_args()


def _launch_web(host: str, port: int):
    from web.server import run_web_server

    run_web_server(host=host, port=port)


async def main():
    load_dotenv()
    args = parse_args()

    if args.log_level:
        import os

        os.environ["LOG_LEVEL"] = args.log_level

    mode = args.mode
    if mode is None:
        print("Select interaction mode:")
        print("  [1] Text mode  (keyboard)")
        print("  [2] Voice mode (offline mic + speaker)")
        print("  [3] Web mode   (browser UI)")
        choice = input("\nEnter 1, 2, or 3: ").strip()
        if choice == "2":
            mode = "voice"
        elif choice == "3":
            mode = "web"
        else:
            mode = "text"

    if mode == "web":
        _launch_web(args.host, args.port)
        return

    app = build_application(get_settings())
    print("Assistant is ready.\n")

    try:
        if mode == "voice":
            await voice_mode(app.assistant, app.settings)
        else:
            await text_mode(app.assistant)
    finally:
        app.worker.stop()


def entrypoint():
    asyncio.run(main())


if __name__ == "__main__":
    entrypoint()