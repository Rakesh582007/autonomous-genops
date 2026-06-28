"""
config.py
Central configuration. Secrets are read from environment variables or Streamlit
secrets — NEVER hardcoded. This is what keeps the public repo safe.
"""
import os

try:
    import streamlit as st
    _HAS_ST = True
except Exception:
    _HAS_ST = False


def get_secret(name: str, default=None):
    """Read a secret from Streamlit secrets first, then env vars."""
    if _HAS_ST:
        try:
            if name in st.secrets:
                return st.secrets[name]
        except Exception:
            pass
    return os.environ.get(name, default)


# Gemini key is OPTIONAL. If absent, the agent falls back to a deterministic
# heuristic brain so the live demo always works.
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")

# DEMO_MODE=true  -> provisioning is simulated (safe for public demo, no cloud cost)
# DEMO_MODE=false -> real terraform apply path (only enable locally with creds)
DEMO_MODE = str(get_secret("DEMO_MODE", "true")).lower() in ("1", "true", "yes")

POLICY_PATH = get_secret("POLICY_PATH", "policy.json")
