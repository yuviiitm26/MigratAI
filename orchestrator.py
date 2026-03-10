# ==========================================================
# MigratAI - Step-by-Step Sequential A2A Pipeline
# 
# AGENT EXECUTION ORDER:
# Step 1 → Architect    : Generate Dockerfile + Bicep
# Step 2 → Risk_Analyst : Security scan + Governance score
# Step 3 → Sentry       : Docker build (local)
# Step 4 → Sentry       : Docker push (Docker Hub)
# Step 5 → Sentry       : Azure infrastructure deploy
# Step 6 → Governance_Officer : Final human sign-off at each gate
# ==========================================================

import os
import sys
import re
import json
import logging
import subprocess
import requests
from pathlib import Path
from datetime import datetime

import autogen
from dotenv import load_dotenv

try:
    from ast_parser import extract_architecture
except ImportError:
    def extract_architecture(file): return "Flask App with SQLite and Templates"

# ==========================================================
# 1. CONFIGURATION
# ==========================================================

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

REQUIRED_ENV = [
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT_NAME",
]

OUTPUT_DIR        = Path("azure_migration_output")
DOCKERFILE        = OUTPUT_DIR / "Dockerfile"
BICEP_FILE        = OUTPUT_DIR / "main.bicep"
AUDIT_LOG         = OUTPUT_DIR / "audit_log.json"
GOVERNANCE_REPORT = OUTPUT_DIR / "governance_report.json"
STEP_LOG          = OUTPUT_DIR / "step_log.json"

MAX_COST_PER_VCPU        = 0.10
MIN_CONFIDENCE_TO_DEPLOY = 50
MAX_REMEDIATION_LOOPS    = 3
COMPLEXITY_TAX           = 5 * 2

# Global step tracker — visible to all agents via tool
PIPELINE_STEPS = {
    "step_1_architect":    {"status": "pending", "label": "Generate Dockerfile + Bicep"},
    "step_2_risk":         {"status": "pending", "label": "Security Scan + Governance Score"},
    "step_3_docker_build": {"status": "pending", "label": "Docker Build (Local)"},
    "step_4_docker_push":  {"status": "pending", "label": "Docker Push (Docker Hub)"},
    "step_5_azure_deploy": {"status": "pending", "label": "Azure Infrastructure Deploy"},
}

def validate_env():
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        logging.critical(f"❌ Missing env vars: {missing}")
        sys.exit(1)

OUTPUT_DIR.mkdir(exist_ok=True)

llm_config = {
    "config_list": [{
        "model":          os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        "api_key":        os.getenv("AZURE_OPENAI_API_KEY"),
        "azure_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "api_type":       "azure",
        "api_version":    os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    }],
    "temperature": 0.0,
}

# ==========================================================
# 2. PIPELINE STEP TRACKER (Shared state across agents)
# ==========================================================

def update_step(step_key: str, status: str, detail: str = "") -> str:
    """
    Agent Tool — Updates the live pipeline step tracker.
    status options: 'running' | 'passed' | 'failed' | 'skipped'
    Called by: Any agent at the start/end of their step.
    """
    icons = {"running": "🔄", "passed": "✅", "failed": "❌", "skipped": "⏭️", "pending": "⏳"}
    if step_key not in PIPELINE_STEPS:
        return f"ERROR: Unknown step key '{step_key}'"

    PIPELINE_STEPS[step_key]["status"] = status
    if detail:
        PIPELINE_STEPS[step_key]["detail"] = detail
    PIPELINE_STEPS[step_key]["updated_at"] = datetime.utcnow().isoformat()

    # Render full pipeline board
    lines = ["\n┌─────────────────────────────────────────────────┐"]
    lines.append(  "│         MIGRATAI PIPELINE STATUS BOARD          │")
    lines.append(  "├─────────────────────────────────────────────────┤")
    for key, val in PIPELINE_STEPS.items():
        icon  = icons.get(val["status"], "❓")
        label = val["label"]
        st    = val["status"].upper().ljust(8)
        lines.append(f"│  {icon}  {label:<34} [{st}] │")
    lines.append(  "└─────────────────────────────────────────────────┘")

    board = "\n".join(lines)
    logging.info(board)

    # Persist step log
    with open(STEP_LOG, "w") as f:
        json.dump(PIPELINE_STEPS, f, indent=2)

    return f"SUCCESS: Step '{step_key}' marked as '{status}'.\n{board}"


