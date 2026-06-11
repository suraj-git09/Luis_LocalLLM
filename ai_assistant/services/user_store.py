import os
import sqlite3
import secrets
import time
from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class User:
    id: int
    email: Optional[str]
    password_hash: Optional[str]
    google_id: Optional[str]
    name: Optional[str]
    is_guest: bool
    created_at: str


class UserStore:
    def __init__(self, db_path: str = "data/app.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

        # In-memory OTP store: {email: {"code": "123456", "expires": timestamp, "attempts": 0}}
        self._otp_store: Dict[str, dict] = {}
        self.OTP_EXPIRY_SECONDS = 10 * 60  # 10 minutes
        self.MAX_OTP_ATTEMPTS = 5

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                password_hash TEXT,
                google_id TEXT UNIQUE,
                name TEXT,
                is_guest INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,  -- 'user' or 'assistant'
                content TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)

        conn.commit()
        conn.close()

    # --- User methods ---
    def create_user(self, email: Optional[str] = None, password_hash: Optional[str] = None,
                    google_id: Optional[str] = None, name: Optional[str] = None,
                    is_guest: bool = False) -> User:
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO users (email, password_hash, google_id, name, is_guest)
            VALUES (?, ?, ?, ?, ?)
        """, (email, password_hash, google_id, name, 1 if is_guest else 0))
        user_id = c.lastrowid
        conn.commit()
        conn.close()
        return self.get_user_by_id(user_id)

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return User(
            id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            google_id=row["google_id"],
            name=row["name"],
            is_guest=bool(row["is_guest"]),
            created_at=row["created_at"]
        )

    def get_user_by_email(self, email: str) -> Optional[User]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_user(row)

    def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_user(row)

    def _row_to_user(self, row) -> User:
        return User(
            id=row["id"], email=row["email"], password_hash=row["password_hash"],
            google_id=row["google_id"], name=row["name"],
            is_guest=bool(row["is_guest"]), created_at=row["created_at"]
        )

    # --- Session / Token ---
    def create_session(self, user_id: int, expiry_seconds: int = 60 * 60 * 24 * 30) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = int(time.time()) + expiry_seconds
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at)
        )
        conn.commit()
        conn.close()
        return token

    def get_user_from_token(self, token: str) -> Optional[User]:
        conn = self._get_conn()
        row = conn.execute("""
            SELECT u.* FROM users u
            JOIN user_sessions s ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
        """, (token, int(time.time()))).fetchone()
        conn.close()
        if row:
            return self._row_to_user(row)
        return None

    def delete_session(self, token: str):
        conn = self._get_conn()
        conn.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()

    # --- OTP (in-memory for simplicity) ---
    def generate_otp(self, email: str) -> str:
        code = f"{secrets.randbelow(900000) + 100000}"  # 6 digit
        self._otp_store[email.lower()] = {
            "code": code,
            "expires": time.time() + self.OTP_EXPIRY_SECONDS,
            "attempts": 0
        }
        return code

    def verify_otp(self, email: str, code: str) -> bool:
        email = email.lower()
        record = self._otp_store.get(email)
        if not record:
            return False

        if time.time() > record["expires"]:
            del self._otp_store[email]
            return False

        record["attempts"] += 1
        if record["attempts"] > self.MAX_OTP_ATTEMPTS:
            del self._otp_store[email]
            return False

        if record["code"] == code:
            del self._otp_store[email]
            return True
        return False

    # --- Chat History ---
    def create_conversation(self, user_id: int, title: str = "New Conversation") -> int:
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO conversations (user_id, title) VALUES (?, ?)
        """, (user_id, title))
        conv_id = c.lastrowid
        conn.commit()
        conn.close()
        return conv_id

    def add_message(self, conversation_id: int, role: str, content: str):
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)
        """, (conversation_id, role, content))
        conn.execute("""
            UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (conversation_id,))
        conn.commit()
        conn.close()

    def get_user_conversations(self, user_id: int, limit: int = 20):
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT id, title, created_at, updated_at 
            FROM conversations 
            WHERE user_id = ? 
            ORDER BY updated_at DESC 
            LIMIT ?
        """, (user_id, limit)).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_conversation_messages(self, conversation_id: int, limit: int = 50):
        """Unsafe direct access by ID only. Prefer get_user_conversation_messages for API use."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT role, content, timestamp 
            FROM messages 
            WHERE conversation_id = ? 
            ORDER BY timestamp ASC 
            LIMIT ?
        """, (conversation_id, limit)).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_user_conversation_messages(self, user_id: int, conversation_id: int, limit: int = 50):
        """Return messages for a conversation only if it belongs to the authenticated user.
        Returns None if the conversation does not exist or does not belong to the user.
        """
        conn = self._get_conn()
        # Enforce ownership to prevent IDOR
        owns = conn.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id)
        ).fetchone()
        if not owns:
            conn.close()
            return None
        rows = conn.execute("""
            SELECT role, content, timestamp 
            FROM messages 
            WHERE conversation_id = ? 
            ORDER BY timestamp ASC 
            LIMIT ?
        """, (conversation_id, limit)).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_latest_conversation(self, user_id: int) -> Optional[int]:
        conn = self._get_conn()
        row = conn.execute("""
            SELECT id FROM conversations 
            WHERE user_id = ? 
            ORDER BY updated_at DESC 
            LIMIT 1
        """, (user_id,)).fetchone()
        conn.close()
        return row["id"] if row else None
