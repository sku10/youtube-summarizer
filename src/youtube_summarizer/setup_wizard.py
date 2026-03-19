"""Interactive setup wizard for YouTube Summarizer."""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

CHECK = f"{GREEN}[✓]{RESET}"
CROSS = f"{RED}[✗]{RESET}"
WARN = f"{YELLOW}[!]{RESET}"
INFO = f"{CYAN}[i]{RESET}"


def _ask(prompt: str, default: str = "n") -> bool:
    """Ask y/N question, return True if yes."""
    suffix = "[Y/n]" if default == "y" else "[y/N]"
    try:
        answer = input(f"    {prompt} {suffix}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default == "y"
    return answer in ("y", "yes")


def _ask_input(prompt: str) -> str:
    try:
        return input(f"    {prompt}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def _run(cmd: str, show: bool = True) -> tuple[int, str]:
    """Run a shell command, return (returncode, output)."""
    if show:
        print(f"    {DIM}$ {cmd}{RESET}")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=300
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, "Command timed out"
    except Exception as e:
        return 1, str(e)


def _header(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")


def _item(ok: bool, msg: str) -> None:
    mark = CHECK if ok else CROSS
    print(f"  {mark} {msg}")


def _info(msg: str) -> None:
    print(f"  {INFO} {msg}")


def _warn(msg: str) -> None:
    print(f"  {WARN} {msg}")


def run_wizard() -> None:
    """Run the full interactive setup wizard."""
    env_path = Path.cwd() / ".env"
    env_vars: dict[str, str] = {}

    # Load existing .env if present
    if env_path.exists():
        load_dotenv(env_path)

    print(f"\n{BOLD}{'═' * 50}{RESET}")
    print(f"{BOLD}  YouTube Summarizer — Setup Wizard{RESET}")
    print(f"{BOLD}{'═' * 50}{RESET}")

    # ── Python ──
    _header("Python")
    py_version = platform.python_version()
    py_ok = sys.version_info >= (3, 10)
    _item(py_ok, f"Python {py_version}")
    if not py_ok:
        print(f"    Requires Python 3.10+. Please upgrade.")
        return

    # ── Core dependencies ──
    _header("Dependencies")
    for pkg, import_name, required in [
        ("youtube-transcript-api", "youtube_transcript_api", True),
        ("flask", "flask", True),
        ("python-dotenv", "dotenv", True),
        ("yt-dlp", "yt_dlp", False),
    ]:
        try:
            __import__(import_name)
            _item(True, f"{pkg}")
        except ImportError:
            _item(False, f"{pkg}" + (" (required)" if required else " (optional — enables video metadata)"))
            if required:
                if _ask(f"Install {pkg}?"):
                    code, out = _run(f"{sys.executable} -m pip install {pkg}")
                    if code == 0:
                        _item(True, f"{pkg} installed")
                    else:
                        print(f"    Install failed: {out[:200]}")
                        return
            else:
                if _ask(f"Install {pkg}? (recommended)"):
                    code, out = _run(f"{sys.executable} -m pip install {pkg}")
                    _item(code == 0, f"{pkg} {'installed' if code == 0 else 'failed'}")

    # ── Hardware ──
    _header("Hardware")
    gpu_found = False
    gpu_info = ""
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        code, out = _run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits", show=False)
        if code == 0 and out.strip():
            for line in out.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                name = parts[0] if parts else "Unknown"
                mem = parts[1] if len(parts) > 1 else "?"
                _item(True, f"GPU: {name} ({mem} MB)")
                gpu_found = True
                gpu_info = f"{name} ({mem} MB)"
    if not gpu_found:
        _item(False, "No NVIDIA GPU detected")
        _info("CPU-only mode works but is slower (1-2 min per summary vs seconds on GPU)")
        _info("Consider using a cloud provider for faster results")

    # CPU
    cpu_name = "Unknown"
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    cpu_name = line.split(":")[1].strip()
                    break
    except FileNotFoundError:
        try:
            code, out = _run("sysctl -n machdep.cpu.brand_string 2>/dev/null", show=False)
            if code == 0:
                cpu_name = out.strip()
        except Exception:
            pass
    _item(True, f"CPU: {cpu_name}")

    # ── Ollama ──
    _header("Ollama (Local LLM)")
    ollama_bin = shutil.which("ollama")
    ollama_running = False
    ollama_models: list[dict] = []

    if ollama_bin:
        code, out = _run("ollama --version", show=False)
        version = out.strip().split("version is ")[-1] if "version" in out else out.strip()
        _item(True, f"Ollama installed ({version})")

        # Check if running
        from . import llm
        ollama_running = llm.ollama_is_running()
        if ollama_running:
            _item(True, "Ollama server is running")
            ollama_models = llm.list_ollama_models()
            if ollama_models:
                _item(True, f"{len(ollama_models)} model(s) available")
                # Show non-embedding models
                chat_models = [m for m in ollama_models
                               if m["family"] not in ("bert",) and m["size_gb"] > 0]
                if chat_models:
                    print(f"    {'─' * 40}")
                    for m in chat_models[:10]:
                        print(f"    {m['name']:40s} {m['params']:>8s}  {m['size_gb']:>6.1f} GB")
                    if len(chat_models) > 10:
                        print(f"    ... and {len(chat_models) - 10} more")
                    print(f"    {'─' * 40}")
            else:
                _item(False, "No models loaded")
                if gpu_found:
                    _info("Recommended: ollama pull qwen3.5:9b  (6.6 GB)")
                else:
                    _info("Recommended: ollama pull qwen3.5:3b  (1.9 GB, works on CPU)")
                model_to_pull = "qwen3.5:9b" if gpu_found else "qwen3.5:3b"
                if _ask(f"Pull {model_to_pull} now?"):
                    print(f"    Pulling {model_to_pull} (this may take a few minutes)...")
                    code, out = _run(f"ollama pull {model_to_pull}")
                    _item(code == 0, f"{model_to_pull} {'ready' if code == 0 else 'failed'}")
        else:
            _item(False, "Ollama server not running")
            if _ask("Start Ollama now?"):
                _run("ollama serve &", show=True)
                import time
                time.sleep(3)
                ollama_running = llm.ollama_is_running()
                _item(ollama_running, "Ollama " + ("started" if ollama_running else "failed to start"))
    else:
        _item(False, "Ollama not installed")
        _info("Ollama runs LLMs locally — free, private, no API key needed")
        if sys.platform == "linux":
            _info("Install: curl -fsSL https://ollama.com/install.sh | sh")
            if _ask("Install Ollama now?"):
                code, out = _run("curl -fsSL https://ollama.com/install.sh | sh")
                _item(code == 0, "Ollama " + ("installed" if code == 0 else "install failed"))
                if code == 0:
                    _run("ollama serve &", show=True)
                    import time
                    time.sleep(3)
        elif sys.platform == "darwin":
            _info("Install: brew install ollama")
            if _ask("Install via Homebrew?"):
                code, _ = _run("brew install ollama")
                _item(code == 0, "Ollama " + ("installed" if code == 0 else "install failed"))
        else:
            _info("Download from: https://ollama.com/download")

    # ── Cloud API Keys ──
    _header("Cloud LLM Providers")
    providers = [
        ("GEMINI_API_KEY", "Google Gemini", "Free: 15 req/min, 1M tokens/day",
         "https://aistudio.google.com/apikey"),
        ("GROQ_API_KEY", "Groq", "Free: 30 req/min, 14.4K req/day",
         "https://console.groq.com/keys"),
        ("OPENROUTER_API_KEY", "OpenRouter", "Some free models",
         "https://openrouter.ai/keys"),
    ]
    has_any_cloud = False
    for env_var, name, tier_info, url in providers:
        key = os.environ.get(env_var, "")
        if key:
            masked = key[:4] + "..." + key[-4:] if len(key) > 8 else "***"
            _item(True, f"{name} — key found ({masked})")
            has_any_cloud = True
        else:
            _item(False, f"{name} — no key")
            _info(f"{tier_info}")
            _info(f"Get key: {url}")
            if _ask(f"Add {name} API key now?"):
                new_key = _ask_input("Paste API key")
                if new_key:
                    os.environ[env_var] = new_key
                    env_vars[env_var] = new_key
                    has_any_cloud = True
                    _item(True, f"{name} key saved")

    # ── Choose default provider ──
    _header("Default LLM Provider")
    current_provider = os.environ.get("LLM_PROVIDER", "")

    if ollama_running and ollama_models:
        _info("Ollama is ready with local models — recommended for privacy")
    if has_any_cloud:
        _info("Cloud provider(s) configured — faster, no local resources needed")

    if not ollama_running and not has_any_cloud:
        _warn("No LLM provider available! Set up Ollama or a cloud API key.")
        _info("You can still fetch and store transcripts without summarization.")
    else:
        available = []
        if ollama_running:
            available.append("ollama")
        for env_var, name, _, _ in providers:
            if os.environ.get(env_var):
                available.append(name.lower().split()[0])

        if current_provider and current_provider in available:
            _item(True, f"Current default: {current_provider}")
        else:
            print(f"    Available: {', '.join(available)}")
            choice = _ask_input(f"Choose default provider ({'/'.join(available)})")
            if choice and choice.lower() in available:
                env_vars["LLM_PROVIDER"] = choice.lower()
                os.environ["LLM_PROVIDER"] = choice.lower()
            elif available:
                env_vars["LLM_PROVIDER"] = available[0]
                os.environ["LLM_PROVIDER"] = available[0]
                _info(f"Defaulting to: {available[0]}")

        # Set default model for chosen provider
        chosen = os.environ.get("LLM_PROVIDER", "ollama")
        if chosen == "ollama" and ollama_models:
            current_model = os.environ.get("OLLAMA_MODEL", "")
            model_names = [m["name"] for m in ollama_models if m["size_gb"] > 0]
            if current_model and current_model in model_names:
                _item(True, f"Ollama model: {current_model}")
            elif model_names:
                # Pick a sensible default
                preferred = ["qwen3.5:9b", "qwen3.5:27b", "qwen3:14b", "qwen3:8b", "llama3.1:latest"]
                picked = next((p for p in preferred if p in model_names), model_names[0])
                env_vars["OLLAMA_MODEL"] = picked
                _item(True, f"Ollama model: {picked}")

    # ── Test connections ──
    _header("Connection Tests")
    from . import llm as llm_mod

    chosen_provider = os.environ.get("LLM_PROVIDER", "ollama")
    if chosen_provider == "ollama" and ollama_running:
        model = os.environ.get("OLLAMA_MODEL", llm_mod.get_model("ollama"))
        print(f"  Testing Ollama ({model})...", end="", flush=True)
        ok, msg = llm_mod.test_connection("ollama", model)
        print(f"\r  {CHECK if ok else CROSS} Ollama {model}: {msg[:60]}")
    for env_var, name, _, _ in providers:
        if os.environ.get(env_var):
            provider_key = name.lower().split()[0]
            print(f"  Testing {name}...", end="", flush=True)
            ok, msg = llm_mod.test_connection(provider_key)
            print(f"\r  {CHECK if ok else CROSS} {name}: {msg[:60]}")

    # ── Storage ──
    _header("Storage")
    data_dir = Path(os.environ.get("YT_SUMMARIZER_DATA_DIR", str(Path.cwd() / "data")))
    data_dir.mkdir(parents=True, exist_ok=True)
    _item(True, f"Data directory: {data_dir}")
    videos_dir = data_dir / "videos"
    if videos_dir.exists():
        count = sum(1 for d in videos_dir.iterdir() if d.is_dir())
        _item(True, f"{count} video(s) stored")
    else:
        _item(True, "Fresh install — no videos yet")

    # ── Write .env ──
    if env_vars:
        _header("Saving Configuration")
        # Merge with existing .env
        existing = {}
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()
        existing.update(env_vars)
        lines = [f"{k}={v}" for k, v in sorted(existing.items())]
        env_path.write_text("\n".join(lines) + "\n")
        _item(True, f"Config saved to {env_path}")

    # ── Summary ──
    print(f"\n{BOLD}{'═' * 50}{RESET}")
    provider_display = os.environ.get("LLM_PROVIDER", "none")
    model_display = env_vars.get("OLLAMA_MODEL", os.environ.get("OLLAMA_MODEL", ""))
    print(f"  Provider: {provider_display}" + (f" ({model_display})" if model_display else ""))
    print(f"  Storage:  {data_dir}")
    print()
    print(f"  {BOLD}Usage:{RESET}")
    print(f"    yt-summarize <youtube-url>              # summarize a video")
    print(f"    yt-summarize <youtube-url> --ask '...'  # ask a question")
    print(f"    yt-summarize --serve                    # start web dashboard")
    print(f"    yt-summarize --setup                    # run this wizard again")
    print(f"{BOLD}{'═' * 50}{RESET}\n")
