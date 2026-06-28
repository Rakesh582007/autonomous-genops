"""
dashboard.py
Conversational front-end for Autonomous GenOps. Run:  streamlit run dashboard.py

Flow per message:
  classify (question vs deploy)
   - question -> answer conversationally
   - deploy   -> validate (policy) -> generate TF + preview impact
                 -> wait for human confirm -> apply (simulated in DEMO mode).
"""
import streamlit as st

from genops import config
from genops.policy_engine import load_policy, evaluate
from genops.agent import (extract_intent, reasoning_trace, gen_instance_name,
                          speak, classify_message, answer_question)
from genops.terraform_gen import generate_hcl
from genops.plan_engine import simulate_plan
from genops.provisioner import apply
from genops.metrics import Timer, log_audit, ts

st.set_page_config(page_title="Autonomous GenOps", page_icon="🧠", layout="wide")

LEDGER = load_policy(config.POLICY_PATH)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending" not in st.session_state:
    st.session_state.pending = None


# ----------------------------- rendering ----------------------------------- #
def render_message(m: dict):
    kind = m["kind"]

    if kind == "text":
        st.markdown(m["text"])

    elif kind == "blocked":
        v = m["payload"]
        if m.get("say"):
            st.markdown(m["say"])
        st.error(f"❌ Blocked by InfoSec policy — matched `{v.get('matched')}` "
                 f"(severity: {v.get('severity')})")
        st.markdown(f"**Why:** {v['reason']}")
        if v.get("alternative"):
            note = v.get("alternative_note", "")
            st.success(f"✅ Suggested compliant alternative: **{v['alternative']}** — {note}")
        else:
            st.markdown("_No compliant alternative exists for this category._")
        with st.expander("🧠 Agent reasoning"):
            for s in m.get("trace", []):
                st.markdown(f"- {s}")

    elif kind == "result":
        p = m["payload"]
        plan = p["plan"]
        intent = p["intent"]
        if p.get("say"):
            st.markdown(p["say"])
        st.markdown(f"**Plan ready for `{p['instance_name']}`** — stack "
                    f"`{intent['stack']}`, TTL {intent['ttl_hours']}h.")
        with st.expander("🧠 Agent reasoning", expanded=False):
            for s in p["trace"]:
                st.markdown(f"- {s}")

        st.markdown("#### 🌍 Environment Impact Preview")
        c1, c2, c3 = st.columns(3)
        c1.metric("➕ Create", len(plan["create"]))
        c2.metric("✏️ Change", len(plan["change"]))
        c3.metric("➖ Destroy", len(plan["destroy"]))
        for r in plan["create"]:
            st.markdown(f"- ➕ `{r['type']}` · **{r['name']}** — {r['detail']}")
        for risk in plan["risks"]:
            st.warning(f"⚠️ [{risk['level'].upper()}] {risk['msg']}")
        st.info(f"💰 On-demand ≈ ${plan['est_monthly_usd']}/mo · this run ≈ "
                f"${plan['est_run_usd']} (auto-destroy after {plan['ttl_hours']}h via TTL)")
        with st.expander("📄 Generated Terraform (main.tf)"):
            st.code(p["hcl"], language="hcl")

    elif kind == "applied":
        r = m["payload"]
        if r["status"] == "SIMULATED":
            st.success(f"🎉 {r['message']}")
            st.markdown(f"**Resource:** `{r['resource_id']}` · "
                        f"**Endpoint:** `{r['endpoint']}`")
        else:
            st.info(r["message"])


