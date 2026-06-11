import asyncio
import logging
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

from app.bootstrap import Application, build_application
from config.settings import get_settings
from services.user_store import UserStore
from services.auth_service import AuthService

logger = logging.getLogger("ai_assistant.web")

_app_instance: Application | None = None
_user_store = None
_auth_service = None
WEB_DIR = Path(__file__).resolve().parent


def _run_async(coro, timeout: float = 300.0):  # Increased for long/complete coding responses (higher token budgets)
    """Run async assistant code on a fresh loop per request (Flask-safe)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
    finally:
        loop.close()


def _get_app() -> Application:
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


def create_web_app() -> Flask:
    flask_app = Flask(
        __name__,
        template_folder=str(WEB_DIR / "templates"),
        static_folder=str(WEB_DIR / "static"),
    )

    @flask_app.route("/")
    def index():
        return render_template("index.html")

    @flask_app.route("/api/health")
    def health():
        app = _get_app()
        report = app.health_service.format_report()
        status = "healthy" if "DEGRADED" not in report.upper() else "degraded"
        return jsonify({"status": status, "report": report})

    @flask_app.route("/api/auth/signup", methods=["POST"])
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

    @flask_app.route("/api/auth/verify-otp", methods=["POST"])
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

    @flask_app.route("/api/auth/login", methods=["POST"])
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

    @flask_app.route("/api/auth/google", methods=["POST"])
    def auth_google():
        # Google sign-in option has been removed per requirements.
        return jsonify({"error": "Google sign-in is no longer available. Please use email or guest."}), 410

    @flask_app.route("/api/auth/guest", methods=["POST"])
    def auth_guest():
        auth, _ = _get_auth()
        result = auth.create_guest_session()
        return jsonify(result)

    @flask_app.route("/api/auth/logout", methods=["POST"])
    def auth_logout():
        auth, _ = _get_auth()
        token = request.args.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            data = request.get_json(silent=True) or {}
            token = data.get("token") or ""
        auth.logout(token or "")
        return jsonify({"success": True})

    @flask_app.route("/api/chat", methods=["POST"])
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
            return jsonify({"error": "Request timed out. Try a shorter prompt."}), 504
        except Exception as exc:
            logger.exception("Web chat request failed")
            return jsonify({"error": str(exc)}), 500

    @flask_app.route("/api/history", methods=["GET"])
    def get_history():
        token = request.args.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")
        auth, store = _get_auth()
        user = auth.get_user_from_token(token) if token else None
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        conversations = store.get_user_conversations(user.id)
        return jsonify({"conversations": conversations})

    @flask_app.route("/api/history/<int:conv_id>", methods=["GET"])
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

    return flask_app


def run_web_server(host: str = "127.0.0.1", port: int = 5000, debug: bool = False):
    # Load .env from the same directory as this file
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
    _get_app()
    flask_app = create_web_app()

    gmail_user = os.getenv("GMAIL_USER")
    email_status = "ENABLED (real emails via Gmail)" if gmail_user else "DEV MODE (codes printed to console + returned as dev_code in API)"
    print(f"\n  AI Assistant Web UI")
    print(f"  Local:  http://{host}:{port}")
    print(f"  Email / OTP: {email_status}")
    print(f"  Press Ctrl+C to stop\n")

    flask_app.run(host=host, port=port, debug=debug, use_reloader=False)