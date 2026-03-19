# YouTube Summarizer

Fetch YouTube transcripts and summarize them with local (Ollama) or cloud LLMs.

Works as a **CLI tool**, **web dashboard**, or **REST API** for agent integration.

## Quick Start

```bash
git clone https://github.com/sku10/youtube-summarizer.git
cd youtube-summarizer
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[metadata]"
yt-summarize --setup
```

The setup wizard detects your system, installs what's missing, and configures LLM providers.

## Usage

### CLI

```bash
yt-summarize https://youtu.be/VIDEO_ID                # executive summary
yt-summarize VIDEO_ID --prompt key_points              # key points
yt-summarize VIDEO_ID --ask "What tools are mentioned?" # custom question
yt-summarize VIDEO_ID --no-llm                         # fetch transcript only
yt-summarize VIDEO_ID --provider gemini                # use specific provider
yt-summarize --serve                                   # start web dashboard
yt-summarize --list                                    # list stored videos
```

### Web Dashboard

```bash
yt-summarize --serve
```

Opens at http://localhost:5100 — paste URLs, get summaries, browse history.

### REST API

The same server exposes a JSON API for agent integration:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Status: provider, model, ollama state |
| GET | `/api/videos` | List all stored videos |
| GET | `/api/videos/<id>` | Video + transcript + summaries |
| POST | `/api/summarize` | `{url, prompt_type?, user_prompt?}` |
| POST | `/api/ask` | `{video_id, prompt}` — follow-up question |
| GET | `/api/search?q=` | Full-text search across transcripts |

## LLM Providers

| Provider | Free Tier | Default Model | Get API Key |
|----------|-----------|---------------|-------------|
| **Ollama** | Local, free | qwen3.5:9b | [ollama.com](https://ollama.com) |
| **Google Gemini** | 15 RPM, 1M TPD | gemini-2.0-flash | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| **Groq** | 30 RPM, 14.4K/day | llama-3.3-70b-versatile | [console.groq.com/keys](https://console.groq.com/keys) |
| **OpenRouter** | Some free models | gemini-2.0-flash-exp:free | [openrouter.ai/keys](https://openrouter.ai/keys) |

Run `yt-summarize --setup` to configure any of these interactively.

## Requirements

- Python 3.10+
- At least one LLM provider (Ollama for local, or a free cloud API key)

## Storage

Transcripts and summaries are stored as JSON files in `data/videos/<video_id>/`. No database needed.

## License

MIT
