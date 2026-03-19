# YouTube Summarizer — Autonomous Agent Setup Guide

This document provides step-by-step instructions for an AI agent to fully install, configure, and validate the YouTube Summarizer package on a user's machine without human intervention (except for approvals and API key input).

## Phase 1: Discovery & Prerequisites

### 1.1 Clone the repository
```bash
git clone https://github.com/sku10/youtube-summarizer.git
cd youtube-summarizer
```

### 1.2 Check Python version
```bash
python3 --version
```
Requires Python 3.10+. If not available, install it first.

### 1.3 Create virtual environment and install
```bash
python3 -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows
pip install -e ".[metadata]"
```
IMPORTANT: Always use a virtual environment. Never use `--break-system-packages`.

### 1.4 Verify installation
```bash
yt-summarize --help
```
Should show all CLI options.

## Phase 2: Hardware Assessment

### 2.1 Check GPU
```bash
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits 2>/dev/null
```

**Interpret results:**
| GPU VRAM | Capability |
|----------|-----------|
| No GPU | CPU-only. Cloud models recommended. Local models will be very slow (minutes per summary). Only suitable for testing or overnight batch jobs. |
| 4-6 GB | Can run qwen3.5:0.8b or qwen3.5:3b locally |
| 8 GB | Can run qwen3.5:9b (recommended local model) |
| 16+ GB | Can run qwen3.5:27b or larger |
| 24+ GB | Can run most models comfortably |

### 2.2 Check CPU and RAM
```bash
# CPU
grep "model name" /proc/cpuinfo | head -1 | cut -d: -f2
nproc

# RAM
free -h | grep Mem | awk '{print "Total:", $2, "Available:", $7}'
```

For CPU-only inference: expect 1-5 minutes per summary depending on model size and transcript length. Set `OLLAMA_TIMEOUT=900` in `.env` for safety.

### 2.3 Check disk space
```bash
df -h . | tail -1 | awk '{print "Available:", $4}'
```
Models need 1-70 GB depending on size. Cloud models need no disk space.

## Phase 3: Ollama Setup

### 3.1 Check if Ollama is installed
```bash
ollama --version 2>/dev/null
```

### 3.2 Install Ollama (if missing)
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 3.3 Check latest version
```bash
curl -s https://api.github.com/repos/ollama/ollama/releases/latest | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])"
```
Compare with installed version. Update if outdated (same install command).

### 3.4 Start Ollama
```bash
# Check if running
curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && echo "running" || echo "not running"

# Start if needed
ollama serve &>/dev/null &
sleep 3
```

### 3.5 List available models
```bash
ollama list
```

### 3.6 Pull a model (if none available)

Choose based on GPU assessment:
```bash
# No GPU or small GPU — use cloud instead (see Phase 4)
# 8 GB GPU:
ollama pull qwen3.5:9b
# 4-6 GB GPU:
ollama pull qwen3.5:3b
# Testing only (tiny, fast):
ollama pull qwen3.5:0.8b
```

## Phase 4: Provider Configuration

### 4.1 Assess what's available

Run all checks in parallel:
```bash
# Local Ollama models
curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c "import sys,json; models=json.load(sys.stdin).get('models',[]); print(f'{len(models)} local models'); [print(f'  {m[\"name\"]}') for m in models[:10]]" 2>/dev/null || echo "Ollama not running"

# Check for existing API keys in .env
grep -E "^(GEMINI_API_KEY|GROQ_API_KEY|OPENROUTER_API_KEY|OLLAMA_API_KEY)=" .env 2>/dev/null | sed 's/=.\{4\}/=****/' || echo "No .env file"

# Check environment
echo "GEMINI_API_KEY: ${GEMINI_API_KEY:+set}"
echo "GROQ_API_KEY: ${GROQ_API_KEY:+set}"
echo "OLLAMA_API_KEY: ${OLLAMA_API_KEY:+set}"
```

### 4.2 Decision tree — which provider to use

