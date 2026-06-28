# 🧠 Autonomous GenOps Provisioner

**Democratizing enterprise infrastructure via intent-driven AI provisioning.**

A conversational agent that lets anyone (PM, analyst, intern) request a cloud
sandbox in plain English. The agent extracts intent, validates it against an
enterprise security policy (Policy-as-Code), generates real Terraform, **previews
the environment impact before touching anything**, and provisions only after a
human confirms.

> Prototype runs in **DEMO mode** by default: provisioning is *simulated*, so the
> public live URL costs nothing and exposes no credentials.

---

## What it does (per request)

1. **Understand** — natural-language request → structured intent (Gemini LLM, or a
   deterministic fallback so the demo never breaks).
2. **Validate** — checked against `policy.json`. Restricted software is blocked
   *with a reason and a suggested compliant alternative* (e.g. `telnet → openssh-server`).
3. **Design** — generates real Terraform (`google_compute_instance` + firewall).
4. **Preview impact** — a `terraform plan`–style diff: what will be created /
   changed / destroyed, risk flags, and estimated cost. *This is the "how will it
   affect the environment" view.*
5. **Confirm** — waits for explicit human approval (agentic safety gate).
6. **Provision** — simulated in DEMO mode; real apply path is gated for local use.

---

## How it maps to the Round-2 evaluation criteria

| Criterion | Where it shows up |
|---|---|
| **Working Model / Core Functionality** | Full chat loop, live policy verdicts, plan preview, confirm-and-provision. |
| **Technical Execution** | Modular package (`config`, `policy_engine`, `agent`, `terraform_gen`, `plan_engine`, `provisioner`, `metrics`), no hardcoded secrets, tested. |
| **User Experience / Interface** | Conversational UI, visible agent reasoning, impact preview, one-click confirm. |
| **Scalability & Integration** | Policy-as-Code ledger, real Terraform output, pluggable LLM brain, audit log. |
| **Progress from Round 1** | Directly realizes the architecture diagram: NL input → LLM orchestrator → Enterprise Ledger → Terraform gen → plan → endpoint. |

---

## Run locally

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

Works with no API key (heuristic brain). For LLM reasoning, set a key:

```bash
export GEMINI_API_KEY=your_key_here   # optional
streamlit run dashboard.py
```

Try: *"Deploy an nginx sandbox for the inventory app for 2 hours"* (approved) and
*"set up a telnet server"* (blocked → suggests openssh-server).

---

## Push to GitHub

```bash
cd autonomous-genops
git init
git add .
git commit -m "Autonomous GenOps prototype"
git branch -M main
git remote add origin https://github.com/<your-username>/autonomous-genops.git
git push -u origin main
```

`.gitignore` already excludes secrets, creds, and the metrics log.

---

## Get your LIVE URL (free)

1. Go to **share.streamlit.io** → sign in with GitHub.
2. **New app** → pick your `autonomous-genops` repo, branch `main`, main file
   `dashboard.py`.
3. *(Optional)* Settings → **Secrets**, add:
   ```toml
   DEMO_MODE = "true"
   # GEMINI_API_KEY = "your_key"   # only if you want live LLM reasoning
   ```
4. **Deploy.** You get a public URL like
   `https://autonomous-genops.streamlit.app` — paste that into your Unstop submission.

Keep `DEMO_MODE = "true"` for the public URL so it never provisions real cloud
resources.

---

## Security

- No API keys or cloud credentials are committed. Secrets load from environment
  variables or Streamlit secrets only.
- The public demo cannot spend money: real `terraform apply` is gated behind
  `DEMO_MODE=false` **and** local credentials.

## Going further (real provisioning, post-submission)

Set `DEMO_MODE=false`, add `gcp_creds.json` locally, and wire `provisioner.apply`
to `terraform init/plan/apply` via subprocess. The generated HCL is already valid.
