# Security Policy

## Reporting Issues

If you discover a security vulnerability, do not open a public issue. Contact the maintainer directly.

## Secret Management

- Never commit `.env` files or API keys to version control.
- Use `.env.example` as a template only — copy to `.env` locally.
- Rotate API keys immediately if they are ever exposed.

## Known Exposure (Action Required)

A previous commit (`8beb591`) contained an `OPENAI_API_KEY` in both:

- `Ai_Assitant/.env`
- `ai_assistant/services/llm_service.py` (hardcoded fallback)

**You must rotate that API key** on your provider dashboard before pushing to a public repository. Removing the file from the latest commit does not erase it from git history.

To scrub history before publishing:

```bash
# Option A: BFG Repo-Cleaner (recommended)
# Download from https://rtyley.github.io/bfg-repo-cleaner/
java -jar bfg.jar --delete-files .env
java -jar bfg.jar --replace-text passwords.txt  # file with sk-...=REMOVED
git reflog expire --expire=now --all && git gc --prune=now --aggressive

# Option B: git filter-repo
pip install git-filter-repo
git filter-repo --path Ai_Assitant/.env --invert-paths
```

Then force-push only if you understand the consequences for collaborators.

## Built-in Protections

| Control | Default | Env Variable |
|---------|---------|--------------|
| Max user input length | 2000 chars | `MAX_INPUT_CHARS` |
| Max note length | 500 chars | `MAX_NOTE_CHARS` |
| Max reminder length | 300 chars | `MAX_REMINDER_CHARS` |
| Conversation memory window | 20 messages | `MAX_MEMORY_MESSAGES` |
| LLM request timeout | 30 seconds | `LLM_TIMEOUT_SECONDS` |
| LLM max response tokens | 512 | `LLM_MAX_TOKENS` |
| LLM rate limit | 10 calls / 60s | `LLM_RATE_LIMIT_CALLS`, `LLM_RATE_LIMIT_PERIOD` |
| Safe math evaluation | AST-only | Built into calculator |
| SQL injection prevention | Parameterized queries | All SQLite services |
| Control character filtering | Enabled | Input validation layer |

## Dependency Auditing

Run periodically:

```bash
pip install pip-audit
pip-audit -r requirements.txt
```

## Production Checklist

- [ ] Rotate any previously committed API keys
- [ ] Configure `GMAIL_USER` + `GMAIL_APP_PASSWORD` for real email verification (or be aware of dev mode behavior)
- [ ] Set LLM credentials via environment only
- [ ] Keep `.env` out of git (verify with `git check-ignore .env`)
- [ ] Run `pytest` before each release
- [ ] Run `pip-audit` monthly
- [ ] Review `data/logs/assistant.log` for repeated failures
- [ ] Document the LAN address and auth flow when sharing the Android APK with others

**Note on authentication:** Google Sign-In has been removed. Email + OTP is the supported account method. When Gmail credentials are not configured, verification codes are returned via the API (`dev_code`) and displayed in the UIs for local development.