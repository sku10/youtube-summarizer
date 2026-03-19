# YouTube Summarizer

## Project Overview
Standalone, publicly distributable Python package for fetching YouTube transcripts and summarizing them with local (Ollama) or cloud LLMs. Designed so anyone can `git clone` and get running.

Originally extracted from private `youtube-helper` + `youtube-info-store` projects in `~/development/`.

## Architecture

### Two access modes from same codebase
1. **Standalone** — `yt-summarize --serve` opens Flask GUI on localhost. User pastes URLs, gets summaries, browses history.
2. **Agentic** — same Flask server exposes clean REST API (`/api/*`). Any agent or dashboard framework can integrate.

### Package structure
```
youtube-summarizer/
├── pyproject.toml
├── .env.example
├── .gitignore
├── CLAUDE.md
├── src/
│   └── youtube_summarizer/
│       ├── __init__.py
│       ├── transcript.py      # fetch transcript via youtube-transcript-api
│       ├── metadata.py        # fetch metadata via yt-dlp (optional dep)
│       ├── llm.py             # LLM abstraction: ollama, gemini, groq, openrouter
│       ├── storage.py         # JSON file storage in data/videos/<video_id>/
│       ├── prompts.py         # default prompts (exec summary, key points, custom)
│       ├── setup_wizard.py    # interactive onboarding wizard
│       ├── cli.py             # CLI entry point (yt-summarize)
│       └── app.py             # Flask dashboard + REST API
└── data/                      # gitignored, auto-created
    └── videos/<video_id>/
        ├── metadata.json
        ├── transcript.json
        └── summaries.json
```

### Dependencies
- **Required**: youtube-transcript-api, flask, python-dotenv
- **Optional**: yt-dlp (for video metadata like title, channel, duration)
- **LLM**: Ollama (local) or cloud APIs (Gemini, Groq, OpenRouter) via stdlib urllib
- **Storage**: JSON files (no DB driver needed)
- Python >=3.10

### LLM Providers
| Provider | Free Tier | Default Model | Key URL |
|----------|-----------|---------------|---------|
| Ollama | Local, free | qwen3.5:9b | N/A |
| Google Gemini | 15 RPM, 1M TPD | gemini-2.0-flash | aistudio.google.com/apikey |
| Groq | 30 RPM, 14.4K/day | llama-3.3-70b-versatile | console.groq.com/keys |
| OpenRouter | Some free models | google/gemini-2.0-flash-exp:free | openrouter.ai/keys |

### API Endpoints
```
GET  /                          # Web dashboard
GET  /api/health                # Status: provider, model, ollama state
GET  /api/videos                # List all stored videos
GET  /api/videos/<id>           # Video + transcript + summaries
POST /api/summarize             # {url, prompt_type?, user_prompt?, languages?, no_llm?}
POST /api/ask                   # {video_id, prompt} — follow-up question
GET  /api/search?q=             # Full-text search across transcripts
```

### CLI
```
yt-summarize <url>                      # executive summary (default)
yt-summarize <url> --prompt key_points  # key points
yt-summarize <url> --ask "..."          # custom question
yt-summarize <url> --no-llm             # fetch only, no summarization
yt-summarize --serve                    # start web dashboard (port 5100)
yt-summarize --setup                    # interactive setup wizard
yt-summarize --list                     # list stored videos
```

### Setup Wizard (`yt-summarize --setup`)
Interactive onboarding that:
- Shows checklist with ✓/✗ for each requirement
- Detects Python, deps, Ollama, GPU, API keys
- Proposes fix commands and runs them on user approval
- Tests LLM connections
- Writes .env config
- Novice-friendly: every failing check shows inline fix

## Build Status
- [x] Project structure created
- [x] pyproject.toml, .gitignore, .env.example
- [x] transcript.py — fetch transcripts
- [x] metadata.py — fetch metadata (yt-dlp optional)
- [x] storage.py — JSON file storage
- [x] prompts.py — default prompts
- [x] llm.py — multi-provider LLM abstraction
- [x] setup_wizard.py — interactive onboarding wizard
- [x] cli.py — CLI entry point
- [x] app.py — Flask dashboard + REST API
- [x] Create venv and install deps (use venv, never --break-system-packages)
- [ ] Test setup wizard
- [x] Test end-to-end: URL → transcript → summary
- [x] Test web dashboard
- [ ] README.md for public distribution

## Rules
- ALWAYS use virtual environments. NEVER use --break-system-packages.
- Keep dependencies minimal — stdlib urllib for HTTP, no httpx/requests.
- yt-dlp is optional, graceful fallback when missing.