```
Has GPU with 8+ GB VRAM?
  → YES: Use local Ollama with qwen3.5:9b (private, fast, free)
  → NO:
      Has Ollama account/API key?
        → YES: Use Ollama cloud (qwen3.5:cloud)
      Has Google account?
        → YES: Use Gemini (free tier, fast, easy setup)
                Get key: https://aistudio.google.com/apikey
      Fallback:
        → Groq (free tier): https://console.groq.com/keys
        → OpenRouter (some free models): https://openrouter.ai/keys
```

### 4.3 Write .env configuration

Create or update `.env` based on chosen provider:

**Option A: Local Ollama (has GPU)**
```bash
cat > .env << 'EOF'
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.5:9b
EOF
```

**Option B: Ollama Cloud (no GPU, has Ollama key)**
```bash
cat > .env << 'EOF'
LLM_PROVIDER=ollama
OLLAMA_URL=https://ollama.com
OLLAMA_API_KEY=<key from https://ollama.com/settings/keys>
OLLAMA_MODEL=qwen3.5:cloud
EOF
```

**Option C: Google Gemini (no GPU, has Google account)**
```bash
cat > .env << 'EOF'
LLM_PROVIDER=gemini
GEMINI_API_KEY=<key from https://aistudio.google.com/apikey>
EOF
```

**Option D: CPU-only local (testing/overnight)**
```bash
cat > .env << 'EOF'
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.5:0.8b
OLLAMA_NUM_CTX=8192
OLLAMA_TIMEOUT=900
EOF
```

### 4.4 YouTube proxy (optional)

If YouTube blocks the IP (common on cloud VMs):
```bash
echo "YOUTUBE_PROXY=http://proxy-server:8888" >> .env
```

## Phase 5: Validation

### 5.1 Test transcript fetch (no LLM)
```bash
source .venv/bin/activate
yt-summarize "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --no-llm
```
Expected: "Transcript: 61 segments, 2089 chars" and "Transcript saved."

If this fails with IP blocked error → need proxy or different network.

### 5.2 Test LLM connection
```bash
yt-summarize "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```
Expected: Executive summary of Rick Astley - Never Gonna Give You Up.

If timeout on CPU → increase `OLLAMA_TIMEOUT` or switch to cloud provider.

### 5.3 Test web dashboard
```bash
yt-summarize --serve &
sleep 2
curl -s http://localhost:5100/api/health | python3 -m json.tool
```
Expected: JSON with `"status": "ok"`, provider, model, available_models.

### 5.4 Test API endpoint
```bash
curl -s -X POST http://localhost:5100/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"url": "dQw4w9WgXcQ", "no_llm": true}' | python3 -m json.tool
```
Expected: JSON with video_id, title, transcript_length.

### 5.5 Verify stored data
```bash
ls data/videos/
cat data/videos/dQw4w9WgXcQ/metadata.json | python3 -m json.tool
```

## Phase 6: Report

After setup, report to the user:

```
YouTube Summarizer — Setup Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Provider:  ollama (qwen3.5:cloud)
GPU:       NVIDIA RTX 3060 Ti (8 GB)
Storage:   ./data/
Dashboard: yt-summarize --serve → http://localhost:5100

Quick test:
  yt-summarize <youtube-url>           # summarize a video
  yt-summarize <youtube-url> --ask "?" # ask a question
  yt-summarize --serve                 # web dashboard

API docs: see API.md
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `pip install` fails with system packages error | Use venv: `python3 -m venv .venv && source .venv/bin/activate` |
| Ollama `model not found` | Run `ollama list` to see available models, use `--model <name>` |
| Ollama version mismatch warning | `curl -fsSL https://ollama.com/install.sh \| sh` then `sudo systemctl restart ollama` |
| YouTube IP blocked | Set `YOUTUBE_PROXY` in `.env` or use a different network |
| Timeout on CPU | Set `OLLAMA_TIMEOUT=900` in `.env` or use cloud provider |
| Context too small (truncated output) | Set `OLLAMA_NUM_CTX=16384` in `.env` |
| `ollama serve` hangs terminal | Use `ollama serve &>/dev/null &` |
| Port 5100 already in use | `yt-summarize --serve --port 8080` |