def get_pipeline_status() -> str:
    """Agent Tool — Returns the current pipeline status board."""
    return update_step(list(PIPELINE_STEPS.keys())[0],
                       PIPELINE_STEPS[list(PIPELINE_STEPS.keys())[0]]["status"])


# ==========================================================
# 3. DETERMINISTIC TOOL LAYER
# ==========================================================

def get_folder_structure(root_dir: str = "./code") -> str:
    """Returns a visual directory tree of the target code folder."""
    if not os.path.exists(root_dir):
        return "❌ Directory not found."
    tree = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [
            d for d in dirs
            if d not in ('.git', 'venv', '__pycache__') and not d.startswith('.')
        ]
        level  = root.replace(root_dir, '').count(os.sep)
        tree.append(f"{' ' * 4 * level}📁 {os.path.basename(root) or 'code'}/")
        for f in files:
            tree.append(f"{' ' * 4 * (level + 1)}📄 {f}")
    return "\n".join(tree)


def save_infrastructure_code(docker_code: str, bicep_code: str) -> str:
    """
    Agent Tool — Saves Dockerfile and Bicep to disk.
    Auto-fixes trailing commas (common LLM hallucination).
    Called by: Architect  |  Step: 1
    """
    try:
        bicep_code = re.sub(r',\s*}', '}', bicep_code)
        bicep_code = re.sub(r',\s*]', ']', bicep_code)

        with open(DOCKERFILE, "w") as f:
            f.write(docker_code.strip())
        with open(BICEP_FILE, "w") as f:
            f.write(bicep_code.strip())

        update_step("step_1_architect", "passed", "Dockerfile + main.bicep written to disk")
        logging.info("✅ [STEP 1] Artifacts saved: Dockerfile + main.bicep")
        return (
            "SUCCESS: Dockerfile and main.bicep saved to azure_migration_output/.\n"
            "NEXT STEP: Risk_Analyst, please begin Step 2 — run the governance assessment."
        )
    except Exception as e:
        update_step("step_1_architect", "failed", str(e))
        return f"ERROR: {str(e)}"


