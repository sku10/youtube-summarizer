"""LLM abstraction — Ollama (local) and cloud providers via HTTP."""

import json
import os
import urllib.request
import urllib.error
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# Provider configs: (env_key_for_api_key, default_model, base_url_template)
PROVIDERS = {
    "ollama": {
        "key_env": None,
        "default_model": "qwen3.5:9b",
        "model_env": "OLLAMA_MODEL",
    },
    "gemini": {
        "key_env": "GEMINI_API_KEY",
        "default_model": "gemini-2.0-flash",
        "model_env": "GEMINI_MODEL",
    },
    "groq": {
        "key_env": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
        "model_env": "GROQ_MODEL",
    },
    "openrouter": {
        "key_env": "OPENROUTER_API_KEY",
        "default_model": "google/gemini-2.0-flash-exp:free",
        "model_env": "OPENROUTER_MODEL",
    },
}


def get_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "ollama").lower()


def get_model(provider: Optional[str] = None) -> str:
    provider = provider or get_provider()
    cfg = PROVIDERS.get(provider, PROVIDERS["ollama"])
    env_model = os.environ.get(cfg["model_env"])
    if env_model:
        return env_model
    # For ollama, try to pick from actually available models
    if provider == "ollama":
        models = list_ollama_models()
        if models:
            model_names = [m["name"] for m in models if m.get("size_gb", 0) > 0 or m.get("cloud")]
            if model_names:
                # Prefer cloud models first, then local by size
                # Prefer cloud models first, then local by quality
                cloud_names = [m for m in model_names if "cloud" in m]
                local_names = [m for m in model_names if "cloud" not in m]
                preferred = cloud_names + ["qwen3.5:9b", "qwen3.5:27b", "qwen3.5:3b",
                             "qwen3.5:0.8b", "llama3.1:latest"]
                for p in preferred:
                    if p in model_names:
                        return p
                return model_names[0]
    return cfg["default_model"]


def get_ollama_url() -> str:
    return os.environ.get("OLLAMA_URL", "http://localhost:11434")


def _http_post(url: str, payload: dict, headers: dict, timeout: int = 120) -> dict:
    """Simple HTTP POST returning parsed JSON."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"HTTP {e.code} from {url}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach {url}: {e.reason}") from e


def _chat_ollama(system: str, user: str, model: str) -> str:
    url = f"{get_ollama_url()}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    num_ctx = os.environ.get("OLLAMA_NUM_CTX")
    if num_ctx:
        payload["options"] = {"num_ctx": int(num_ctx)}
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("OLLAMA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    timeout = int(os.environ.get("OLLAMA_TIMEOUT", "600"))
    resp = _http_post(url, payload, headers, timeout=timeout)
    return resp.get("message", {}).get("content", "")


def _chat_gemini(system: str, user: str, model: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={api_key}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
    }
    resp = _http_post(url, payload, {"Content-Type": "application/json"})
    try:
        return resp["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected Gemini response: {json.dumps(resp)[:500]}")


def _chat_openai_compat(system: str, user: str, model: str,
                        base_url: str, api_key: str) -> str:
    """OpenAI-compatible chat (Groq, OpenRouter, etc.)."""
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    resp = _http_post(url, payload, headers)
    try:
        return resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected response: {json.dumps(resp)[:500]}")


def chat(system: str, user: str, provider: Optional[str] = None,
         model: Optional[str] = None) -> str:
    """Send a chat message to the configured LLM provider.

    Returns the assistant's response text.
    """
    provider = provider or get_provider()
    model = model or get_model(provider)

    if provider == "ollama":
        return _chat_ollama(system, user, model)
    elif provider == "gemini":
        return _chat_gemini(system, user, model)
    elif provider == "groq":
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set")
        return _chat_openai_compat(system, user, model,
                                   "https://api.groq.com/openai/v1", api_key)
    elif provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        return _chat_openai_compat(system, user, model,
                                   "https://openrouter.ai/api/v1", api_key)
    else:
        raise RuntimeError(f"Unknown LLM provider: {provider}")


def test_connection(provider: Optional[str] = None,
                    model: Optional[str] = None) -> tuple[bool, str]:
    """Quick connection test. Returns (success, message)."""
    try:
        resp = chat("You are a test.", "Say OK.", provider=provider, model=model)
        return True, resp.strip()[:100]
    except Exception as e:
        return False, str(e)


def _fetch_ollama_models(url: str, api_key: str = "", is_cloud: bool = False) -> list[dict]:
    """Fetch models from a single Ollama endpoint."""
    try:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = urllib.request.Request(f"{url}/api/tags", headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return [
            {
                "name": m["name"],
                "size_gb": round(m.get("size", 0) / 1e9, 1),
                "family": m.get("details", {}).get("family", ""),
                "params": m.get("details", {}).get("parameter_size", ""),
                "cloud": is_cloud or "cloud" in m["name"] or bool(m.get("remote_host")),
            }
            for m in data.get("models", [])
        ]
    except Exception:
        return []


def list_ollama_models() -> list[dict]:
    """List models from both local Ollama and Ollama cloud (if configured)."""
    seen = set()
    result = []

    # Query Ollama cloud first if API key is set
    api_key = os.environ.get("OLLAMA_API_KEY", "")
    if api_key:
        for m in _fetch_ollama_models("https://ollama.com", api_key, is_cloud=True):
            if m["name"] not in seen:
                seen.add(m["name"])
                result.append(m)

    # Then local Ollama
    for m in _fetch_ollama_models("http://localhost:11434"):
        if m["name"] not in seen:
            seen.add(m["name"])
            result.append(m)

    # Sort: cloud first (best models on top), then local
    _cloud_rank = {
        "qwen3.5": 0, "deepseek-v3": 1, "kimi-k2": 2, "minimax-m2": 3,
        "gpt-oss": 4, "glm-5": 5, "cogito": 6,
    }

    def _sort_key(m):
        is_cloud = 0 if m["cloud"] else 1
        rank = 99
        for prefix, r in _cloud_rank.items():
            if m["name"].startswith(prefix):
                rank = r
                break
        return (is_cloud, rank, m["name"])

    result.sort(key=_sort_key)
    return result


def ollama_is_running() -> bool:
    try:
        url = f"{get_ollama_url()}/api/tags"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False
