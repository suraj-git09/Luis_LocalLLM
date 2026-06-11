# Luis — AI Assistant

**Thoughtful. Context-aware. Yours.**

Luis is a production-grade, modular AI assistant featuring:

- A clean, modern **web interface** with account authentication
- A native **Android client** for on-device use over your local network
- Persistent **conversation history** for signed-in users (with New Chat support)
- Strong offline capabilities, pluggable commands, and graceful LLM fallback

The assistant is designed for thoughtful interactions, excellent follow-up handling, and real usability both locally and when shared with others on the same network.

## Key Features

### Core Capabilities
- Modular command system (calculator, notes, reminders, weather, system info, general Q&A, help)
- Intelligent intent routing with multi-stage fallback (cache → knowledge base → LLM)
- Local-first design with automatic Ollama detection and OpenAI-compatible API fallback
- Background reminder scheduler with SQLite persistence
- Structured logging and operational health reporting
- Fully offline voice I/O (Vosk STT + pyttsx3 TTS, optional Faster-Whisper)

### User Interfaces & Accounts
- **Web UI** (Flask): Professional login/signup with email + 6-digit OTP verification, guest mode, sidebar with quick actions, **New Chat**, and **History** (recent conversations for account users)
- **Android Client**: Native Material 3 chat experience with typewriter responses, native gravity-jumping thinking indicator, server configuration, and full support for authenticated history + new chat
- **Authentication**: Email/password accounts with time-limited OTP verification. Guest sessions available for quick testing. Google Sign-In has been removed.
- **Conversation History**: Authenticated users can view recent conversations, load previous threads, and explicitly start new chats. The backend supports explicit `conversation_id` and `new_chat` parameters.

### Developer & Operations Experience
- Safe AST-based calculator (no `eval`)
- Environment-driven configuration with clear `.env.example`
- Comprehensive test suite
- Docker support and production-ready packaging
- Clear separation between the web UI server and the dedicated mobile API server

## Project Structure

```
ai_assistant/
├── app/                  # Bootstrap and dependency wiring
├── assistant/            # Core request routing and pipeline
├── commands/             # Pluggable command handlers
├── config/               # Settings (env-driven)
├── nlp/                  # Intent classification
├── services/             # Auth, storage, LLM, reminders, voice, metrics, etc.
├── web/                  # Flask web UI (templates + static)
├── web/server.py         # Web interface server
├── mobile_api_server.py  # Dedicated REST API for Android clients
├── main.py               # CLI entry point
├── tests/
├── scripts/
└── requirements*.txt
```

Companion client:

```
AIAssistantAndroid/       # Native Kotlin + Material 3 Android app
```

## Authentication & User Accounts

Luis supports two types of sessions:

- **Account users** (recommended for full experience)
  - Sign up with email + password
  - Receive a 6-digit verification code via email (or in dev mode directly in the UI)
  - Full access to persistent **History** and **New Chat** features

- **Guest sessions**
  - No email required
  - Temporary (6-hour) sessions
  - No conversation history across sessions

**Important:** Real email delivery requires `GMAIL_USER` and `GMAIL_APP_PASSWORD` (Gmail App Password) to be configured. When these are not set, the system operates in **development mode**: the code is printed to the server console/logs **and** returned in the API response as `dev_code` so the web and Android UIs can display it directly.

Google Sign-In has been removed from both the web and Android clients.

See the Configuration section and `.env.example` for setup details.

## Web Interface

Run the web server:

```bash
python -m ai_assistant.web.server
# or
python scripts/run_web.ps1
```

Open http://127.0.0.1:5000.

The interface includes:
- Clean authentication flow (Log in / Sign up / Guest)
- Sidebar with Quick actions, **+ New chat** button, and **History** list (visible only for authenticated accounts)
- Responsive chat pane with code formatting and live health status
- Context-aware responses with excellent follow-up support

Authenticated users can switch between previous conversations and start fresh threads that are persisted server-side.

## Android Client

The Android app connects to `mobile_api_server.py` (or the regular web server) over your local Wi-Fi.

Key capabilities:
- Material 3 dark theme with polished chat UI
- Word-by-word typewriter animation for assistant replies
- Native gravity-style jumping dots thinking indicator (no heavy animation libraries)
- Persistent local chat + server-backed history for account users
- Menu actions: **New chat**, **History** (loads previous conversations), **Logout**, Settings, Test connection, Clear chat

See [AIAssistantAndroid/README.md](AIAssistantAndroid/README.md) for build instructions and detailed usage.

Quick start for mobile backend:

```bash
python mobile_api_server.py
# Copy the "LAN address" it prints and enter it in the app Settings
```

## Getting Started

### 1. Environment

```bash
cd ai_assistant
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
cp .env.example .env
```

### 2. Configure

Edit `.env` (critical items):

- LLM access: `OPENAI_API_KEY` or a local Ollama model
- **Email verification** (strongly recommended for real use):
  ```env
  GMAIL_USER=you@gmail.com
  GMAIL_APP_PASSWORD=your-16-char-app-password
  ```

Without Gmail credentials the system still works in dev mode (codes shown in UI + server logs).

### 3. Run Modes

| Mode                    | Command                                      | Notes |
|-------------------------|----------------------------------------------|-------|
| CLI (text)              | `python main.py`                             | Default |
| CLI (voice)             | `python main.py --mode voice`                | Requires Vosk model |
| Web UI                  | `python -m ai_assistant.web.server`          | http://127.0.0.1:5000 |
| Mobile API (Android)    | `python mobile_api_server.py`                | Prints LAN address automatically |
| Production scripts      | `.\scripts\run.ps1` / `./scripts/run.sh`     | Venv + tests + run |