def run_risk_assessment(region: str) -> str:
    """
    Agent Tool — Security scan + cost estimate + risk scoring.
    Called by: Risk_Analyst  |  Step: 2
    """
    update_step("step_2_risk", "running")

    # ── Checkov Security Scan ────────────────────────────
    violations, high_sev = [], 0
    if not BICEP_FILE.exists():
        violations = [{"id": "FILE_MISSING", "name": "main.bicep not found"}]
        high_sev   = 1
    else:
        try:
            proc = subprocess.run(
                ["checkov", "-f", str(BICEP_FILE), "--output", "json", "--quiet"],
                capture_output=True, text=True
            )
            raw = proc.stdout.strip()
            if raw:
                data   = json.loads(raw)
                if isinstance(data, list): data = data[0]
                failed = data.get("results", {}).get("failed_checks", [])
                violations = [
                    {"id": c.get("check_id"), "name": c.get("check_name")}
                    for c in failed
                ]
                high_sev = sum(
                    1 for c in failed
                    if any(k in c.get("check_id", "")
                           for k in ["CKV_AZURE_227", "CKV_AZURE_167"])
                )
        except Exception as e:
            violations = [{"id": "PARSE_ERR", "name": str(e)}]
            high_sev   = 1

    # ── Azure Live Cost Estimate ─────────────────────────
    cost_val, cost_ok = 0.0, False
    try:
        url = (
            f"https://prices.azure.com/api/retail/prices"
            f"?$filter=armRegionName eq '{region}' "
            f"and serviceName eq 'Azure Container Apps'"
        )
        items = requests.get(url, timeout=10).json().get("Items", [])
        for item in items:
            if "vCPU" in item.get("meterName", ""):
                cost_val = float(item["retailPrice"])
                cost_ok  = True
                break
    except Exception:
        pass

    # ── Risk Formula ─────────────────────────────────────
    security_risk    = (len(violations) * 4) + (high_sev * 20)
    cost_risk        = 0.0
    if cost_ok and cost_val > MAX_COST_PER_VCPU:
        overage      = (cost_val - MAX_COST_PER_VCPU) / MAX_COST_PER_VCPU
        cost_risk    = min(overage * 50, 40)
    total_risk       = security_risk + cost_risk + COMPLEXITY_TAX
    risk_score       = int(min(total_risk, 100))
    confidence_score = 100 - risk_score
    if high_sev > 0:
        confidence_score = min(confidence_score, 50)

    allowed = confidence_score >= MIN_CONFIDENCE_TO_DEPLOY

    report = {
        "timestamp":   datetime.utcnow().isoformat(),
        "region":      region,
        "security":    {"violations": violations, "high_severity": high_sev, "passed": len(violations) == 0},
        "cost":        {"vcpu_hourly_usd": cost_val if cost_ok else "unavailable",
                        "threshold_usd": MAX_COST_PER_VCPU,
                        "within_budget": (cost_val <= MAX_COST_PER_VCPU) if cost_ok else "unknown"},
        "scores":      {"risk_score": risk_score, "confidence_score": confidence_score},
        "deployment_allowed": allowed,
    }

    with open(GOVERNANCE_REPORT, "w") as f:
        json.dump(report, f, indent=2)

    step_status = "passed" if allowed else "failed"
    update_step("step_2_risk", step_status,
                f"Risk={risk_score} | Confidence={confidence_score} | Allowed={allowed}")

    return json.dumps(report, indent=2)


def docker_build(dockerhub_username: str, app_name: str) -> str:
    """
    Agent Tool — Builds the Docker image LOCALLY from ./code folder.
    Called by: Sentry  |  Step: 3
    """
    update_step("step_3_docker_build", "running")
    tag     = f"{dockerhub_username}/{app_name}:latest"
    command = f"docker build -t {tag} -f {DOCKERFILE} ./code"

    logging.info(f"🐳 [STEP 3] Building Docker image: {tag}")
    logging.info(f"   Command: {command}")

    try:
        result = subprocess.run(
            command, shell=True,
            capture_output=True, text=True, timeout=600
        )
        if result.returncode == 0:
            update_step("step_3_docker_build", "passed", f"Image built: {tag}")
            return (
                f"SUCCESS: Docker image '{tag}' built locally.\n"
                f"Build output:\n{result.stdout[-1000:]}\n"   # last 1000 chars
                f"NEXT STEP: Sentry, proceed to Step 4 — push the image to Docker Hub."
            )
        else:
            update_step("step_3_docker_build", "failed", result.stderr[:300])
            return f"FAILURE: Docker build failed.\n{result.stderr}"
    except subprocess.TimeoutExpired:
        update_step("step_3_docker_build", "failed", "Build timed out")
        return "FAILURE: Docker build timed out after 600 seconds."
    except Exception as e:
        update_step("step_3_docker_build", "failed", str(e))
        return f"CRITICAL ERROR: {str(e)}"


