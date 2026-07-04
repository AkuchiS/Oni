"""
A minimal, optional, OpenAI-compatible chat client over stdlib urllib.

oni never *requires* a model — every stage has a heuristic fallback. But if one is configured
it writes a much better narrative. Configuration is by environment, so it drops straight onto
an OpenAI, OpenRouter, Ollama, vLLM, or any OpenAI-compatible endpoint:

    ONI_ENDPOINT   (or OPENAI_BASE_URL / OPENAI_API_BASE)  default https://api.openai.com/v1
    ONI_API_KEY    (or OPENAI_API_KEY)                     optional (Ollama/local need none)
    ONI_MODEL      (or OPENAI_MODEL)                        default gpt-4o-mini

`available()` tells the pipeline whether to bother; `complete()` returns text or None. It never
raises into the pipeline — a dead endpoint just means the heuristic path is taken.
"""
import os
import json
import urllib.request
import urllib.error


def _base():
    b = (os.environ.get("ONI_ENDPOINT") or os.environ.get("OPENAI_BASE_URL")
         or os.environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1")
    return b.rstrip("/")


def _key():
    return os.environ.get("ONI_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""


def model():
    return os.environ.get("ONI_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"


def available():
    """A model is usable if a key is set, or the endpoint is a local one (no key needed)."""
    if os.environ.get("ONI_NO_LLM"):
        return False
    if _key():
        return True
    b = _base().lower()
    return any(h in b for h in ("localhost", "127.0.0.1", "0.0.0.0", "ollama", ":11434", ":8000", ":1234"))


def complete(prompt, system=None, max_tokens=1400, temperature=0.2, timeout=90):
    """One-shot completion. Returns the text, or None on any failure (caller falls back)."""
    if not available():
        return None
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": model(), "messages": msgs,
        "max_tokens": max_tokens, "temperature": temperature,
    }).encode()
    headers = {"Content-Type": "application/json"}
    if _key():
        headers["Authorization"] = "Bearer " + _key()
    req = urllib.request.Request(_base() + "/chat/completions", data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
        return (d["choices"][0]["message"]["content"] or "").strip() or None
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, OSError):
        return None
