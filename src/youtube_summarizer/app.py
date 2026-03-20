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

from pathlib import Path

app = Flask(__name__)
init_default_prompts()

TEMPLATE = (Path(__file__).parent / "index.html").read_text()



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

    # Use cached transcript if available
    cached_transcript = load_transcript(video_id)
    cached_meta = load_metadata(video_id)
    if cached_transcript and cached_meta:
        full_text = cached_transcript.get("text", "")
        metadata = cached_meta
        segments = cached_transcript.get("segments", [])
    else:
        try:
            segments = fetch_transcript(video_id, languages=languages)
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 422
        full_text = transcript_to_text(segments)
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5100)
    args = parser.parse_args()
    app.run(host="0.0.0.0", port=args.port)
