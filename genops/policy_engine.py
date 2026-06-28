"""
policy_engine.py
The Policy-as-Code engine. Reads the enterprise ledger (policy.json) and returns
a structured verdict for any request, including WHY it was blocked and a
compliant ALTERNATIVE to suggest. This replaces the old substring check.
"""
import json
import re


def load_policy(path: str = "policy.json") -> dict:
    with open(path, "r") as f:
        return json.load(f)


def _mentions(term: str, text: str) -> bool:
    """Whole-word match so 'tor' does NOT fire on 'inventory'."""
    return re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])", text) is not None


def evaluate(text: str, ledger: dict) -> dict:
    """
    Evaluate a request string against the ledger.
    Returns: {compliant, tier, severity, matched, reason, alternative, alternative_note}
    """
    t = (text or "").lower()

    # Tier 1 — hard-prohibited categories (no compliant alternative exists)
    for cat in ledger.get("prohibited_categories", []):
        for kw in cat.get("keywords", []):
            if _mentions(kw, t):
                return {
                    "compliant": False,
                    "tier": "prohibited",
                    "severity": cat.get("severity", "critical"),
                    "matched": kw,
                    "reason": cat.get("reason", "Prohibited category."),
                    "alternative": cat.get("suggested_alternative"),
                    "alternative_note": "",
                }

    # Tier 2 — restricted software (blocked, but a compliant alternative exists)
    for item in ledger.get("restricted_software", []):
        names = [item["name"]] + item.get("aliases", [])
        for n in names:
            if _mentions(n, t):
                return {
                    "compliant": False,
                    "tier": "restricted",
                    "severity": item.get("severity", "medium"),
                    "matched": item["name"],
                    "reason": item.get("reason", "Restricted by policy."),
                    "alternative": item.get("suggested_alternative"),
                    "alternative_note": item.get("alternative_note", ""),
                }

    # Default — compliant
    return {
        "compliant": True,
        "tier": "approved",
        "severity": "none",
        "matched": None,
        "reason": "Request maps to approved baseline stacks. No restricted software detected.",
        "alternative": None,
        "alternative_note": "",
    }


def format_block_message(verdict: dict) -> str:
    """Human-readable block message with suggestion."""
    base = f"'{verdict.get('matched')}' is not compliant with InfoSec policy " \
           f"(severity: {verdict.get('severity')}). {verdict.get('reason')}"
    if verdict.get("alternative"):
        base += f" Suggested compliant alternative: {verdict['alternative']}. " \
                f"{verdict.get('alternative_note', '')}"
    return base.strip()
