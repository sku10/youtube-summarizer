# YouTube Summarizer

Fetch YouTube transcripts and summarize them with local (Ollama) or cloud LLMs.

Works as a **CLI tool**, **web dashboard**, or **REST API** for AI agent integration.

## Quick Start

```bash
git clone https://github.com/sku10/youtube-summarizer.git
cd youtube-summarizer
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[metadata]"
yt-summarize --setup
```

The setup wizard detects your system, installs Ollama if needed, checks for GPU, configures LLM providers (local or cloud), and writes your `.env`.

## CLI Usage

```bash
yt-summarize <url>                              # executive summary (default)
yt-summarize <url> --prompt key_points          # key points extraction
yt-summarize <url> --ask "What tools mentioned?" # custom question
yt-summarize <url> --no-llm                     # fetch transcript only, skip LLM
yt-summarize <url> --model qwen3.5:cloud        # use specific model
yt-summarize <url> --provider gemini            # use specific provider
yt-summarize <url> -l en,fi                     # prefer specific transcript languages
yt-summarize --serve                            # start web dashboard on port 5100
yt-summarize --serve --port 8080                # custom port
yt-summarize --setup                            # interactive setup wizard
yt-summarize --list                             # list all stored videos
```

## Web Dashboard

```bash
yt-summarize --serve
```

Opens at http://localhost:5100. Features:
- Paste or drag & drop YouTube URLs
- Model selector (auto-populated from available models, cloud first)
- Editable prompt templates with save/recall
- Summary, transcript, history, and search tabs
- Follow-up questions about any video

## REST API (for AI agents)

Start the server, then any agent can call it:

```bash
# Summarize a video
curl -X POST http://localhost:5100/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'

# Ask a follow-up question
curl -X POST http://localhost:5100/api/ask \
  -H "Content-Type: application/json" \
  -d '{"video_id": "VIDEO_ID", "prompt": "What were the key recommendations?"}'

# Search across all stored transcripts
curl "http://localhost:5100/api/search?q=machine+learning"
```

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Status, provider, model, available models list |
| GET | `/api/videos` | List all stored videos |
| GET | `/api/videos/<id>` | Full video data: metadata + transcript + summaries |
| POST | `/api/summarize` | Fetch transcript and summarize. Body: `{url, prompt_type?, prompt_key?, user_prompt?, model?, no_llm?}` |
| POST | `/api/ask` | Follow-up question. Body: `{video_id, prompt, model?}` |
| GET | `/api/search?q=` | Full-text search across transcripts |
| GET | `/api/prompts` | List saved prompts (sorted by most used) |
| POST | `/api/prompts` | Save/update a prompt. Body: `{title, text, key?}` |
| DELETE | `/api/prompts/<key>` | Delete a prompt |

Full API documentation with examples, agent integration patterns, and Python code snippets: **[API.md](API.md)**

## LLM Providers

| Provider | Free Tier | Default Model | Get API Key |
|----------|-----------|---------------|-------------|
| **Ollama** (local) | Free, private | auto-detected | [ollama.com](https://ollama.com) |
| **Ollama Cloud** | Free tier | qwen3.5:cloud | [ollama.com/settings/keys](https://ollama.com/settings/keys) |
| **Google Gemini** | 15 RPM, 1M TPD | gemini-2.0-flash | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| **Groq** | 30 RPM, 14.4K/day | llama-3.3-70b-versatile | [console.groq.com/keys](https://console.groq.com/keys) |
| **OpenRouter** | Some free models | gemini-2.0-flash-exp:free | [openrouter.ai/keys](https://openrouter.ai/keys) |

Run `yt-summarize --setup` to configure any of these interactively.

## Configuration

All config lives in `.env` (created by setup wizard or manually). Key variables:

```bash
LLM_PROVIDER=ollama              # or gemini, groq, openrouter
OLLAMA_URL=http://localhost:11434 # or https://ollama.com for cloud
OLLAMA_MODEL=qwen3.5:9b          # auto-detected if not set
OLLAMA_API_KEY=                   # only for Ollama cloud
GEMINI_API_KEY=                   # Google Gemini
YOUTUBE_PROXY=                    # proxy for YouTube if IP blocked
```

See `.env.example` for all options.

## Storage

All data stored as JSON files in `data/` (gitignored):

```
data/
├── prompts.json                  # saved prompt templates
└── videos/<video_id>/
    ├── metadata.json             # title, channel, duration, etc.
    ├── transcript.json           # segments + full text
    └── summaries.json            # all summaries for this video
```

No database required. Files are human-readable and trivially inspectable.

## Requirements

- Python 3.10+
- At least one LLM provider (local Ollama, Ollama cloud, or a free cloud API key)
- Optional: yt-dlp (for video metadata — installed with `pip install -e ".[metadata]"`)

## License

MIT
