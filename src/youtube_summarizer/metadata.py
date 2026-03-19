"""Fetch YouTube video metadata via yt-dlp (optional dependency)."""

from typing import Optional


def fetch_metadata(video_id: str) -> dict:
    """Fetch video metadata. Returns dict with title, channel, etc.

    Falls back to minimal stub if yt-dlp is not installed.
    """
    try:
        import yt_dlp
    except ImportError:
        return _stub_metadata(video_id)

    url = f"https://www.youtube.com/watch?v={video_id}"
    opts = {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
        "extract_flat": False,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            "video_id": video_id,
            "title": info.get("title"),
            "channel": info.get("uploader"),
            "description": info.get("description"),
            "thumbnail_url": info.get("thumbnail"),
            "duration": info.get("duration"),
            "language": info.get("language"),
            "url": info.get("webpage_url", url),
        }
    except Exception:
        return _stub_metadata(video_id)


def _stub_metadata(video_id: str) -> dict:
    """Minimal metadata when yt-dlp is unavailable."""
    return {
        "video_id": video_id,
        "title": None,
        "channel": None,
        "description": None,
        "thumbnail_url": None,
        "duration": None,
        "language": None,
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }
