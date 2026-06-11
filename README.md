**Luis — AI Assistant**
Thoughtful. Context-aware. Yours.

Luis is a production-grade, modular AI assistant featuring:

A clean, modern web interface with account authentication
A native Android client for on-device use over your local network
Persistent conversation history for signed-in users (with New Chat support)
Strong offline capabilities, pluggable commands, and graceful LLM fallback
The assistant is designed for thoughtful interactions, excellent follow-up handling, and real usability both locally and when shared with others on the same network.

**Key Features**
Core Capabilities
Modular command system (calculator, notes, reminders, weather, system info, general Q&A, help)
Intelligent intent routing with multi-stage fallback (cache → knowledge base → LLM)
Local-first design with automatic Ollama detection and OpenAI-compatible API fallback
Background reminder scheduler with SQLite persistence
Structured logging and operational health reporting
Fully offline voice I/O (Vosk STT + pyttsx3 TTS, optional Faster-Whisper)


**User Interfaces & Accounts**
Web UI (Flask): Professional login/signup with email + 6-digit OTP verification, guest mode, sidebar with quick actions, New Chat, and History (recent conversations for account users)
Android Client: Native Material 3 chat experience with typewriter responses, native gravity-jumping thinking indicator, server configuration, and full support for authenticated history + new chat
Authentication: Email/password accounts with time-limited OTP verification. Guest sessions available for quick testing. Google Sign-In has been removed.
Conversation History: Authenticated users can view recent conversations, load previous threads, and explicitly start new chats. The backend supports explicit conversation_id and new_chat parameters.
Developer & Operations Experience
Safe AST-based calculator (no eval)
Environment-driven configuration with clear .env.example
Comprehensive test suite
Docker support and production-ready packaging
Clear separation between the web UI server and the dedicated mobile API server.


**Project Structure**
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
_______________________________________________________________________________________________________________________________________________________________________________________________________________________________________

