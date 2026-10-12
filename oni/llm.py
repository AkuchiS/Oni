"""Optional model transport. The public pipeline requires explicit use_llm=True.

ONI_ENDPOINT pairs only with ONI_API_KEY. If only ONI_API_KEY is set, it uses
https://api.openai.com/v1. Otherwise OPENAI_BASE_URL / OPENAI_API_BASE and
OPENAI_API_KEY form the generic pair. ONI_MODEL / OPENAI_MODEL select the model.
ONI_NO_LLM always disables this transport. Credentialed endpoints require HTTPS.
"""
import ipaddress
import http.client
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def _config():
    if os.environ.get("ONI_ENDPOINT"):
        base, key = os.environ["ONI_ENDPOINT"], os.environ.get("ONI_API_KEY", "")
    elif os.environ.get("ONI_API_KEY"):
        base, key = "https://api.openai.com/v1", os.environ["ONI_API_KEY"]
    else:
        base = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1"
        key = os.environ.get("OPENAI_API_KEY", "")
    return base.rstrip("/"), key


def _base():
    return _config()[0]


def _key():
    return _config()[1]


def model():
    return os.environ.get("ONI_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"


def _loopback(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def available():
    if os.environ.get("ONI_NO_LLM"):
        return False
    base, key = _config()
    try:
        url = urllib.parse.urlsplit(base)
        if url.username or url.password or url.query or url.fragment or not url.hostname:
            return False
        if url.scheme not in ("https", "http") or (key and url.scheme != "https"):
            return False
        # Unauthenticated HTTP is allowed only on the loopback host.
        return bool(key) or _loopback(url.hostname)
    except ValueError:
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def complete(prompt, system=None, max_tokens=1400, temperature=0.2, timeout=90):
    if not available():
        return None
    base, key = _config()
    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({"model": model(), "messages": messages,
                       "max_tokens": max_tokens, "temperature": temperature}).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(base + "/chat/completions", data=body, headers=headers)
    sys.stderr.write("oni: model request to %s\n" % urllib.parse.urlsplit(base).hostname)
    try:
        handlers = [_NoRedirect()]
        if _loopback(urllib.parse.urlsplit(base).hostname):
            handlers.append(urllib.request.ProxyHandler({}))
        with urllib.request.build_opener(*handlers).open(req, timeout=timeout) as response:
            payload = response.read(1024 * 1024 + 1)
        if len(payload) > 1024 * 1024:
            return None
        data = json.loads(payload)
        choices = data.get("choices") if isinstance(data, dict) else None
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return None
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):
            return content.strip() or None
        return None
    except (urllib.error.URLError, http.client.HTTPException, KeyError, ValueError,
            TypeError, OSError, RecursionError):
        return None
