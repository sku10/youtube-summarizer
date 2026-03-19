# YouTube Summarizer — API Reference

Base URL: `http://localhost:5100` (default)

Start the server: `yt-summarize --serve` or `yt-summarize --serve --port 8080`

All endpoints return JSON. POST endpoints accept `Content-Type: application/json`.

---

## Quick Start for AI Agents

An agent can summarize any YouTube video in a single HTTP call:

```bash
curl -X POST http://localhost:5100/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'
```

Response includes `video_id`, `title`, `summary`, `model`, `transcript_text` (first 2000 chars).

To ask follow-up questions about the same video:

```bash
curl -X POST http://localhost:5100/api/ask \
  -H "Content-Type: application/json" \
  -d '{"video_id": "VIDEO_ID", "prompt": "What tools are mentioned?"}'
```

---

## Endpoints

### GET /api/health

System status. Use this to discover available models and current config.

**Response:**
```json
{
  "status": "ok",
  "provider": "ollama",
  "model": "qwen3.5:cloud",
  "ollama_running": true,
  "ollama_models": 40,
  "available_models": ["qwen3.5:cloud", "qwen3.5:9b", "llama3.1:latest", "..."]
}
```

### GET /api/videos

List all previously processed videos.

**Response:**
```json
[
  {
    "video_id": "dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up",
    "channel": "Rick Astley",
    "duration": 213,
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "has_transcript": true,
    "summary_count": 2,
    "saved_at": "2026-03-19T17:16:57Z"
  }
]
```

### GET /api/videos/\<video_id\>

Full data for a single video: metadata, transcript, and all summaries.

**Response:**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "metadata": { "title": "...", "channel": "...", "duration": 213 },
  "transcript": {
    "segment_count": 61,
    "text": "full transcript text...",
    "segments": [{"text": "...", "start": 0.0, "duration": 3.2}]
  },
  "summaries": [
    {
      "prompt_type": "executive_summary",
      "model": "qwen3.5:cloud",
      "response": "summary text...",
      "created_at": "2026-03-19T17:17:30Z"
    }
  ]
}
```

### POST /api/summarize

Fetch transcript, optionally summarize with LLM. This is the main endpoint.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | yes | YouTube URL or video ID |
| `languages` | string[] | no | Preferred transcript languages, e.g. `["en", "fi"]` |
| `prompt_type` | string | no | `"executive_summary"` (default), `"key_points"`, or `"custom"` |
| `prompt_key` | string | no | Key of a saved prompt (from `/api/prompts`) |
| `user_prompt` | string | no | Custom prompt text (used when prompt_type is `"custom"` or as override) |
| `no_llm` | bool | no | If `true`, fetch and store transcript only, skip LLM |
| `provider` | string | no | Override LLM provider: `"ollama"`, `"gemini"`, `"groq"`, `"openrouter"` |
| `model` | string | no | Override model name, e.g. `"qwen3.5:cloud"` |

**Examples:**

```bash
# Executive summary (default)
curl -X POST http://localhost:5100/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'

# Key points with specific model
curl -X POST http://localhost:5100/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"url": "VIDEO_ID", "prompt_type": "key_points", "model": "qwen3.5:9b"}'

# Custom question
curl -X POST http://localhost:5100/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"url": "VIDEO_ID", "prompt_type": "custom", "user_prompt": "List all products mentioned"}'

# Fetch transcript only, no LLM
curl -X POST http://localhost:5100/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"url": "VIDEO_ID", "no_llm": true}'

# Use a saved prompt by key
curl -X POST http://localhost:5100/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"url": "VIDEO_ID", "prompt_key": "executive_summary"}'
```

**Response (200):**
```json
{
  "video_id": "VIDEO_ID",
  "title": "Video Title",
  "transcript_length": 698,
  "transcript_text": "first 2000 chars of transcript...",
  "provider": "ollama",
  "model": "qwen3.5:cloud",
  "prompt_type": "executive_summary",
  "summary": "The full LLM summary text..."
}
```

**Error responses:** `400` (bad input), `422` (transcript unavailable), `502` (LLM error)

### POST /api/ask

Ask a follow-up question about a previously processed video.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `video_id` | string | yes | Video ID from a previous summarize call |
| `prompt` | string | yes | Your question |
| `provider` | string | no | Override provider |
| `model` | string | no | Override model |

**Example:**
```bash
curl -X POST http://localhost:5100/api/ask \
  -H "Content-Type: application/json" \
  -d '{"video_id": "VIDEO_ID", "prompt": "What were the three main recommendations?"}'
