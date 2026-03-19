"""JSON file-based storage for videos, transcripts, and summaries."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_DATA_DIR = Path.cwd() / "data"


def _data_dir() -> Path:
    import os
    p = Path(os.environ.get("YT_SUMMARIZER_DATA_DIR", str(DEFAULT_DATA_DIR)))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _video_dir(video_id: str) -> Path:
    d = _data_dir() / "videos" / video_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_metadata(video_id: str, metadata: dict) -> None:
    metadata["saved_at"] = _now()
    path = _video_dir(video_id) / "metadata.json"
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))


def save_transcript(video_id: str, segments: list[dict], full_text: str) -> None:
    path = _video_dir(video_id) / "transcript.json"
    payload = {
        "video_id": video_id,
        "fetched_at": _now(),
        "segment_count": len(segments),
        "segments": segments,
        "text": full_text,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def save_summary(video_id: str, prompt_type: str, user_prompt: str,
                 model: str, response: str) -> None:
    path = _video_dir(video_id) / "summaries.json"
    summaries = load_summaries(video_id)
    summaries.append({
        "prompt_type": prompt_type,
        "user_prompt": user_prompt,
        "model": model,
        "response": response,
        "created_at": _now(),
    })
    path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2))


def load_metadata(video_id: str) -> Optional[dict]:
    path = _video_dir(video_id) / "metadata.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def load_transcript(video_id: str) -> Optional[dict]:
    path = _video_dir(video_id) / "transcript.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def load_summaries(video_id: str) -> list[dict]:
    path = _video_dir(video_id) / "summaries.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def list_videos() -> list[dict]:
    """List all stored videos with metadata."""
    videos_dir = _data_dir() / "videos"
    if not videos_dir.exists():
        return []
    results = []
    for d in sorted(videos_dir.iterdir()):
        if not d.is_dir():
            continue
        meta = load_metadata(d.name)
        if meta:
            meta["has_transcript"] = (d / "transcript.json").exists()
            meta["summary_count"] = len(load_summaries(d.name))
            results.append(meta)
    return results


def _prompts_path() -> Path:
    return _data_dir() / "prompts.json"


def load_prompts() -> dict:
    """Load all saved prompts. Returns {key: {title, text, created_at, last_used, use_count}}."""
    path = _prompts_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_prompt(key: str, title: str, text: str) -> dict:
    """Save or update a prompt. Returns the prompt entry."""
    prompts = load_prompts()
    now = _now()
    if key in prompts:
        prompts[key]["title"] = title
        prompts[key]["text"] = text
    else:
        prompts[key] = {
            "title": title,
            "text": text,
            "created_at": now,
            "last_used": None,
            "use_count": 0,
        }
    _prompts_path().write_text(json.dumps(prompts, ensure_ascii=False, indent=2))
    return prompts[key]


def record_prompt_use(key: str) -> None:
    """Increment use_count and update last_used for a prompt."""
    prompts = load_prompts()
    if key in prompts:
        prompts[key]["use_count"] = prompts[key].get("use_count", 0) + 1
        prompts[key]["last_used"] = _now()
        _prompts_path().write_text(json.dumps(prompts, ensure_ascii=False, indent=2))


def delete_prompt(key: str) -> bool:
    """Delete a prompt by key. Returns True if deleted."""
    prompts = load_prompts()
    if key in prompts:
        del prompts[key]
        _prompts_path().write_text(json.dumps(prompts, ensure_ascii=False, indent=2))
        return True
    return False


def init_default_prompts() -> None:
    """Seed default prompts if prompts.json doesn't exist."""
    path = _prompts_path()
    if path.exists():
        return
    from .prompts import EXECUTIVE_SUMMARY, KEY_POINTS, SYSTEM_PROMPT
    now = _now()
    defaults = {
        "executive_summary": {
            "title": "Executive Summary",
            "text": EXECUTIVE_SUMMARY.replace("\n\nTranscript:\n{transcript}", ""),
            "created_at": now,
            "last_used": None,
            "use_count": 0,
        },
        "key_points": {
            "title": "Key Points",
            "text": KEY_POINTS.replace("\n\nTranscript:\n{transcript}", ""),
            "created_at": now,
            "last_used": None,
            "use_count": 0,
        },
    }
    path.write_text(json.dumps(defaults, ensure_ascii=False, indent=2))


def search_transcripts(query: str) -> list[dict]:
    """Search across all stored transcripts."""
    query_lower = query.lower()
    videos_dir = _data_dir() / "videos"
    if not videos_dir.exists():
        return []
    results = []
    for d in videos_dir.iterdir():
        if not d.is_dir():
            continue
        transcript = load_transcript(d.name)
        if transcript and query_lower in transcript.get("text", "").lower():
            meta = load_metadata(d.name) or {"video_id": d.name}
            meta["matched_video_id"] = d.name
            results.append(meta)
    return results
