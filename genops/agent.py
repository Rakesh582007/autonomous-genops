"""
agent.py
The agent "brain". Two jobs:
  1. extract_intent  -> turn a natural-language request into structured intent
  2. reasoning_trace -> produce the visible chain-of-thought the UI shows

Uses Gemini if a key is configured; otherwise falls back to a deterministic
heuristic so the demo never breaks.
"""
import json
import re
import random

from . import config

_KNOWN_STACKS = {
    "nodejs": "nodejs", "node": "nodejs",
    "python3": "python3", "python": "python3",
    "static-html": "static-html", "static": "static-html", "html": "static-html",
    "apache2": "apache2", "apache": "apache2",
    "postgresql": "postgresql", "postgres": "postgresql",
    "redis": "redis",
    "nginx": "nginx",
}

_INTENT_PROMPT = """You are an infrastructure intent parser for an enterprise GenOps agent.
Read the user's request and return STRICT JSON only, no prose:
{{"software": <main software/package mentioned or null>,
  "stack": <one of: nginx, nodejs, python3, static-html, apache2, postgresql, redis>,
  "purpose": <short summary of what they want>,
  "ttl_hours": <integer lifespan, default 1>}}

User request: "{prompt}"
"""


def gen_instance_name() -> str:
    return f"sandbox-{random.randint(1000, 9999)}"


def _heuristic_intent(prompt: str) -> dict:
    t = prompt.lower()
    stack = "nginx"
    for key, norm in _KNOWN_STACKS.items():
        if re.search(rf"\b{re.escape(key)}\b", t):
            stack = norm
            break

    ttl = 1
    m = re.search(r"(\d+)\s*(hour|hr|h\b|min|minute)", t)
    if m:
        val = int(m.group(1))
        ttl = val if "h" in m.group(2) else max(1, round(val / 60))

    software = None
    for token in ["telnet", "ftp", "teamviewer", "ngrok", "tor", "php5",
                  "python2", "nmap", "xmrig", "torrent", "metasploit"]:
        if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", t):
            software = token
            break

    return {
        "software": software,
        "stack": stack,
        "purpose": prompt.strip(),
        "ttl_hours": ttl,
        "_source": "heuristic",
        "raw": prompt,
    }


def _normalize(data: dict, prompt: str, source: str) -> dict:
    stack = (data.get("stack") or "nginx").lower()
    if stack not in _KNOWN_STACKS.values():
        stack = "nginx"
    try:
        ttl = int(data.get("ttl_hours") or 1)
    except (TypeError, ValueError):
        ttl = 1
    return {
        "software": data.get("software"),
        "stack": stack,
        "purpose": data.get("purpose") or prompt.strip(),
        "ttl_hours": max(1, ttl),
        "_source": source,
        "raw": prompt,
    }


def extract_intent(prompt: str) -> dict:
    """Structured intent from natural language. Gemini if available, else heuristic."""
    key = config.GEMINI_API_KEY
    if key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            resp = model.generate_content(
                _INTENT_PROMPT.format(prompt=prompt),
                generation_config={"response_mime_type": "application/json"},
            )
            data = json.loads(resp.text.strip())
            return _normalize(data, prompt, "gemini")
        except Exception:
            # Any API hiccup -> deterministic fallback. The demo stays alive,
            # but unlike the old code this fallback does NOT weaken the policy check.
            pass
    return _heuristic_intent(prompt)


def reasoning_trace(intent: dict, verdict: dict) -> list:
    """The visible 'thinking' the UI renders, so it reads like an agent."""
    steps = [
        f"Parsed request → stack `{intent['stack']}`, TTL {intent['ttl_hours']}h "
        f"(source: {intent['_source']}).",
        "Validated request against the Enterprise Ledger (policy.json).",
    ]
    if verdict["compliant"]:
        steps.append("No restricted software or prohibited category matched → ✅ compliant.")
        steps.append("Generating Terraform (google_compute_instance + firewall).")
        steps.append("Running plan to preview environment impact BEFORE any change.")
        steps.append("Holding for human confirmation before apply (agentic safety gate).")
    else:
        steps.append(
            f"Matched policy rule on `{verdict.get('matched')}` "
            f"(severity: {verdict['severity']}) → ❌ blocked."
        )
        if verdict.get("alternative"):
            steps.append(f"Resolved a compliant alternative: {verdict['alternative']}.")
        else:
            steps.append("No compliant alternative exists for this category — hard stop.")
    return steps