```

**Response:**
```json
{
  "video_id": "VIDEO_ID",
  "prompt": "What were the three main recommendations?",
  "response": "The three main recommendations were...",
  "model": "qwen3.5:cloud"
}
```

### GET /api/search?q=\<query\>

Full-text search across all stored transcripts.

**Example:**
```bash
curl "http://localhost:5100/api/search?q=machine+learning"
```

**Response:** Array of matching video metadata objects.

### GET /api/prompts

List all saved prompts, sorted by most used (default) or newest.

**Query params:** `sort=most_used` (default) or `sort=newest`

**Response:**
```json
[
  {
    "key": "executive_summary",
    "title": "Executive Summary",
    "text": "Provide an executive summary of this video transcript...",
    "created_at": "2026-03-19T17:00:00Z",
    "last_used": "2026-03-19T20:30:00Z",
    "use_count": 15
  }
]
```

### POST /api/prompts

Save or update a prompt.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | yes | The prompt text |
| `title` | string | no | Display title (defaults to first 50 chars of text) |
| `key` | string | no | Prompt key (auto-generated with timestamp if omitted) |

**Example:**
```bash
curl -X POST http://localhost:5100/api/prompts \
  -H "Content-Type: application/json" \
  -d '{"title": "Finnish Summary", "text": "Summarize this video in Finnish. Keep it under 200 words."}'
```

### DELETE /api/prompts/\<key\>

Delete a saved prompt.

---

## Agent Integration Patterns

### Pattern 1: One-shot summarize
```python
import urllib.request, json

def summarize_video(url, prompt="executive_summary"):
    req = urllib.request.Request(
        "http://localhost:5100/api/summarize",
        data=json.dumps({"url": url, "prompt_type": prompt}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())
```

### Pattern 2: Fetch first, ask multiple questions
```python
# Step 1: Fetch transcript (no LLM cost)
data = post("/api/summarize", {"url": url, "no_llm": True})
video_id = data["video_id"]

# Step 2: Ask specific questions
q1 = post("/api/ask", {"video_id": video_id, "prompt": "What tools are mentioned?"})
q2 = post("/api/ask", {"video_id": video_id, "prompt": "Summarize in 3 bullet points"})
```

### Pattern 3: Batch processing with search
```python
# Summarize several videos
for url in video_urls:
    post("/api/summarize", {"url": url})

# Later, search across all transcripts
results = get("/api/search?q=kubernetes")
```

### Pattern 4: Use custom prompts
```python
# Create a reusable prompt
post("/api/prompts", {
    "title": "Product Mentions",
    "text": "List every product, tool, or service mentioned in this video with a one-line description of each."
})

# Use it by key
post("/api/summarize", {"url": url, "prompt_key": "product_mentions_20260319_220000"})
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | Active provider: `ollama`, `gemini`, `groq`, `openrouter` |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API URL. Set to `https://ollama.com` for cloud |
| `OLLAMA_MODEL` | auto-detected | Model name. Cloud example: `qwen3.5:cloud` |
| `OLLAMA_API_KEY` | — | API key for Ollama cloud |
| `OLLAMA_NUM_CTX` | auto | Context window size override |
| `OLLAMA_TIMEOUT` | `600` | Request timeout in seconds |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `GROQ_API_KEY` | — | Groq API key |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `YOUTUBE_PROXY` | — | Proxy URL for YouTube requests |
| `YT_SUMMARIZER_DATA_DIR` | `./data` | Storage directory |

All configured via `.env` file or `yt-summarize --setup`.