# ------------------------------- sidebar ----------------------------------- #
with st.sidebar:
    st.header("⚙️ Control Plane")
    st.metric("Execution Mode",
              "🟡 DEMO (simulated)" if config.DEMO_MODE else "🟢 LIVE (real apply)")
    st.metric("Agent Brain",
              "Gemini LLM" if config.GEMINI_API_KEY else "Heuristic (no key)")
    with st.expander("✅ Approved stacks"):
        st.write(", ".join(LEDGER.get("approved_stacks", [])))
    with st.expander("⛔ Restricted (sample)"):
        for it in LEDGER.get("restricted_software", [])[:6]:
            alt = it.get("suggested_alternative") or "blocked"
            st.write(f"• **{it['name']}** → {alt}")
    if st.button("🗑️ Reset conversation"):
        st.session_state.messages = []
        st.session_state.pending = None
        st.rerun()


# -------------------------------- header ----------------------------------- #
st.title("🧠 Autonomous GenOps Provisioner")
st.caption("Describe infrastructure in plain English. The agent validates it against "
           "enterprise policy, previews the blast radius, and provisions — only after you confirm.")

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        render_message(m)


# ------------------------------ input loop --------------------------------- #
prompt = st.chat_input("e.g., Deploy an nginx sandbox for the inventory app for 2 hours")
if prompt:
    st.session_state.messages.append({"role": "user", "kind": "text", "text": prompt})

    with st.chat_message("assistant"):
        with st.status("🧠 Agent working…", expanded=True) as status:
            with Timer() as t:
                st.write("Reading your message…")
                kind = classify_message(prompt)

                if kind == "question":
                    st.write("Answering your question…")
                    reply = answer_question(prompt, LEDGER)
                    status.update(label="💬 Replied", state="complete")
                    msg = {"role": "assistant", "kind": "text", "text": reply}
                    st.session_state.messages.append(msg)
                    st.rerun()

                st.write("Parsing conversational intent…")
                intent = extract_intent(prompt)
                st.write(f"→ stack `{intent['stack']}`, TTL {intent['ttl_hours']}h "
                         f"({intent['_source']})")
                st.write("Validating against Enterprise Ledger…")
                scan_text = f"{prompt} {intent.get('software') or ''}"
                verdict = evaluate(scan_text, LEDGER)
                trace = reasoning_trace(intent, verdict)
            dur = t.elapsed
            mode = "demo" if config.DEMO_MODE else "live"

            if not verdict["compliant"]:
                status.update(label="❌ Blocked by policy", state="error")
                say = speak(prompt, intent, verdict)
                msg = {"role": "assistant", "kind": "blocked",
                       "payload": verdict, "trace": trace, "say": say}
                log_audit([ts(), "-", intent["stack"], "BLOCKED", dur, mode])
            else:
                st.write("Generating Terraform & planning impact…")
                name = gen_instance_name()
                hcl = generate_hcl(intent, name)
                plan = simulate_plan(intent, name)
                say = speak(prompt, intent, verdict)
                status.update(label="✅ Compliant — plan ready", state="complete")
                payload = {"intent": intent, "verdict": verdict, "trace": trace,
                           "hcl": hcl, "plan": plan, "instance_name": name, "say": say}
                msg = {"role": "assistant", "kind": "result", "payload": payload}
                st.session_state.pending = payload
                log_audit([ts(), name, intent["stack"], "APPROVED", dur, mode])

    st.session_state.messages.append(msg)
    st.rerun()


# --------------------------- confirmation gate ----------------------------- #
if st.session_state.pending:
    p = st.session_state.pending
    st.markdown("---")
    st.markdown(f"#### ⚡ Ready to provision `{p['instance_name']}` "
                f"({p['intent']['stack']})")
    col1, col2 = st.columns(2)
    if col1.button("✅ Confirm & Provision", type="primary", use_container_width=True):
        result = apply(p["hcl"], p["instance_name"])
        st.session_state.messages.append(
            {"role": "assistant", "kind": "applied", "payload": result})
        st.session_state.pending = None
        st.rerun()
    if col2.button("✋ Cancel", use_container_width=True):
        st.session_state.messages.append(
            {"role": "assistant", "kind": "text",
             "text": "Provisioning cancelled. No changes made."})
        st.session_state.pending = None
        st.rerun()
