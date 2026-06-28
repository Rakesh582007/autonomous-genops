"""
plan_engine.py
The "show how it affects the environment" feature. This is conceptually
`terraform plan`: a diff of what will be created / changed / destroyed, plus
risk flags and an estimated cost — shown BEFORE anything is applied.

In DEMO mode this is computed deterministically from the intent. With real
creds + terraform installed you would swap simulate_plan() for a subprocess
call to `terraform plan -json` and parse the resource_changes.
"""


def simulate_plan(intent: dict, instance_name: str) -> dict:
    stack = intent.get("stack", "nginx")
    ttl = intent.get("ttl_hours", 1)

    create = [
        {
            "type": "google_compute_instance",
            "name": instance_name,
            "detail": f"e2-micro · us-central1-a · debian-11 · stack={stack}",
        },
        {
            "type": "google_compute_firewall",
            "name": f"{instance_name}-allow-http",
            "detail": "tcp:80 ingress from 0.0.0.0/0",
        },
    ]

    risks = [
        {
            "level": "medium",
            "msg": "Firewall opens port 80 to 0.0.0.0/0 (public internet). "
                   "Fine for an ephemeral sandbox; restrict source_ranges for production.",
        }
    ]
    if stack == "redis":
        risks.append({
            "level": "high",
            "msg": "Redis must run with a password (requirepass) and stay on a private "
                   "network. The generated config sets a placeholder — change it.",
        })

    # e2-micro ~ $6.11/mo on-demand; free-tier eligible in some regions.
    # TTL auto-destroy means real cost is a fraction of this.
    est_full_month = 6.11
    est_actual = round(est_full_month * (ttl / (24 * 30)), 4)

    return {
        "create": create,
        "change": [],
        "destroy": [],
        "risks": risks,
        "est_monthly_usd": est_full_month,
        "est_run_usd": est_actual,
        "ttl_hours": ttl,
    }
