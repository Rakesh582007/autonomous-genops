"""
agent.py
The agent "brain". Jobs:
  1. classify_message -> is this a deploy request or a general question?
  2. answer_question  -> conversational reply to non-deploy messages
  3. extract_intent   -> turn a deploy request into structured intent
  4. reasoning_trace  -> the visible chain-of-thought the UI shows
  5. speak            -> a natural-language reply for deploy requests

Uses Gemini if a key is configured; otherwise falls back to deterministic logic
so the demo never breaks.
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
            # gemini-flash-latest auto-points to the current fast model
            # (gemini-1.5-flash was shut down; this won't go stale).
            model = genai.GenerativeModel(config.GEMINI_MODEL)
            resp = model.generate_content(
                _INTENT_PROMPT.format(prompt=prompt),
                generation_config={"response_mime_type": "application/json"},
            )
            data = json.loads(resp.text.strip())
            return _normalize(data, prompt, "gemini")
        except Exception:
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


_SPEAK_PROMPT = """You are the Autonomous GenOps agent — a friendly, concise cloud
infrastructure assistant. A user asked: "{prompt}"

You parsed this intent: stack={stack}, TTL={ttl}h.
Policy verdict: compliant={compliant}{matched_part}.

Write a short, natural 2-3 sentence reply to the user, first person ("I"), as if you
are an AI agent talking to them. {tone}
Do NOT use markdown headers or bullet points. Just talk."""


def speak(prompt: str, intent: dict, verdict: dict) -> str:
    """A natural-language reply from the agent. Gemini if available, else templated."""
    key = config.GEMINI_API_KEY
    if key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            model = genai.GenerativeModel(config.GEMINI_MODEL)
            if verdict["compliant"]:
                tone = ("Confirm you understood, mention you've prepared a Terraform plan "
                        "and will show the environment impact for them to confirm.")
                matched_part = ""
            else:
                alt = verdict.get("alternative")
                tone = (f"Politely explain it's blocked for security and suggest "
                        f"'{alt}' as a compliant alternative." if alt else
                        "Politely explain it's blocked for security with no safe alternative.")
                matched_part = f", blocked on '{verdict.get('matched')}'"
            resp = model.generate_content(_SPEAK_PROMPT.format(
                prompt=prompt, stack=intent["stack"], ttl=intent["ttl_hours"],
                compliant=verdict["compliant"], matched_part=matched_part, tone=tone))
            txt = (resp.text or "").strip()
            if txt:
                return txt
        except Exception:
            pass

    # Templated fallback — still reads naturally.
    if verdict["compliant"]:
        return (f"Got it — I'll set up a {intent['stack']} sandbox with a "
                f"{intent['ttl_hours']}-hour lifespan. I've prepared the Terraform and "
                f"a preview of exactly what it'll create. Take a look below and confirm "
                f"when you're ready.")
    alt = verdict.get("alternative")
    if alt:
        return (f"I can't provision that — {verdict.get('matched')} is restricted by our "
                f"security policy. I'd suggest {alt} instead, which is approved and does "
                f"the same job securely. Want me to set that up?")
    return (f"I can't provision that — {verdict.get('matched')} is blocked by policy and "
            f"there's no compliant alternative I can offer here.")


# --------------------------------------------------------------------------- #
#  Router: is this a provisioning request, or a general question/greeting?
# --------------------------------------------------------------------------- #
_DEPLOY_VERBS = ["deploy", "provision", "spin up", "spin me", "set up", "setup",
                 "create", "launch", "build me", "boot", "stand up", "give me a",
                 "i need a", "i want a", "make me a"]

_CLASSIFY_PROMPT = """You route messages for a cloud-provisioning agent.
Classify the user's message as exactly one word:
- "deploy" if they are asking to create/provision/spin up an environment, sandbox,
  server, or piece of infrastructure (even casually).
- "question" if they are asking what you can do, how you work, greeting you, or
  anything that is NOT a request to actually build infrastructure.

Message: "{prompt}"
Answer with only one word: deploy OR question."""


def classify_message(prompt: str) -> str:
    """Return 'deploy' or 'question'. Gemini if available, else keyword heuristic."""
    key = config.GEMINI_API_KEY
    if key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            model = genai.GenerativeModel(config.GEMINI_MODEL)
            resp = model.generate_content(_CLASSIFY_PROMPT.format(prompt=prompt))
            ans = (resp.text or "").strip().lower()
            if "deploy" in ans:
                return "deploy"
            if "question" in ans:
                return "question"
        except Exception:
            pass
    # Heuristic fallback: question phrasing wins even if a deploy verb appears
    # ("what can you create for me?" is a question, not a deploy order).
    t = prompt.lower().strip()
    question_lead = ("what", "how", "who", "why", "when", "where", "can you",
                     "could you", "do you", "are you", "tell me", "explain",
                     "hi", "hey", "hello")
    if t.endswith("?") or t.startswith(question_lead):
        return "question"
    return "deploy" if any(v in t for v in _DEPLOY_VERBS) else "question"


_ANSWER_PROMPT = """You are the Autonomous GenOps agent — a friendly, concise cloud
infrastructure assistant. You help people provision secure, ephemeral cloud sandboxes
by describing them in plain English. You validate every request against an enterprise
security policy and can suggest compliant alternatives when something is restricted.

You can create sandboxes on these approved stacks: {stacks}.
Restricted examples you block (and the alternative you suggest): telnet -> openssh-server,
ftp -> sftp, teamviewer -> IAP. Crypto-mining and offensive tooling are hard-blocked.

The user said: "{prompt}"

Reply in 2-4 natural sentences, first person ("I"). If they asked what you can do,
explain briefly and invite them to describe what they need. Do NOT use markdown
headers or bullet points. Just talk."""


def answer_question(prompt: str, ledger: dict) -> str:
    """Conversational answer to a non-deploy message."""
    stacks = ", ".join(ledger.get("approved_stacks", []))
    key = config.GEMINI_API_KEY
    if key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            model = genai.GenerativeModel(config.GEMINI_MODEL)
            resp = model.generate_content(
                _ANSWER_PROMPT.format(prompt=prompt, stacks=stacks))
            txt = (resp.text or "").strip()
            if txt:
                return txt
        except Exception:
            pass
    # Templated fallback.
    return (f"I'm your GenOps provisioning agent — describe the environment you need in "
            f"plain English and I'll validate it against our security policy, show you the "
            f"impact, and provision it once you confirm. I can set up sandboxes on: {stacks}. "
            f"What would you like to build?")
