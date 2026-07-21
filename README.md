# AI Content Discovery Assistant

An AI-powered assistant that continuously searches X (Twitter) and Google News for content opportunities in your niche, filters them with AI, notifies you on Telegram, and generates ready-to-post X content only after your explicit approval.

**Nothing is ever published automatically. You stay in complete control.**

---

## Features

- **Multi-source discovery**
  - X (Twitter) – keyword, hashtag and trend search
  - Google News – RSS-based, no API key required
- **AI relevance filter** – only high-quality, on-niche opportunities reach you
- **Clean Telegram notifications** with:
  - Source, Topic, Summary
  - Why it matters
  - Suggested angle
  - ✅ Approve / ❌ Skip / 🔄 Rewrite Angle buttons
- **AI writing engine** that follows a strict Human Writing System
  - Natural rhythm, no AI clichés, no em dashes
  - Single posts or short threads
  - Optional image-generation prompts
  - Hashtags only when they add value
- **Fully configurable** via environment variables
- **Production-ready** Ubuntu 24.04 deployment (systemd, automatic restart, logging)
- **Open source** (MIT)

---

## Screenshots

> Placeholder – add screenshots of the Telegram cards and generated posts here.

---

## Architecture Overview

```
Scheduler
   ├── X Scanner ──────────────┐
   └── Google News Scanner ────┤
                               ▼
                        Keyword pre-filter
                        + duplicate detection
                               ▼
                        AI Filter Engine
                               ▼
                     Telegram Notification
                     (Approve / Skip / Rewrite)
                               ▼
                        AI Writing Engine
                     (Human Writing System)
                               ▼
                     Finished post delivered
                     to you (never auto-published)
```

---

## Requirements

