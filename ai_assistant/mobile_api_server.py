"""
Standalone mobile API server — does NOT modify the web UI.
Exposes only REST endpoints for the Android app.

Usage:
    python mobile_api_server.py
    python mobile_api_server.py --host 0.0.0.0 --port 5000
"""

import argparse
import asyncio
import logging
import os
import socket
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from app.bootstrap import build_application
from config.settings import get_settings
from services.user_store import UserStore
from services.auth_service import AuthService

logger = logging.getLogger("ai_assistant.mobile_api")

_app_instance = None
_user_store = None
_auth_service = None


def _run_async(coro, timeout: float = 300.0):  # Increased for long/complete coding responses (higher token budgets)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
    finally:
        loop.close()


def _get_app():
    global _app_instance
    if _app_instance is None:
        _app_instance = build_application(get_settings())
    return _app_instance


def _get_auth():
    global _user_store, _auth_service
    if _user_store is None:
        _user_store = UserStore()
        _auth_service = AuthService(_user_store)
    return _auth_service, _user_store


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def create_mobile_api() -> Flask:
    api = Flask(__name__)

    @api.route("/api/info")
    def info():
        return jsonify(
            {
                "name": "AI Assistant Mobile API",
                "version": "1.0.0",
                "endpoints": ["/api/info", "/api/health", "/api/chat"],
                "lan_ip": _local_ip(),
            }
        )

    @api.route("/api/health")
    def health():
        app = _get_app()
        report = app.health_service.format_report()
        status = "healthy" if "DEGRADED" not in report.upper() else "degraded"
        return jsonify({"status": status, "report": report})

    @api.route("/api/auth/signup", methods=["POST"])
    def auth_signup():
        auth, _ = _get_auth()
        data = request.get_json(silent=True) or {}
        email = data.get("email")
        password = data.get("password")
        name = data.get("name")

        if not email or not password:
            return jsonify({"error": "Email and password are required."}), 400

        result = auth.signup_with_email(email, password, name)
        if not result["success"]:
            return jsonify({"error": result["error"]}), 400
        return jsonify(result)

    @api.route("/api/auth/verify-otp", methods=["POST"])
    def auth_verify_otp():
        auth, _ = _get_auth()
        data = request.get_json(silent=True) or {}
        email = data.get("email")
        code = data.get("code")

        if not email or not code:
            return jsonify({"error": "Email and code are required."}), 400

        result = auth.complete_email_verification(email, code)
        if not result["success"]:
            return jsonify({"error": result.get("error", "Verification failed")}), 400
        return jsonify(result)

    @api.route("/api/auth/login", methods=["POST"])
    def auth_login():
        auth, _ = _get_auth()
        data = request.get_json(silent=True) or {}
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"error": "Email and password are required."}), 400

        result = auth.login_with_email(email, password)
        if not result["success"]:
            return jsonify({"error": result["error"]}), 400
        return jsonify(result)

    @api.route("/api/auth/google", methods=["POST"])
    def auth_google():
        # Google sign-in option has been removed per requirements.
        return jsonify({"error": "Google sign-in is no longer available. Please use email or guest."}), 410

    @api.route("/api/auth/guest", methods=["POST"])
    def auth_guest():
        auth, _ = _get_auth()
        result = auth.create_guest_session()
        return jsonify(result)

    @api.route("/api/auth/logout", methods=["POST"])
    def auth_logout():
        auth, _ = _get_auth()
        token = request.args.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")
        # Also support token in JSON body for convenience
        if not token:
            data = request.get_json(silent=True) or {}
            token = data.get("token") or ""
        auth.logout(token or "")
        return jsonify({"success": True})

    @api.route("/api/chat", methods=["POST"])
    def chat():
        payload = request.get_json(silent=True) or {}
        message = (payload.get("message") or "").strip()
        token = payload.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")

        if not message:
            return jsonify({"error": "Message is required."}), 400

        auth, store = _get_auth()
        user = auth.get_user_from_token(token) if token else None
        user_id = user.id if user else None

        app = _get_app()
        try:
            response = _run_async(app.assistant.handle_input(message))

            # Persist history for authenticated users. Support explicit conversation switching / new chat.
            conv_id = None
            if user_id:
                force_new = bool(payload.get("new_chat"))
                provided_cid = payload.get("conversation_id")
                if force_new:
                    title = (message or "New chat")[:50]
                    conv_id = store.create_conversation(user_id, title=title)
                elif provided_cid:
                    # Verify ownership (prevents using other users' conv ids)
                    owns = store.get_user_conversation_messages(user_id, int(provided_cid), limit=1)
                    if owns is not None:
                        conv_id = int(provided_cid)
                if conv_id is None:
                    # Default: latest or create fresh
                    conv_id = store.get_latest_conversation(user_id)
                    if not conv_id:
                        conv_id = store.create_conversation(user_id, title=message[:50])
                store.add_message(conv_id, "user", message)
                store.add_message(conv_id, "assistant", response)

            snapshot = app.metrics.get_snapshot().to_dict()
            return jsonify(
                {
                    "response": response,
                    "conversation_id": conv_id,
                    "meta": {
                        "requests": snapshot["total_requests"],
                        "errors": snapshot["command_errors"] + snapshot["llm_errors"],
                    },
                    "user": {"id": user_id, "name": user.name if user else None} if user_id else None
                }
            )
        except asyncio.TimeoutError:
            return jsonify({"error": "Request timed out."}), 504
        except Exception as exc:
            logger.exception("Mobile API chat failed")
            return jsonify({"error": str(exc)}), 500

    @api.route("/api/history", methods=["GET"])
    def get_history():
        token = request.args.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")
        auth, store = _get_auth()
        user = auth.get_user_from_token(token) if token else None
        if not user:
            return jsonify({"error": "Authentication required"}), 401

        conversations = store.get_user_conversations(user.id)
        return jsonify({"conversations": conversations})

    @api.route("/api/history/<int:conv_id>", methods=["GET"])
    def get_conversation(conv_id):
        token = request.args.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")
        auth, store = _get_auth()
        user = auth.get_user_from_token(token) if token else None
        if not user:
            return jsonify({"error": "Authentication required"}), 401

        messages = store.get_user_conversation_messages(user.id, conv_id)
        if messages is None:
            return jsonify({"error": "Conversation not found"}), 404
        return jsonify({"messages": messages})

    return api


