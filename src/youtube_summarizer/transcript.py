"""Fetch YouTube transcripts."""

import os
import urllib.parse
from typing import Iterable, Optional

from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)
from youtube_transcript_api.proxies import GenericProxyConfig


def _get_proxy_config() -> Optional[GenericProxyConfig]:
    """Build proxy config from YOUTUBE_PROXY env var if set."""
    proxy_url = os.environ.get("YOUTUBE_PROXY")
    if proxy_url:
        return GenericProxyConfig(https_url=proxy_url)
    return None


def parse_video_id(source: str) -> str:
    """Extract video ID from a URL or plain ID string."""
    if not source:
        raise ValueError("Video ID or URL must be supplied")
    source = source.strip()
    parsed = urllib.parse.urlparse(source)
    if "youtube.com" in (parsed.netloc or "") or "youtu.be" in (parsed.netloc or ""):
        if parsed.query:
            params = urllib.parse.parse_qs(parsed.query)
            if "v" in params:
                return params["v"][0]
        path = parsed.path.strip("/ ")
        if path:
            return path
        raise ValueError(f"Cannot extract video ID from URL: {source}")
    return source


def fetch_transcript(
    video_id: str,
    languages: Optional[Iterable[str]] = None,
) -> list[dict]:
    """Fetch transcript segments for a YouTube video.

    Returns list of {text, start, duration} dicts.
    Raises RuntimeError if transcript unavailable.
    """
    try:
        proxy = _get_proxy_config()
        api = YouTubeTranscriptApi(proxy_config=proxy)
        if languages:
            transcript = api.fetch(video_id, languages=list(languages))
        else:
            transcript = api.fetch(video_id)
        return transcript.to_raw_data()
    except TranscriptsDisabled:
        raise RuntimeError(f"Transcripts are disabled for video {video_id}")
    except NoTranscriptFound:
        raise RuntimeError(f"No transcript found for video {video_id}")
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch transcript: {exc}") from exc


def transcript_to_text(segments: list[dict]) -> str:
    """Flatten transcript segments into a single text string."""
    return " ".join(seg.get("text", "") for seg in segments)