- Ubuntu 24.04 LTS (recommended) or any modern Linux with Python 3.12+
- A Telegram bot token ([@BotFather](https://t.me/BotFather))
- Your Telegram numeric user ID
- X (Twitter) API v2 credentials (for the X scanner)
- An OpenAI-compatible API key (OpenAI, xAI Grok, Azure, local models, etc.)

---

## Quick Start (Development)

```bash
git clone https://github.com/your-org/ai-content-discovery.git
cd ai-content-discovery

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your real tokens and keys

PYTHONPATH=. python run.py
```

Or use the convenience script:

```bash
./scripts/start.sh
```

---

## Production Installation (Ubuntu 24.04)

```bash
# 1. Clone the repository
sudo git clone https://github.com/your-org/ai-content-discovery.git /opt/ai-content-discovery
cd /opt/ai-content-discovery

# 2. Run the installer (creates user, venv, systemd service)
sudo ./scripts/install.sh

# 3. Configure secrets
sudo nano /opt/ai-content-discovery/.env

# 4. Start the service
sudo systemctl start ai-content-discovery
sudo systemctl status ai-content-discovery

# 5. Follow the logs
sudo journalctl -u ai-content-discovery -f
```

The installer will:
- Install system packages (Python 3.12, build tools, etc.)
- Create a dedicated system user `aicontent`
- Create a virtual environment and install Python dependencies
- Install and enable a systemd service with automatic restart
- Apply basic hardening (NoNewPrivileges, ProtectSystem, etc.)

### Updating

```bash
sudo ./scripts/update.sh
```

---

## Configuration

All configuration is done through environment variables (see `.env.example`).

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes |
| `TELEGRAM_ALLOWED_USER_IDS` | Comma-separated Telegram user IDs | Yes |
| `X_BEARER_TOKEN` / `X_API_KEY` / … | X API v2 credentials | For X scanner |
| `AI_API_KEY` | OpenAI-compatible API key | Yes |
| `AI_BASE_URL` | API base URL (default OpenAI) | No |
| `AI_MODEL_FILTER` | Model for relevance filtering | No |
| `AI_MODEL_WRITER` | Model for post generation | No |
| `NICHE_KEYWORDS` | Comma-separated niche topics | Yes |
| `SCAN_INTERVAL_MINUTES` | How often to scan (default 30) | No |
| `ENABLE_X_SCANNER` | `true` / `false` | No |
| `ENABLE_NEWS_SCANNER` | `true` / `false` | No |
| `ENABLE_AI_FILTER` | `true` / `false` | No |

---

## Telegram Setup

1. Talk to [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. Get your numeric user ID from [@userinfobot](https://t.me/userinfobot).
3. Put both values in `.env`.
4. Start the application and send `/start` to your bot.

Only users listed in `TELEGRAM_ALLOWED_USER_IDS` can interact with the bot.

---

## X API Setup

1. Create a project and app in the [X Developer Portal](https://developer.x.com/).
2. Generate a Bearer Token and (for trends) user-context tokens.
3. Add them to `.env`.

Recent search works on most access levels. Trends may require elevated access.

---

## Google News Configuration

No API key is required. The scanner uses public Google News RSS feeds.

Control language and country with:

```
NEWS_LANGUAGE=en
NEWS_COUNTRY=US
```

---

## Project Structure

```
ai-content-discovery/
├── src/
│   ├── ai/                 # Filter + Writing engines
│   ├── bot/                # Telegram bot (handlers, keyboards, store)
│   ├── config/             # Settings and constants
│   ├── notifications/      # Telegram notifier
│   ├── scanners/           # X and Google News scanners
│   ├── scheduler/          # APScheduler jobs
│   ├── utils/              # Helpers, logging, text cleanup
│   └── main.py             # Application entry point
├── scripts/
│   ├── install.sh          # Ubuntu 24.04 installer
│   ├── update.sh           # Update script
│   ├── start.sh            # Development launcher
│   └── smoke_test.py       # Offline integration test
├── systemd/                # Reference systemd unit
├── logs/                   # Runtime logs (gitignored)
├── data/                   # Runtime data (gitignored)
├── .env.example
├── requirements.txt
├── LICENSE
├── README.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── CHANGELOG.md
```

---

## Usage

| Command | Description |
|---------|-------------|
| `/start` | Welcome + main menu |
| `/status` | Current status and pending count |
| `/niche` | Show configured niche keywords |
| `/scan` | Manually run X + Google News scan + AI filter |
| `/scan_news` | Manually run only Google News scan |
| `/demo` | Send a sample opportunity card (for testing buttons) |
| `/help` | Show help |

When an opportunity arrives:

1. Read the card.
2. Press **✅ Approve** → the writing engine generates a post/thread + optional image prompt.
3. Or press **❌ Skip** to discard it.
4. Or press **🔄 Rewrite Angle** to get a new suggested angle and decide again.

Copy the generated text and post it yourself. The assistant never posts on your behalf.

---

## Human Writing System

Every AI-generated post is forced to follow a strict set of rules that eliminate typical AI writing patterns:

- Natural rhythm (mixed sentence lengths)
- No em dashes
- No clichés (“game changer”, “pivotal moment”, “tapestry”, …)
- No vague attribution (“experts say”)
- Simple, direct language
- Preserve all facts, names, numbers and quotes
- Occasional natural imperfections allowed

A final deterministic cleanup pass enforces the most important rules even if the model slips.

---

## Troubleshooting

| Problem | Possible solution |
|---------|-------------------|
| Bot does not respond | Check `TELEGRAM_BOT_TOKEN` and that your user ID is in `TELEGRAM_ALLOWED_USER_IDS` |
| “X scanner not ready” | Verify all `X_*` credentials and that the app has the required access level |
| No Google News results | Check outbound network access; the sandbox/firewall may block RSS |
| AI filter / writer errors | Verify `AI_API_KEY` and `AI_BASE_URL`; check provider status |
| Service fails to start | `sudo journalctl -u ai-content-discovery -n 50` |
| Permission errors on logs/data | Ensure the `aicontent` user owns `/opt/ai-content-discovery` |

Run the offline smoke test at any time:

```bash
PYTHONPATH=. python scripts/smoke_test.py
```

---

## FAQ

**Does the bot post to X automatically?**  
No. It only generates the text and sends it to you. You decide whether and when to post.

**Can I use a local LLM?**  
Yes. Point `AI_BASE_URL` and `AI_API_KEY` at any OpenAI-compatible endpoint (Ollama, vLLM, LM Studio, etc.).

**Can I add more sources?**  
Yes. Implement the `BaseScanner` interface and register a new job in the scheduler.

**Is my data stored?**  
Opportunities are kept in an in-memory store for the lifetime of the process. No external database is required for the current version.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Security

See [SECURITY.md](SECURITY.md).

## License

This project is licensed under the MIT License – see [LICENSE](LICENSE) for details.

## Credits

Built as a production-quality open-source tool for independent creators and teams who want AI assistance without giving up control.
