"""CLI entry point for YouTube Summarizer."""

import argparse
import json
import sys

from dotenv import load_dotenv

load_dotenv()


SERVICE_NAME = "yt-summarize"


def _install_service(port: int) -> None:
    """Install systemd user service."""
    import shutil
    import subprocess
    from pathlib import Path

    venv_python = shutil.which("python") or sys.executable
    project_dir = Path.cwd()
    env_file = project_dir / ".env"

    service_dir = Path.home() / ".config" / "systemd" / "user"
    service_dir.mkdir(parents=True, exist_ok=True)
    service_file = service_dir / f"{SERVICE_NAME}.service"

    unit = f"""[Unit]
Description=YouTube Summarizer Web Dashboard
After=network.target

[Service]
Type=simple
WorkingDirectory={project_dir}
ExecStart={venv_python} -m youtube_summarizer.app --port {port}
Restart=on-failure
RestartSec=5
{'EnvironmentFile=' + str(env_file) if env_file.exists() else ''}

[Install]
WantedBy=default.target
"""
    service_file.write_text(unit)
    subprocess.run(["systemctl", "--user", "daemon-reload"])
    subprocess.run(["systemctl", "--user", "enable", SERVICE_NAME])
    subprocess.run(["systemctl", "--user", "start", SERVICE_NAME])
    # Enable lingering so service runs without active login session
    subprocess.run(["loginctl", "enable-linger"], capture_output=True)

    print(f"Service installed and started.")
    print(f"  Dashboard: http://localhost:{port}")
    print(f"  Status:    systemctl --user status {SERVICE_NAME}")
    print(f"  Logs:      journalctl --user -u {SERVICE_NAME} -f")
    print(f"  Stop:      systemctl --user stop {SERVICE_NAME}")
    print(f"  Remove:    yt-summarize --uninstall-service")


def _uninstall_service() -> None:
    """Remove systemd user service."""
    import subprocess
    from pathlib import Path

    subprocess.run(["systemctl", "--user", "stop", SERVICE_NAME], capture_output=True)
    subprocess.run(["systemctl", "--user", "disable", SERVICE_NAME], capture_output=True)
    service_file = Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"
    if service_file.exists():
        service_file.unlink()
    subprocess.run(["systemctl", "--user", "daemon-reload"])
    print(f"Service removed.")


def _summarize(args) -> None:
    from .transcript import fetch_transcript, parse_video_id, transcript_to_text
    from .metadata import fetch_metadata
    from .storage import save_metadata, save_transcript, save_summary, load_transcript, load_metadata, init_default_prompts
    from .llm import chat, get_provider, get_model
    from .prompts import build_prompt
    init_default_prompts()

    source = args.url
    video_id = parse_video_id(source)
    languages = [l.strip() for l in args.language.split(",")] if args.language else None

    # Use cached transcript if available
    cached = load_transcript(video_id)
    cached_meta = load_metadata(video_id) if cached else None

    if cached and cached_meta:
        segments = cached.get("segments", [])
        full_text = cached.get("text", "")
        metadata = cached_meta
        print(f"Using cached transcript for {video_id} ({len(segments)} segments, {len(full_text)} chars)")
        if metadata.get("title"):
            ch = f" ({metadata['channel']})" if metadata.get("channel") else ""
            print(f"Title: {metadata['title']}{ch}")
    else:
        print(f"Fetching transcript for {video_id}...", flush=True)
        try:
            segments = fetch_transcript(video_id, languages=languages)
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        full_text = transcript_to_text(segments)
        print(f"Transcript: {len(segments)} segments, {len(full_text)} chars")
        print("Fetching metadata...", flush=True)
        metadata = fetch_metadata(video_id)
        if metadata.get("title"):
            print(f"Title: {metadata['title']}")
        save_metadata(video_id, metadata)
        save_transcript(video_id, segments, full_text)

    # LLM summarization
    if args.no_llm:
        print("\nTranscript saved. Skipping LLM summary (--no-llm).")
        if args.json:
            print(json.dumps({"video_id": video_id, "metadata": metadata,
                              "transcript_length": len(segments)}, indent=2))
        return

    provider = args.provider or get_provider()
    model = args.model or get_model(provider)

    if args.ask:
        prompt_type = "custom"
        user_prompt = args.ask
    else:
        prompt_type = args.prompt_type or "executive_summary"
        user_prompt = ""

    system_msg, user_msg = build_prompt(full_text, prompt_type, user_prompt)
    print(f"\nSummarizing with {provider}/{model}...", flush=True)

    try:
        response = chat(system_msg, user_msg, provider=provider, model=model)
    except RuntimeError as e:
        print(f"LLM error: {e}", file=sys.stderr)
        print("Transcript was saved. Run with --no-llm or fix provider config.")
        sys.exit(1)

    save_summary(video_id, prompt_type, user_prompt or prompt_type, model, response)

    if args.json:
        print(json.dumps({
            "video_id": video_id,
            "title": metadata.get("title"),
            "provider": provider,
            "model": model,
            "prompt_type": prompt_type,
            "summary": response,
        }, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'─' * 50}")
        print(response)
        print(f"{'─' * 50}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="YouTube Summarizer — fetch transcripts, summarize with LLMs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  yt-summarize https://youtu.be/VIDEO_ID
  yt-summarize VIDEO_ID --prompt key_points
  yt-summarize VIDEO_ID --ask "What tools are mentioned?"
  yt-summarize --serve
  yt-summarize --setup""",
    )

    parser.add_argument("url", nargs="?", help="YouTube URL or video ID")
    parser.add_argument("--ask", help="Ask a custom question about the video")
    parser.add_argument("--prompt", dest="prompt_type",
                        choices=["executive_summary", "key_points"],
                        help="Prompt type (default: executive_summary)")
    parser.add_argument("--language", "-l",
                        help="Comma-separated language codes (e.g. en,fi)")
    parser.add_argument("--provider", help="LLM provider override")
    parser.add_argument("--model", help="Model override")
    parser.add_argument("--no-llm", action="store_true",
                        help="Fetch and store transcript only, skip summarization")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    parser.add_argument("--serve", action="store_true",
                        help="Start the web dashboard")
    parser.add_argument("--port", type=int, default=5100,
                        help="Web dashboard port (default: 5100)")
    parser.add_argument("--setup", action="store_true",
                        help="Run the setup wizard")
    parser.add_argument("--list", action="store_true",
                        help="List all stored videos")
    parser.add_argument("--install-service", action="store_true",
                        help="Install as systemd user service (auto-starts on login)")
    parser.add_argument("--uninstall-service", action="store_true",
                        help="Remove the systemd user service")

    args = parser.parse_args()

    if args.setup:
        from .setup_wizard import run_wizard
        run_wizard()
        return

    if args.install_service:
        _install_service(args.port)
        return

    if args.uninstall_service:
        _uninstall_service()
        return

    if args.serve:
        from .app import app
        print(f"Starting YouTube Summarizer on http://localhost:{args.port}")
        app.run(host="0.0.0.0", port=args.port)
        return

    if args.list:
        from .storage import list_videos
        videos = list_videos()
        if not videos:
            print("No videos stored yet.")
            return
        for v in videos:
            title = v.get("title") or v.get("video_id", "?")
            vid = v.get("video_id", "?")
            sums = v.get("summary_count", 0)
            print(f"  {vid}  {title[:60]}  ({sums} summaries)")
        return

    if not args.url:
        parser.print_help()
        return

    _summarize(args)