def main():
    # Load .env from the same directory as this script (works even if run from another folder)
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
    parser = argparse.ArgumentParser(description="AI Assistant Mobile API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (0.0.0.0 for LAN)")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    _get_app()
    api = create_mobile_api()
    lan = _local_ip()

    gmail_user = os.getenv("GMAIL_USER")
    email_status = "ENABLED (real emails via Gmail)" if gmail_user else "DEV MODE (codes printed to console + returned as dev_code in API)"

    print("\n" + "="*60)
    print("  LUIS ANDROID APP - SERVER READY")
    print("="*60)
    print(f"\n  LAN address (share with friend):  http://{lan}:{args.port}")
    print(f"  Local (for emulator):             http://127.0.0.1:{args.port}")
    print(f"\n  Email / OTP verification: {email_status}")
    print("\n  INSTRUCTIONS FOR TESTING:")
    print("  1. Share the Luis APK with your friend.")
    print("  2. Friend installs the APK (enable 'Unknown sources').")
    print("  3. Both devices must be on the SAME Wi-Fi as this PC.")
    print("  4. In the app: Menu (⋮) → Settings → paste the LAN address above.")
    print("  5. Tap 'Test connection', then start chatting!")
    print("\n  Press Ctrl+C to stop the server\n" + "="*60 + "\n")

    api.run(host=args.host, port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()