def docker_push(dockerhub_username: str, app_name: str) -> str:
    """
    Agent Tool — Pushes the locally built image to Docker Hub.
    Requires: user must be logged in via 'docker login' before this runs.
    Called by: Sentry  |  Step: 4
    """
    update_step("step_4_docker_push", "running")
    tag     = f"{dockerhub_username}/{app_name}:latest"
    command = f"docker push {tag}"

    logging.info(f"📤 [STEP 4] Pushing Docker image to Docker Hub: {tag}")
    logging.info(f"   Command: {command}")

    try:
        result = subprocess.run(
            command, shell=True,
            capture_output=True, text=True, timeout=600
        )
        if result.returncode == 0:
            update_step("step_4_docker_push", "passed", f"Pushed: {tag}")
            return (
                f"SUCCESS: Image '{tag}' pushed to Docker Hub.\n"
                f"Push output:\n{result.stdout[-500:]}\n"
                f"NEXT STEP: Sentry, proceed to Step 5 — deploy Azure infrastructure."
            )
        else:
            err = result.stderr or result.stdout
            update_step("step_4_docker_push", "failed", err[:300])
            # Detect Docker Hub auth failure
            if "denied" in err.lower() or "unauthorized" in err.lower():
                return (
                    "FAILURE: Docker Hub authentication failed.\n"
                    "ACTION REQUIRED: Ask Governance_Officer to run 'docker login' "
                    "in their terminal, then type 'retry_push' to continue."
                )
            return f"FAILURE: Docker push failed.\n{err}"
    except subprocess.TimeoutExpired:
        update_step("step_4_docker_push", "failed", "Push timed out")
        return "FAILURE: Docker push timed out after 600 seconds."
    except Exception as e:
        update_step("step_4_docker_push", "failed", str(e))
        return f"CRITICAL ERROR: {str(e)}"


def azure_deploy(app_name: str, dockerhub_username: str, region: str) -> str:
    """
    Agent Tool — Deploys the infrastructure to Azure Container Instances.
    """
    update_step("step_5_azure_deploy", "running")
    
    rg = "MigratAI-RG" 
    container_name = f"{app_name}-app-v4"
    dns_label = f"migratai-demo-{app_name}-v4"
    image = f"{dockerhub_username}/{app_name}:latest"

    # 1. Pull the password from environment variables safely
    docker_password = os.getenv("DOCKER_PASSWORD") 
    if not docker_password:
        return "FAILURE: DOCKER_PASSWORD environment variable not set."

    # 2. Construct the command as a SINGLE STRING (Fix for the fake success bug)
    command = (
        f"az container create "
        f"--resource-group {rg} "
        f"--name {container_name} "
        f"--image {image} "
        f"--dns-name-label {dns_label} "
        f"--ports 5000 "
        f"--os-type Linux "
        f"--cpu 1 "
        f"--memory 1.5 "
        f"--location {region} "
        f"--registry-login-server index.docker.io "
        f"--registry-username {dockerhub_username} "
        f"--registry-password {docker_password}"
    )

    logging.info(f"☁️  [STEP 5] Deploying to Azure — RG: {rg} | Image: {image}")
    logging.info(f"   Command: {command}")

    try:
        result = subprocess.run(
            command, shell=True,
            capture_output=True, text=True, timeout=900
        )
        if result.returncode == 0:
            update_step("step_5_azure_deploy", "passed", f"Deployed {app_name} to {rg}")
            
            # Fix 3: Generate the correct Azure Container Instances URL
            correct_url = f"http://{dns_label}.{region}.azurecontainer.io:5000"
            
            return (
                f"SUCCESS: Azure deployment complete.\n"
                f"App URL: {correct_url}\n"
                f"Output:\n{result.stdout[-500:]}"
            )
        else:
            err = result.stderr or result.stdout
            update_step("step_5_azure_deploy", "failed", err[:300])

            # Smart error diagnosis for Environment/RG issues
            if "ResourceGroupNotFound" in err:
                return (
                    f"FAILURE: Resource group '{rg}' not found.\n"
                    f"AUTO-FIX: Run → az group create --name {rg} --location {region}\n"
                    f"Then call azure_deploy again."
                )
            
            if "UNAUTHORIZED" in err or "authentication" in err.lower():
                return (
                    "FAILURE: Azure CLI not authenticated.\n"
                    "AUTO-FIX: Run → az login\n"
                    "Then call azure_deploy again."
                )
            
            return f"FAILURE: Azure deployment failed.\n{err}"

    except subprocess.TimeoutExpired:
        update_step("step_5_azure_deploy", "failed", "Deploy timed out")
        return "FAILURE: Azure deployment timed out after 900 seconds."
    except Exception as e:
        update_step("step_5_azure_deploy", "failed", str(e))
        return f"CRITICAL ERROR: {str(e)}"
