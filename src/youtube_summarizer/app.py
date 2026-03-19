"""Flask web dashboard and REST API."""

import json
import traceback

from flask import Flask, jsonify, request

from .llm import chat, get_model, get_provider, list_ollama_models, ollama_is_running
from .metadata import fetch_metadata
from .prompts import build_prompt
from .storage import (
    delete_prompt,
    init_default_prompts,
    list_videos,
    load_metadata,
    load_prompts,
    load_summaries,
    load_transcript,
    record_prompt_use,
    save_metadata,
    save_prompt,
    save_summary,
    save_transcript,
    search_transcripts,
)
from .transcript import fetch_transcript, parse_video_id, transcript_to_text

app = Flask(__name__)
init_default_prompts()

TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YouTube Summarizer</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: Inter, system-ui, -apple-system, sans-serif;
      background: #0d1117; color: #cdd9e5;
      padding: 1.5rem; max-width: 960px; margin: 0 auto;
      line-height: 1.5;
    }
    h1 { margin-bottom: 0.25rem; }
    h1 span { color: #f85149; }
    .subtitle { color: #768390; margin-bottom: 1.5rem; }
    .card {
      background: #161b22; border: 1px solid #30363d;
      border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem;
    }
    label { display: block; color: #768390; font-size: 0.85rem; margin-bottom: 0.25rem; }
    input, select, textarea {
      width: 100%; padding: 0.5rem 0.75rem; font-size: 0.95rem;
      background: #0d1117; color: #cdd9e5; border: 1px solid #30363d;
      border-radius: 6px; margin-bottom: 0.75rem;
    }
    textarea { resize: vertical; min-height: 120px; font-family: inherit; font-size: 0.85rem; }
    button {
      padding: 0.5rem 1.25rem; font-size: 0.95rem; font-weight: 600;
      border: none; border-radius: 6px; cursor: pointer;
      background: #238636; color: #fff; margin-right: 0.5rem;
    }
    button:hover { background: #2ea043; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    button.secondary { background: #30363d; }
    button.secondary:hover { background: #484f58; }
    .row { display: flex; gap: 0.75rem; }
    .row > * { flex: 1; }
    .status { padding: 0.75rem; border-radius: 6px; margin: 0.75rem 0; font-size: 0.9rem; }
    .status.ok { background: #0d2818; border: 1px solid #238636; }
    .status.err { background: #2d1117; border: 1px solid #f85149; }
    .status.loading { background: #1c1f24; border: 1px solid #30363d; }
    .result {
      background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
      padding: 1rem; margin-top: 0.75rem; white-space: pre-wrap;
      font-size: 0.9rem; max-height: 500px; overflow-y: auto;
    }
    .video-item {
      padding: 0.5rem 0; border-bottom: 1px solid #21262d;
      display: flex; justify-content: space-between; align-items: center;
      cursor: pointer;
    }
    .video-item:hover { background: #1c2128; }
    .video-item .title { font-weight: 500; }
    .video-item .meta { color: #768390; font-size: 0.8rem; }
    .tabs { display: flex; gap: 0; margin-bottom: -1px; }
    .tab {
      padding: 0.5rem 1rem; background: transparent; color: #768390;
      border: 1px solid transparent; border-bottom: none;
      border-radius: 6px 6px 0 0; cursor: pointer; font-size: 0.9rem;
    }
    .tab.active { background: #161b22; color: #cdd9e5; border-color: #30363d; }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .badge { background: #30363d; padding: 0.1rem 0.5rem; border-radius: 10px; font-size: 0.75rem; }
  </style>
</head>
<body>
  <h1>YouTube <span>Summarizer</span></h1>
  <p class="subtitle">Fetch transcripts, summarize with LLMs, search your history</p>

  <div class="card">
    <label>YouTube URL or Video ID — paste, type, or drag & drop a link</label>
    <input id="urlInput" placeholder="https://www.youtube.com/watch?v=... or video ID">
    <div class="row">
      <div style="flex:2;">
        <label>Prompt</label>
        <select id="promptType"><option>loading...</option></select>
      </div>
      <div>
        <label>Model</label>
        <select id="modelInput"><option>loading...</option></select>
      </div>
      <div>
        <label>Languages (optional)</label>
        <input id="langInput" placeholder="en,fi">
      </div>
    </div>
    <div id="promptEditor">
      <label>Prompt text <span style="color:#768390;font-size:0.8rem;">(edit to customize, then save)</span></label>
      <textarea id="promptText" rows="4" placeholder="Enter your prompt..."></textarea>
      <div class="row" style="align-items:center;">
        <input id="promptTitle" placeholder="Prompt title (optional)" style="margin-bottom:0;">
        <button class="secondary" onclick="saveCurrentPrompt()" style="flex:none;margin-bottom:0;">Save Prompt</button>
      </div>
    </div>
    <div style="margin-top:0.75rem;">
      <button onclick="summarize()" id="goBtn">Summarize</button>
      <button class="secondary" onclick="fetchOnly()">Fetch Only (no LLM)</button>
    </div>
    <div id="status"></div>
  </div>

  <div class="tabs">
    <div class="tab active" onclick="showTab('summary')">Summary</div>
    <div class="tab" onclick="showTab('transcript')">Transcript</div>
    <div class="tab" onclick="showTab('history')">History <span class="badge" id="histCount">0</span></div>
    <div class="tab" onclick="showTab('search')">Search</div>
  </div>

  <div class="card" style="border-top-left-radius: 0;">
    <div id="tab-summary" class="tab-content active">
      <div class="result" id="summaryResult">Submit a video to get started.</div>
    </div>
    <div id="tab-transcript" class="tab-content">
      <div class="result" id="transcriptResult">No transcript loaded.</div>
    </div>
    <div id="tab-history" class="tab-content">
      <div id="historyList">Loading...</div>
    </div>
    <div id="tab-search" class="tab-content">
      <input id="searchInput" placeholder="Search across all transcripts...">
      <button onclick="doSearch()" class="secondary" style="margin-top:0.5rem;">Search</button>
      <div class="result" id="searchResult">Enter a query above.</div>
    </div>
  </div>

  <div class="card">
    <label>Ask follow-up about current video</label>
    <div class="row">
      <input id="followupInput" placeholder="What else would you like to know?">
      <button onclick="askFollowup()" style="flex:none;">Ask</button>
    </div>
    <div class="result" id="followupResult" style="display:none;"></div>
  </div>

<script>
const $ = id => document.getElementById(id);
let currentVideoId = null;

// Drag & drop URL support — works on the whole page
document.addEventListener('dragover', e => {
  e.preventDefault();
  $('urlInput').style.borderColor = '#238636';
  $('urlInput').style.boxShadow = '0 0 8px rgba(35,134,54,0.5)';
});
document.addEventListener('dragleave', e => {
  $('urlInput').style.borderColor = '#30363d';
  $('urlInput').style.boxShadow = 'none';
});
document.addEventListener('drop', e => {
  e.preventDefault();
  $('urlInput').style.borderColor = '#30363d';
  $('urlInput').style.boxShadow = 'none';
  const text = (e.dataTransfer.getData('text/uri-list') || e.dataTransfer.getData('text/plain') || '').trim();
  if (text && (text.includes('youtube.com') || text.includes('youtu.be'))) {
    $('urlInput').value = text.split('\\n')[0].trim();
    $('urlInput').focus();
  }
});

let allPrompts = [];

async function loadPrompts() {
  try {
    const resp = await fetch('/api/prompts?sort=most_used');
    allPrompts = await resp.json();
    const sel = $('promptType');
    sel.innerHTML = '';
    // Add "Custom" option first
    const custom = document.createElement('option');
    custom.value = '__custom__'; custom.textContent = '— Custom / New —';
    sel.appendChild(custom);
    // Add saved prompts
    allPrompts.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.key;
      opt.textContent = p.title + (p.use_count ? ' (' + p.use_count + 'x)' : '');
      sel.appendChild(opt);
    });
    // Select first saved prompt by default if available
    if (allPrompts.length) {
      sel.value = allPrompts[0].key;
      onPromptChange();
    }
  } catch(e) { console.error('loadPrompts:', e); }
}

function onPromptChange() {
  const key = $('promptType').value;
  if (key === '__custom__') {
    $('promptText').value = '';
    $('promptTitle').value = '';
    return;
  }
  const p = allPrompts.find(x => x.key === key);
  if (p) {
    $('promptText').value = p.text;
    $('promptTitle').value = p.title;
  }
}

$('promptType').onchange = onPromptChange;

async function saveCurrentPrompt() {
  const text = $('promptText').value.trim();
  if (!text) return;
  const title = $('promptTitle').value.trim() || text.slice(0, 50);
  const currentKey = $('promptType').value;
  const body = {text, title};
  // If editing an existing prompt, keep the key
  if (currentKey !== '__custom__') body.key = currentKey;
  try {
    const resp = await fetch('/api/prompts', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    const data = await resp.json();
    await loadPrompts();
    $('promptType').value = data.key;
    setStatus('Prompt saved: ' + title, 'ok');
  } catch(e) {
    setStatus('Failed to save prompt', 'err');
  }
}

function showTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  $('tab-' + name).classList.add('active');
  event.target.classList.add('active');
}

function setStatus(msg, type) {
  const el = $('status');
  el.className = 'status ' + type;
  el.textContent = msg;
}

async function summarize() {
  const url = $('urlInput').value.trim();
  if (!url) { setStatus('Enter a URL or video ID.', 'err'); return; }
  const langs = $('langInput').value.split(',').map(s => s.trim()).filter(Boolean);
  const promptKey = $('promptType').value;
  const promptText = $('promptText').value.trim();

  $('goBtn').disabled = true;
  setStatus('Fetching transcript and summarizing...', 'loading');

  const body = {url, languages: langs, model: $('modelInput').value.trim() || undefined};
  if (promptKey !== '__custom__') {
    body.prompt_key = promptKey;
  }
  if (promptText) {
    body.user_prompt = promptText;
    body.prompt_type = 'custom';
  }

  try {
    const resp = await fetch('/api/summarize', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    const data = await resp.json();
    if (!resp.ok) { setStatus(data.error || 'Failed', 'err'); return; }

    currentVideoId = data.video_id;
    setStatus(
      (data.title ? data.title + ' — ' : '') +
      (data.channel ? data.channel + ' · ' : '') + 'Summarized with ' + data.model, 'ok'
    );
    $('summaryResult').textContent = data.summary;
    if (data.transcript_text) {
      $('transcriptResult').textContent = data.transcript_text;
    }
    refreshHistory();
  } catch(e) {
    setStatus('Network error: ' + e.message, 'err');
  } finally {
    $('goBtn').disabled = false;
  }
}

async function fetchOnly() {
  const url = $('urlInput').value.trim();
  if (!url) { setStatus('Enter a URL or video ID.', 'err'); return; }
  const langs = $('langInput').value.split(',').map(s => s.trim()).filter(Boolean);

  setStatus('Fetching transcript...', 'loading');
  try {
    const resp = await fetch('/api/summarize', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url, languages: langs, no_llm: true})
    });
    const data = await resp.json();
    if (!resp.ok) { setStatus(data.error || 'Failed', 'err'); return; }

    currentVideoId = data.video_id;
    setStatus((data.title ? data.title + ' — ' : '') + 'Transcript saved', 'ok');
    $('summaryResult').textContent = 'No LLM summary (fetch only mode).';
    if (data.transcript_text) {
      $('transcriptResult').textContent = data.transcript_text;
    }
    refreshHistory();
  } catch(e) {
    setStatus('Network error: ' + e.message, 'err');
  }
}

async function askFollowup() {
  if (!currentVideoId) { setStatus('Summarize a video first.', 'err'); return; }
  const prompt = $('followupInput').value.trim();
  if (!prompt) return;

  $('followupResult').style.display = '';
  $('followupResult').textContent = 'Thinking...';
  try {
    const resp = await fetch('/api/ask', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({video_id: currentVideoId, prompt, model: $('modelInput').value.trim() || undefined})
    });
    const data = await resp.json();
    $('followupResult').textContent = resp.ok ? data.response : (data.error || 'Failed');
  } catch(e) {
    $('followupResult').textContent = 'Error: ' + e.message;
  }
}

async function refreshHistory() {
  try {
    const resp = await fetch('/api/videos');
    const videos = await resp.json();
    $('histCount').textContent = videos.length;
    if (!videos.length) {
      $('historyList').textContent = 'No videos yet.';
      return;
    }
    $('historyList').innerHTML = videos.map(v => {
      const channel = v.channel ? v.channel + ' · ' : '';
      const date = v.saved_at ? new Date(v.saved_at).toLocaleDateString() : '';
      return '<div class="video-item" onclick="loadVideo(\\'' + v.video_id + '\\')">' +
        '<div style="flex:1;min-width:0;">' +
          '<div class="title">' + (v.title || v.video_id) + '</div>' +
          '<div class="meta">' + channel + (v.summary_count || 0) + ' summaries · ' + date + '</div>' +
          '<div class="meta"><a href="' + (v.url || 'https://youtube.com/watch?v=' + v.video_id) + '" target="_blank" style="color:#58a6ff;" onclick="event.stopPropagation();">' + v.video_id + '</a></div>' +
        '</div>' +
      '</div>';
    }).join('');
  } catch(e) {
    $('historyList').textContent = 'Error loading history.';
  }
}

async function loadVideo(videoId) {
  currentVideoId = videoId;
  try {
    const resp = await fetch('/api/videos/' + videoId);
    const data = await resp.json();
    const m = data.metadata || {};
    if (m.title) {
      const ch = m.channel ? ' · ' + m.channel : '';
      setStatus(m.title + ch, 'ok');
    }
    if (data.transcript && data.transcript.text) {
      $('transcriptResult').textContent = data.transcript.text;
    }
    if (data.summaries && data.summaries.length) {
      const el = $('summaryResult');
      el.innerHTML = '';
      data.summaries.slice().reverse().forEach((s, i) => {
        const date = s.created_at ? new Date(s.created_at).toLocaleString() : '';
        const header = document.createElement('div');
        header.style.cssText = 'color:#768390;font-size:0.8rem;margin-bottom:0.25rem;' + (i > 0 ? 'margin-top:1rem;border-top:1px solid #30363d;padding-top:0.75rem;' : '');
        header.textContent = (s.prompt_type || 'custom') + ' · ' + (s.model || '?') + ' · ' + date;
        el.appendChild(header);
        const body = document.createElement('div');
        body.style.whiteSpace = 'pre-wrap';
        body.textContent = s.response;
        el.appendChild(body);
      });
    }
    showTab('summary');
    document.querySelectorAll('.tab')[0].click();
  } catch(e) {}
}

async function doSearch() {
  const q = $('searchInput').value.trim();
  if (!q) return;
  try {
    const resp = await fetch('/api/search?q=' + encodeURIComponent(q));
    const data = await resp.json();
    $('searchResult').textContent = data.length
      ? data.map(v => (v.title || v.matched_video_id)).join('\\n')
      : 'No results.';
  } catch(e) {
    $('searchResult').textContent = 'Error: ' + e.message;
  }
}

// Load available models from health endpoint
fetch('/api/health').then(r => r.json()).then(d => {
  const sel = $('modelInput');
  sel.innerHTML = '';
  const models = d.available_models || [];
  const current = d.model || '';
  if (!models.length) {
    sel.innerHTML = '<option>' + (current || 'no models') + '</option>';
    return;
  }
  // Cloud models first, then local; current model always on top
  const cloud = models.filter(m => m.includes('cloud') && m !== current);
  const local = models.filter(m => !m.includes('cloud') && m !== current);
  const sorted = [current, ...cloud, ...local];
  sorted.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m; opt.textContent = m;
    sel.appendChild(opt);
  });
  sel.value = current;
}).catch(e => { console.error('loadModels:', e); });

loadPrompts();
refreshHistory();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return TEMPLATE


@app.route("/api/health")
def health():
    provider = get_provider()
    model = get_model(provider)
    models = list_ollama_models()
    model_names = [m["name"] for m in models]
    return jsonify({
        "status": "ok",
        "provider": provider,
        "model": model,
        "ollama_running": ollama_is_running(),
        "ollama_models": len(models),
        "available_models": model_names,
    })


@app.route("/api/videos")
def api_list_videos():
    return jsonify(list_videos())


@app.route("/api/videos/<video_id>")
def api_get_video(video_id: str):
    meta = load_metadata(video_id)
    transcript = load_transcript(video_id)
    summaries = load_summaries(video_id)
    if not meta and not transcript:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "video_id": video_id,
        "metadata": meta,
        "transcript": transcript,
        "summaries": summaries,
    })


@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    data = request.get_json(silent=True) or {}
    source = data.get("url") or data.get("source")
    if not source:
        return jsonify({"error": "url required"}), 400

    languages = data.get("languages")
    if isinstance(languages, str):
        languages = [l.strip() for l in languages.split(",") if l.strip()]

    prompt_type = data.get("prompt_type", "executive_summary")
    user_prompt = data.get("user_prompt", "")
    no_llm = data.get("no_llm", False)

    try:
        video_id = parse_video_id(source)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Fetch transcript
    try:
        segments = fetch_transcript(video_id, languages=languages)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 422

    full_text = transcript_to_text(segments)

    # Fetch and save metadata
    metadata = fetch_metadata(video_id)
    save_metadata(video_id, metadata)
    save_transcript(video_id, segments, full_text)

    result = {
        "video_id": video_id,
        "title": metadata.get("title"),
        "channel": metadata.get("channel"),
        "url": metadata.get("url"),
        "transcript_length": len(segments),
        "transcript_text": full_text[:2000],
    }

    if no_llm:
        return jsonify(result)

    # Summarize
    provider = data.get("provider") or get_provider()
    model = data.get("model") or get_model(provider)

    # Check if using a stored prompt by key
    prompt_key = data.get("prompt_key")
    prompt_text = ""
    if prompt_key:
        prompts = load_prompts()
        if prompt_key in prompts:
            prompt_text = prompts[prompt_key]["text"]
            record_prompt_use(prompt_key)

    system_msg, user_msg = build_prompt(full_text, prompt_type, user_prompt, prompt_text=prompt_text)

    try:
        response = chat(system_msg, user_msg, provider=provider, model=model)
    except RuntimeError as e:
        return jsonify({"error": f"LLM error: {e}", **result}), 502

    save_summary(video_id, prompt_key or prompt_type, user_prompt or prompt_type, model, response)
    result.update({
        "provider": provider,
        "model": model,
        "prompt_type": prompt_type,
        "summary": response,
    })
    return jsonify(result)


@app.route("/api/ask", methods=["POST"])
def api_ask():
    data = request.get_json(silent=True) or {}
    video_id = data.get("video_id")
    prompt = data.get("prompt")
    if not video_id or not prompt:
        return jsonify({"error": "video_id and prompt required"}), 400

    transcript = load_transcript(video_id)
    if not transcript:
        return jsonify({"error": "no transcript for this video"}), 404

    full_text = transcript.get("text", "")
    system_msg, user_msg = build_prompt(full_text, "custom", prompt)

    provider = data.get("provider") or get_provider()
    model = data.get("model") or get_model(provider)

    try:
        response = chat(system_msg, user_msg, provider=provider, model=model)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    save_summary(video_id, "custom", prompt, model, response)
    return jsonify({"video_id": video_id, "prompt": prompt, "response": response,
                    "model": model})


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "")
    if not q:
        return jsonify({"error": "query required"}), 400
    return jsonify(search_transcripts(q))


@app.route("/api/prompts")
def api_list_prompts():
    init_default_prompts()
    prompts = load_prompts()
    sort = request.args.get("sort", "newest")
    items = [{"key": k, **v} for k, v in prompts.items()]
    if sort == "most_used":
        items.sort(key=lambda x: x.get("use_count", 0), reverse=True)
    else:
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jsonify(items)


@app.route("/api/prompts", methods=["POST"])
def api_save_prompt():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text required"}), 400
    if not title:
        title = text[:50]
    from datetime import datetime
    key = data.get("key") or f"{title.lower().replace(' ', '_')[:30]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    entry = save_prompt(key, title, text)
    return jsonify({"key": key, **entry})


@app.route("/api/prompts/<key>", methods=["DELETE"])
def api_delete_prompt(key: str):
    if delete_prompt(key):
        return jsonify({"deleted": key})
    return jsonify({"error": "not found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100)