## Configuration Reference

See `.env.example` for the complete list. Important variables:

| Variable                  | Purpose                                      |
|---------------------------|----------------------------------------------|
| `OPENAI_API_KEY`          | Online LLM fallback                          |
| `LOCAL_MODEL` / `OLLAMA_BASE_URL` | Local Ollama                                 |
| `GMAIL_USER` / `GMAIL_APP_PASSWORD` | Email delivery for account verification   |
| `MAX_INPUT_CHARS` etc.    | Input & rate limiting                        |

When email credentials are absent, signup responses include a `dev_code` field. Both frontends display this automatically.

## Conversation History & Multi-Chat Support

Authenticated users benefit from server-side conversation storage:

- **Web**: History list appears in the sidebar. Click any entry to load it. Use "+ New chat" to start a fresh thread.
- **Android**: Use the menu → **History** to browse and load previous conversations. **New chat** starts a clean thread.
- Backend chat endpoint accepts optional `conversation_id` and `new_chat` flags for precise control.

Guest sessions and the CLI do not persist cross-session history.

## Testing

```bash
pip install -r requirements.txt pytest pytest-asyncio
pytest
```

## Deployment & Production

- Use the Docker Compose setup for combined assistant + Ollama.
- Always keep `.env` out of version control.
- Rotate any secrets that may have been committed previously (see `SECURITY.md`).
- For Android distribution to others, use the LAN address printed by `mobile_api_server.py` and the instructions in `AIAssistantAndroid/SHARE_WITH_FRIEND.txt`.

## Troubleshooting

**Users not receiving verification emails**
- Set `GMAIL_USER` and a valid Gmail **App Password**.
- Check server startup logs — it prints the current email status (`ENABLED` or `DEV MODE`).
- In dev mode the code appears on the OTP screen and in the terminal.

**Android can't connect**
- Use the exact LAN address printed by `mobile_api_server.py`.
- Same Wi-Fi network.
- Firewall allowing port 5000.
- Emulator: `http://10.0.2.2:5000`.

**Resend code**
- The resend button works for pending verifications. The backend treats repeat signup attempts for the same email as a resend.

## Security

See [SECURITY.md](SECURITY.md) for secret handling, input limits, and the production checklist.

## Android Client Details

Full documentation, build instructions, and sharing guide live in the `AIAssistantAndroid/` directory (including `README.md` and `SHARE_WITH_FRIEND.txt`).

## Documentation

The primary, always-up-to-date documentation is:

- `README.md` (this file) — architecture, getting started, authentication, history features
- `AIAssistantAndroid/README.md` — Android-specific usage and building
- `SECURITY.md` — secrets, limits, and production checklist
- `.env.example` — complete configuration reference with email setup guidance

A generated Word document snapshot can be created with:

```bash
cd ai_assistant
python scripts/generate_documentation.py
```

This produces `AI_Assistant_Project_Documentation.docx` in the project root.

## License

MIT

## Quick Start

### 1. Create virtual environment

```bash
cd ai_assistant
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

Voice dependencies are included in `requirements.txt`. For a minimal text-only install:

```bash
pip install python-dotenv openai
```

### 3. Configure environment

```bash
copy .env.example .env
```

Set `OPENAI_API_KEY` for online LLM usage, or run [Ollama](https://ollama.com) locally for offline LLM.

### 4. Run

```bash
python main.py
```

Or with explicit mode:

```bash
python main.py --mode text
python main.py --mode voice
python main.py --mode web
python main.py --log-level DEBUG
```

### Web UI (Flask)

```bash
pip install -r requirements.txt
python main.py --mode web
# open http://127.0.0.1:5000
```

Or on Windows:

```powershell
.\scripts\run_web.ps1
```

The web UI includes quick-action chips, live health status, code formatting, and token-optimized LLM responses.

## Supported Commands

| Command          | Example                                      |
|------------------|----------------------------------------------|
| Calculator       | `calculate 15 * 24`                          |
| Notes            | `save note buy milk` / `show notes`          |
| System info      | `system info` / `what is the time`           |
| Weather          | `what is the weather in delhi`               |
| Reminders        | `remind me to drink water in 5 minutes`      |
| Help             | `help`                                       |
| General Q&A      | Any thoughtful or open-ended question        |

## Testing

```bash
pip install pytest pytest-asyncio
pytest
```

## Monitoring & Health

Ask `system health` for a live operational report (databases, LLM backend, reminder worker, request/error metrics, uptime).

Logs are rotated automatically (default 5 MB × 3 backups). See `LOG_MAX_BYTES` / `LOG_BACKUP_COUNT`.

## Voice Mode

Requires a Vosk model (e.g. `vosk-model-small-en-us-0.15` extracted to `data/vosk-model-small-en-us-0.15`).

## Deployment

See the **Getting Started** section above for the recommended ways to run the web UI and mobile API server.

Docker Compose is available for combined assistant + Ollama deployments.

## Android Client

A full-featured native companion app lives in `AIAssistantAndroid/`.

- Connects to `mobile_api_server.py` (recommended) or the web server.
- Supports authenticated **History** and **New Chat**.
- Includes build scripts that work without Android Studio.

Detailed instructions, build steps, and sharing guide: [AIAssistantAndroid/README.md](AIAssistantAndroid/README.md).

Quick mobile backend:
```bash
python mobile_api_server.py
```

## License

MIT