def execute_bash_command(command: str) -> str:
    """
    Agent Tool — Generic CLI executor for one-off fix commands.
    (az group create, az login, docker login, etc.)
    Called by: Sentry for auto-fix commands only.
    """
    logging.info(f"🔧 [FIX] Running: {command}")
    try:
        result = subprocess.run(
            command, shell=True,
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return f"SUCCESS:\n{result.stdout}"
        else:
            return f"FAILURE:\n{result.stderr or result.stdout}"
    except Exception as e:
        return f"CRITICAL ERROR: {str(e)}"


def save_audit_trail(messages: list) -> None:
    """Persists the full agent conversation to an audit log."""
    try:
        with open(AUDIT_LOG, "w") as f:
            json.dump(messages, f, indent=2)
        logging.info(f"📋 Audit trail → {AUDIT_LOG}")
    except Exception as e:
        logging.warning(f"⚠️ Audit trail save failed: {e}")


# ==========================================================
# 4. TERMINATION
# ==========================================================

def is_termination_msg(x):
    return isinstance(x, dict) and "TERMINATE" in str(x.get("content", "")).upper()


# ==========================================================
# 5. AGENT DEFINITIONS
# ==========================================================

# ── Agent 1: Human Governance Officer ──────────────────────
governance_officer = autogen.UserProxyAgent(
    name="Governance_Officer",
    system_message="""You are the Human Governance Officer.
    You are shown the pipeline board at each gate.
    Respond ONLY when Sentry asks for your input:
    - 'approve'      → proceed to next step
    - 'redo'         → ask Architect to regenerate artefacts
    - 'retry_push'   → retry the Docker Hub push (after docker login)
    - 'abort'        → cancel the migration entirely""",
    human_input_mode="ALWAYS",
    is_termination_msg=is_termination_msg,
    code_execution_config=False,
)


# ── Agent 2: Silent CI/CD Pipeline Executor ────────────────
cicd_pipeline = autogen.UserProxyAgent(
    name="CICD_Pipeline",
    system_message=(
        "You are the automated CI/CD pipeline executor. "
        "Run every tool call from Architect, Risk_Analyst, and Sentry "
        "immediately and silently. Do not add commentary."
    ),
    human_input_mode="NEVER",
    is_termination_msg=is_termination_msg,
    code_execution_config={"use_docker": False},
)


# ── Agent 3: Cloud Architect ───────────────────────────────
architect = autogen.AssistantAgent(
    name="Architect",
    llm_config=llm_config,
    system_message="""You are a Senior Azure Cloud Architect.
    CRITICAL SCHEMA RULE: Azure Container Apps requires memory in 'Gi' units. However, for this migration, if you receive a 'ContainerAppInvalidSchema' error, you must immediately pivot.

    Abandon the Bicep template.

    Direct the Sentry agent to use the az container create command.

    Set CPU to 1 and Memory to 1.5.

    Do not wrap numbers in json() functions.
    BICEP (Microsoft.ContainerInstance/containerGroups ONLY):
- Do NOT use Microsoft.App/containerApps.
- Use 'Microsoft.ContainerInstance/containerGroups@2021-10-01'.
- cpu: 1
- memory: json('1.5')  <-- For ACI, this format IS correct.
- osType: 'Linux'
- ipAddress: {
    type: 'Public'
    dnsNameLabel: 'migratai-demo-${containerAppName}'
    ports: [{ port: 5000, protocol: 'TCP' }]
  }
- No placeholders like <subscription-id>.

    ═══ STEP 1 OF 5: GENERATE INFRASTRUCTURE CODE ═══

    DOCKERFILE (exact):
    ┌─────────────────────────────────────────┐
    │ FROM python:3.9-slim                    │
    │ WORKDIR /app                            │
    │ COPY . /app                             │
    │ RUN pip install --no-cache-dir \\       │
    │     -r requirements.txt                 │
    │ EXPOSE 5000                             │
    │ CMD ["gunicorn","--bind",               │
    │      "0.0.0.0:5000","app:app"]          │
    └─────────────────────────────────────────┘

    BICEP (Microsoft.App/containerApps ONLY):
    - targetPort: 5000
    - allowHttpsOnly: true
    - cpu: json('0.5')   memory: json('1.0')  ← never raw decimals
    - Parameters: containerAppName, containerImage ONLY
    - No ACR credentials — image comes from Docker Hub
    - Zero trailing commas before } or ]

    PROTOCOL:
    1. Call save_infrastructure_code(docker_code, bicep_code).
    2. Announce: "✅ STEP 1 COMPLETE. Risk_Analyst: begin Step 2."

    ═══ SELF-HEALING PROTOCOL (CRITICAL) ═══
    If you receive a FAILURE message stating 'AppLogsConfiguration.Destination' is invalid:
    1. You must RE-GENERATE the Bicep code immediately.
    2. REMOVE the entire 'appLogsConfiguration' block from the 'configuration' properties.
    3. Do NOT try to fix the destination string; simply DELETE the block.
    4. Call save_infrastructure_code(docker_code, fixed_bicep_code).
    5. Announce: "⚠️ I have self-healed the Bicep template by removing the invalid logging configuration. Risk_Analyst: please re-verify Step 2."

    ON REMEDIATION REQUEST:
    - Fix only the Bicep violations listed, regenerate, call save_infrastructure_code again.
    - After 3 failed attempts say: "REMEDIATION_FAILED — escalating to Governance_Officer." """,
)

# ── Agent 4: Risk Analyst ──────────────────────────────────
risk_analyst = autogen.AssistantAgent(
    name="Risk_Analyst",
    llm_config=llm_config,
    system_message=f"""You are the Cloud Risk & Governance Analyst.

    ═══ STEP 2 OF 5: GOVERNANCE ASSESSMENT ═══

    1. Call run_risk_assessment(region).
    2. Present this exact board from the result:

    ╔══════════════════════════════════════════╗
    ║      ENTERPRISE GOVERNANCE REPORT        ║
    ╠══════════════════════════════════════════╣
    ║ 🛡  Security    : PASSED / FAILED        ║
    ║ 💰  vCPU Cost   : $X.XX / hr             ║
    ║ 📊  Risk Score  : XX / 100               ║
    ║ 🎯  Confidence  : XX / 100               ║
    ║ 🚦  Gate Status : ALLOWED / BLOCKED      ║
    ╚══════════════════════════════════════════╝

    3. If BLOCKED:
       - List each violation id + name clearly.
       - Tell Architect: "Fix violations and call save_infrastructure_code."
       - After Architect saves, call run_risk_assessment again.
       - Max {MAX_REMEDIATION_LOOPS} attempts. After that → "REMEDIATION_FAILED."

    4. If ALLOWED:
       - Announce: "✅ STEP 2 COMPLETE. Sentry: begin Step 3 — Docker build." """,
)


# ── Agent 5: DevSecOps Sentry ──────────────────────────────
sentry = autogen.AssistantAgent(
    name="Sentry",
    llm_config=llm_config,
    system_message="""You are the DevSecOps Sentry and Deployment Commander.
    You execute Steps 3, 4, and 5 — IN ORDER. Never skip a step.

    ══════════════════════════════════════════════════
    STEP 3 OF 5: DOCKER BUILD (LOCAL)
    ══════════════════════════════════════════════════
    1. Call docker_build(dockerhub_username, app_name).
    2. If SUCCESS → announce "✅ STEP 3 COMPLETE. Proceeding to Step 4."
    3. If FAILURE → report the error to Governance_Officer and STOP.

    ══════════════════════════════════════════════════
    STEP 4 OF 5: DOCKER PUSH (DOCKER HUB)
    ══════════════════════════════════════════════════
    4. Before pushing, ask Governance_Officer:
       "✅ Docker image built locally. Ready to push to Docker Hub.
        ⚠️  Ensure you have run 'docker login' in your terminal.
        Type 'approve' to push, or 'abort' to cancel."

    5. On 'approve' → call docker_push(dockerhub_username, app_name).
    6. If 'denied/unauthorized' → ask Governance_Officer to run 'docker login'
       and type 'retry_push', then call docker_push again.
    7. If SUCCESS → announce "✅ STEP 4 COMPLETE. Proceeding to Step 5."

    ══════════════════════════════════════════════════
    STEP 5 OF 5: AZURE DEPLOYMENT
    ══════════════════════════════════════════════════
    8. Ask Governance_Officer:
       "✅ Image is live on Docker Hub. Ready to deploy to Azure.
        This will create/update Azure Container Apps in MigratAI-RG.
        Type 'approve' to deploy, or 'abort' to cancel."

    9. On 'approve' → call azure_deploy(app_name, dockerhub_username, region).

    10. Auto-fix errors (max 2 retries):
        - ResourceGroupNotFound →
            execute_bash_command("az group create --name MigratAI-RG --location [region]")
            then call azure_deploy again.
        - Azure CLI not authenticated →
            Tell Governance_Officer: "Run '' then type 'approve' again."
        - Other errors → Report full error to Governance_Officer.

    11. On SUCCESS → print:
        ╔══════════════════════════════════════════════╗
        ║         ✅  MIGRATION COMPLETE               ║
        ╠══════════════════════════════════════════════╣
        ║  🐳  Image  : [dockerhub_username]/[app]     ║
        ║  ☁️   Region : [region]                       ║
        ║  🌐  URL    : https://[app].[region]          ║
        ║              .azurecontainerapps.io           ║
        ║  📋  Report : governance_report.json          ║
        ║  📋  Audit  : audit_log.json                  ║
        ╚══════════════════════════════════════════════╝
        Then output exactly: TERMINATE

    12. On 'abort' at any stage → output: TERMINATE""",
)


# ==========================================================
# 6. REGISTER TOOLS
# ==========================================================

# Architect tools
autogen.agentchat.register_function(
    save_infrastructure_code,
    caller=architect, executor=cicd_pipeline,
    name="save_infrastructure_code",
    description="[STEP 1] Save Dockerfile and Bicep code to disk.",
)

# Risk Analyst tools
autogen.agentchat.register_function(
    run_risk_assessment,
    caller=risk_analyst, executor=cicd_pipeline,
    name="run_risk_assessment",
    description="[STEP 2] Run Checkov security scan + Azure cost estimate + risk scoring.",
)

# Sentry tools — one function per pipeline step
autogen.agentchat.register_function(
    docker_build,
    caller=sentry, executor=cicd_pipeline,
    name="docker_build",
    description="[STEP 3] Build the Docker image locally from ./code folder.",
)

autogen.agentchat.register_function(
    docker_push,
    caller=sentry, executor=cicd_pipeline,
    name="docker_push",
    description="[STEP 4] Push the locally built image to Docker Hub.",
)

autogen.agentchat.register_function(
    azure_deploy,
    caller=sentry, executor=cicd_pipeline,
    name="azure_deploy",
    description="[STEP 5] Deploy Bicep infrastructure to Azure Container Apps.",
)

autogen.agentchat.register_function(
    execute_bash_command,
    caller=sentry, executor=cicd_pipeline,
    name="execute_bash_command",
    description="Run a one-off CLI fix command (az group create, az login, etc.).",
)

autogen.agentchat.register_function(
    update_step,
    caller=sentry, executor=cicd_pipeline,
    name="update_step",
    description="Update the pipeline step tracker board.",
)


# ==========================================================
# 7. A2A ORCHESTRATION ENGINE
# ==========================================================

def start_migration(
    region:             str,
    dockerhub_username: str,
    app_name:           str,
    code_path:          str = "./code",
):
    validate_env()

    if not os.path.exists(f"{code_path}/app.py"):
        logging.error(f"❌ app.py not found in '{code_path}'. Aborting.")
        return

    blueprint   = extract_architecture(f"{code_path}/app.py")
    folder_tree = get_folder_structure(code_path)

    # Mark step 1 as running immediately
    update_step("step_1_architect", "running")

    logging.info("🚀 Booting MigratAI Step-by-Step A2A Pipeline...")
    logging.info(f"   Region={region} | DockerHub={dockerhub_username} | App={app_name}")

    groupchat = autogen.GroupChat(
        agents=[governance_officer, cicd_pipeline, architect, risk_analyst, sentry],
        messages=[],
        max_round=50,
        speaker_selection_method="auto",
        admin_name="Governance_Officer",
    )

    manager = autogen.GroupChatManager(
        groupchat=groupchat,
        llm_config=llm_config,
        is_termination_msg=is_termination_msg,
    )

    kickstart = f"""
[SYSTEM: MIGRATAI STEP-BY-STEP PIPELINE INITIATED]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TARGET APP          : {code_path}
  DEPLOYMENT REGION   : {region}
  DOCKER HUB USERNAME : {dockerhub_username}
  APP NAME            : {app_name}
  FULL IMAGE TAG      : {dockerhub_username}/{app_name}:latest
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

── PIPELINE ──
  Step 1 → Architect    : Generate Dockerfile + Bicep
  Step 2 → Risk_Analyst : Security Scan + Governance Score
  Step 3 → Sentry       : Docker Build (Local)
  Step 4 → Sentry       : Docker Push (Docker Hub)
  Step 5 → Sentry       : Azure Infrastructure Deploy

── BLUEPRINT ──
{blueprint}

── DIRECTORY CONTEXT ──
{folder_tree}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Each agent completes their step and hands off to the next.
Governance_Officer approves each deployment gate.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Architect — Step 1 is yours. Generate and save the infrastructure code now.
"""

    try:
        governance_officer.initiate_chat(manager, message=kickstart)
    finally:
        save_audit_trail(groupchat.messages)
        logging.info(f"📋 Governance report → {GOVERNANCE_REPORT}")
        logging.info(f"📋 Pipeline step log → {STEP_LOG}")
        logging.info(f"📋 Full audit log    → {AUDIT_LOG}")


# ==========================================================
# 8. ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    print("\n" + "═" * 58)
    print("   MigratAI  |  Step-by-Step A2A Pipeline")
    print("   Docker Hub Edition  |  Powered by AutoGen")
    print("═" * 58)

    print("""
  PIPELINE OVERVIEW:
  ──────────────────────────────────────────────────────
  Step 1 → Architect    : Generate Dockerfile + Bicep
  Step 2 → Risk_Analyst : Security Scan + Governance
  Step 3 → Sentry       : Docker Build (Local Image)
  Step 4 → Sentry       : Docker Push (Docker Hub)
  Step 5 → Sentry       : Azure Infrastructure Deploy
  ──────────────────────────────────────────────────────
  ⚠️  Before starting: make sure 'docker login' and
     'az login' have been run in this terminal.
  ──────────────────────────────────────────────────────
""")

    region        = input("  Enter Azure region       (e.g. eastus) : ").strip() or "eastus"
    dockerhub_user = input("  Enter Docker Hub username (e.g. yuvraj) : ").strip()
    app_name       = input("  Enter App name           (e.g. mad1)   : ").strip() or "mad1"

    if not dockerhub_user:
        print("\n  ❌ Docker Hub username is required. Aborting.")
        sys.exit(1)

    print(f"""
  ✅ Config accepted:
     Region   : {region}
     DockerHub : {dockerhub_user}/{app_name}:latest
     Azure RG  : MigratAI-RG

  Starting pipeline in 3 seconds...
""")

    import time; time.sleep(3)

    start_migration(
        region=region,
        dockerhub_username=dockerhub_user,
        app_name=app_name,
        code_path="./code",
    )