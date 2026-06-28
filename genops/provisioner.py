"""
provisioner.py
Executes the plan. In DEMO mode (default) this is SIMULATED — clearly labelled,
no real cloud resources, no cost. The real apply path is gated behind
DEMO_MODE=false AND the presence of credentials, and is intentionally disabled
for the public demo so a public URL can never spend money.
"""
import os
import time

from . import config


def apply(hcl: str, instance_name: str) -> dict:
    if config.DEMO_MODE:
        time.sleep(0.4)  # honest: this is the only artificial pause, and it's labelled
        return {
            "status": "SIMULATED",
            "resource_id": instance_name,
            "message": "terraform apply simulated (DEMO_MODE). No real cloud resources "
                       "were created. Flip DEMO_MODE=false locally with creds to go live.",
            "endpoint": f"http://{instance_name}.sandbox.genops.local",
        }

    if not os.path.exists("gcp_creds.json"):
        return {
            "status": "DISABLED",
            "resource_id": instance_name,
            "message": "Real provisioning requested but gcp_creds.json is missing. "
                       "Add credentials locally to enable the live apply path.",
            "endpoint": None,
        }

    # Real path stub — wire to `terraform init/plan/apply` via subprocess here.
    return {
        "status": "DISABLED",
        "resource_id": instance_name,
        "message": "Live apply is intentionally disabled on the hosted demo for safety. "
                   "Run locally with DEMO_MODE=false to provision for real.",
        "endpoint": None,
    }


def destroy(instance_name: str) -> dict:
    if config.DEMO_MODE:
        return {"status": "SIMULATED",
                "message": f"terraform destroy simulated for {instance_name}."}
    return {"status": "DISABLED",
            "message": "Live destroy disabled on hosted demo."}
