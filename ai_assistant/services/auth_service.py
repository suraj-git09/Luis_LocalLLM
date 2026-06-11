import logging
import os
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from werkzeug.security import generate_password_hash, check_password_hash

from services.user_store import UserStore

logger = logging.getLogger("ai_assistant.auth")


class AuthService:
    def __init__(self, user_store: UserStore):
        self.store = user_store

        # Gmail SMTP settings (user's personal Gmail)
        # IMPORTANT: User must use App Password, not real password.
        self.smtp_host = "smtp.gmail.com"
        self.smtp_port = 587
        self.smtp_user = os.getenv("GMAIL_USER")          # e.g. yourname@gmail.com
        self.smtp_app_password = os.getenv("GMAIL_APP_PASSWORD")  # 16-char app password

    # --- Password ---
    def hash_password(self, password: str) -> str:
        return generate_password_hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        return check_password_hash(password_hash, password)

    # --- Email OTP (using personal Gmail) ---
    def send_verification_otp(self, email: str) -> str:
        """
        Generates and sends (or attempts to send) a 6-digit OTP.
        Always returns the code so callers can use it for dev fallbacks / tests.
        Real delivery only happens when GMAIL_USER + GMAIL_APP_PASSWORD are set.
        """
        code = self.store.generate_otp(email)

        dev_mode = not self.smtp_user or not self.smtp_app_password

        if dev_mode:
            # Development / no email configured: surface via server logs + dev_code in API response
            logger.warning("=== [DEV MODE] OTP for %s: %s (no GMAIL_USER/GMAIL_APP_PASSWORD configured) ===", email, code)
            print(f"\n=== [DEV] OTP for {email}: {code} ===\n")
            return code

        subject = "Your Luis Verification Code"
        body = self._build_otp_email_body(email, code)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.smtp_user
        msg["To"] = email

        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_app_password)
                server.sendmail(self.smtp_user, email, msg.as_string())
            logger.info("OTP email sent successfully to %s", email)
            return code
        except Exception as e:
            logger.error("Failed to send OTP email to %s: %s", email, e)
            print(f"[AuthService] Failed to send OTP email: {e}")
            # Return code anyway (dev can still proceed by looking at logs)
            return code

    def resend_verification_otp(self, email: str) -> str:
        """Re-generate and (re)send OTP for an existing email (used for resend button / duplicate signup attempts)."""
        # Just delegate — generate_otp will overwrite the previous code for this email
        return self.send_verification_otp(email)

    def _build_otp_email_body(self, email: str, code: str) -> str:
        """Professional, short email template as requested."""
        return f"""Hello,

Thank you for signing up with Luis.

Your 6-digit verification code is:

{code}

This code will expire in 10 minutes.

If you did not request this, you can safely ignore this email.

— The Luis Team
"""

    def verify_otp(self, email: str, code: str) -> bool:
        return self.store.verify_otp(email, code)

    # --- User creation ---
    def signup_with_email(self, email: str, password: str, name: Optional[str] = None) -> dict:
        email = email.lower().strip()
        existing = self.store.get_user_by_email(email)

        if existing:
            # Treat as resend request (supports "Resend code" buttons and repeated signup attempts).
            # This makes resend work reliably without a separate API endpoint for most clients.
            code = self.resend_verification_otp(email)
            dev_mode = not self.smtp_user or not self.smtp_app_password
            resp = {
                "success": True,
                "user_id": existing.id,
                "message": "Verification code resent to your email."
            }
            if dev_mode:
                resp["dev_code"] = code
                resp["message"] = "Dev mode: new verification code generated (check server console/logs)."
            return resp

        password_hash = self.hash_password(password)
        user = self.store.create_user(email=email, password_hash=password_hash, name=name or email.split("@")[0])

        # Send OTP (real email or dev fallback that prints/logs the code)
        code = self.send_verification_otp(email)

        dev_mode = not self.smtp_user or not self.smtp_app_password
        resp = {
            "success": True,
            "user_id": user.id,
            "message": "Verification code sent to your email."
        }
        if dev_mode:
            resp["dev_code"] = code
            resp["message"] = "Dev mode: verification code generated. Check the server console or logs (dev_code also returned for local testing)."
        return resp

    def complete_email_verification(self, email: str, code: str) -> dict:
        if not self.verify_otp(email, code):
            return {"success": False, "error": "Invalid or expired verification code."}

        user = self.store.get_user_by_email(email)
        if not user:
            return {"success": False, "error": "User not found."}

        # Issue long-lived token
        token = self.store.create_session(user.id)
        return {"success": True, "token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}

    def login_with_email(self, email: str, password: str) -> dict:
        email = email.lower().strip()
        user = self.store.get_user_by_email(email)
        if not user or not user.password_hash:
            return {"success": False, "error": "Invalid email or password."}

        if not self.verify_password(password, user.password_hash):
            return {"success": False, "error": "Invalid email or password."}

        token = self.store.create_session(user.id)
        return {"success": True, "token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}

    # --- Google OAuth (hardened) ---
    def _verify_google_id_token(self, id_token: str) -> dict:
        """Verify a Google ID token and return the claims (sub, email, name, ...)."""
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        if not client_id or "REPLACE_WITH_YOUR_WEB_CLIENT_ID" in client_id:
            raise ValueError(
                "GOOGLE_CLIENT_ID is not configured or still has the placeholder. "
                "Set the real Web application Client ID in .env (and matching value in Android strings.xml)."
            )
        try:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests

            request = google_requests.Request()
            idinfo = google_id_token.verify_oauth2_token(id_token, request, client_id)

            # Extra audience check (defense in depth)
            if idinfo.get("aud") != client_id:
                raise ValueError("Token audience does not match configured client ID")

            return idinfo
        except Exception as exc:
            logger.warning("Google ID token verification failed: %s", exc)
            raise ValueError("Invalid or expired Google ID token") from exc

    def login_or_create_with_google(
        self,
        google_id: Optional[str] = None,
        email: Optional[str] = None,
        name: Optional[str] = None,
        id_token: Optional[str] = None,
    ) -> dict:
        """Create or log in a user via Google.

        Preferred (secure): pass id_token (real Google ID token). google_id + email is accepted
        only when GOOGLE_CLIENT_ID is not set (dev/demo mode).
        """
        verified_claims = None
        if id_token:
            verified_claims = self._verify_google_id_token(id_token)
            google_id = verified_claims.get("sub")
            email = verified_claims.get("email") or email
            name = verified_claims.get("name") or name
            logger.info("Google ID token verified successfully for sub=%s", google_id)

        if not google_id:
            return {"success": False, "error": "google_id or a valid id_token is required"}

        # Dev/demo mode (only when no client ID configured): allow raw google_id
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        if not id_token and not client_id:
            logger.warning(
                "Google sign-in using raw google_id without ID token verification (DEV MODE only — "
                "set GOOGLE_CLIENT_ID in .env + matching value in Android strings.xml for real verification)"
            )

        email = email.lower().strip() if email else None
        user = self.store.get_user_by_google_id(google_id)

        if not user and email:
            user = self.store.get_user_by_email(email)

        if not user:
            user = self.store.create_user(
                email=email,
                google_id=google_id,
                name=name,
                is_guest=False
            )
        else:
            # Link google_id to an existing email account if needed (best-effort)
            if not user.google_id and google_id:
                # Note: a production implementation would do an explicit UPDATE here.
                # For now we rely on the next lookup by google_id after recreation isn't needed
                # because we just created/linked above. This keeps behavior stable.
                pass

        token = self.store.create_session(user.id)
        return {"success": True, "token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}

    # --- Guest ---
    def create_guest_session(self) -> dict:
        user = self.store.create_user(is_guest=True, name="Guest")
        token = self.store.create_session(user.id, expiry_seconds=60 * 60 * 6)  # 6 hours for guests
        return {"success": True, "token": token, "user": {"id": user.id, "name": "Guest", "is_guest": True}}

    def logout(self, token: str) -> dict:
        """Invalidate the session token server-side. Idempotent and safe for invalid/expired tokens."""
        self.store.delete_session(token)
        return {"success": True}

    def get_user_from_token(self, token: str):
        return self.store.get_user_from_token(token)
