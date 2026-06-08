import json
import os
import sys
from pathlib import Path

# ── Platform-aware config directory ───────────────────────────────────────────
if sys.platform == "win32":
    CONFIG_DIR = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Polaris"
else:
    CONFIG_DIR = Path("/etc/polaris")

AGENT_CONFIG_FILE = CONFIG_DIR / "agent.json"

# ── Thresholds ─────────────────────────────────────────────────────────────────
CPU_ALERT_THRESHOLD    = float(os.getenv("POLARIS_CPU_THRESHOLD",    "90"))
MEMORY_ALERT_THRESHOLD = float(os.getenv("POLARIS_MEMORY_THRESHOLD", "90"))
DISK_ALERT_THRESHOLD   = float(os.getenv("POLARIS_DISK_THRESHOLD",   "90"))

# ── Intervals (seconds) ────────────────────────────────────────────────────────
METRICS_INTERVAL    = int(os.getenv("POLARIS_METRICS_INTERVAL",    "30"))
HEARTBEAT_INTERVAL  = int(os.getenv("POLARIS_HEARTBEAT_INTERVAL",  "60"))
SSH_CHECK_INTERVAL  = int(os.getenv("POLARIS_SSH_CHECK_INTERVAL",  "1800"))
ALERT_SUSTAIN_SECONDS = int(os.getenv("POLARIS_ALERT_SUSTAIN",     "0"))

# ── Auto-reboot ────────────────────────────────────────────────────────────────
REBOOT_ENABLED          = os.getenv("POLARIS_REBOOT_ENABLED", "false").lower() == "true"
REBOOT_CPU_THRESHOLD    = float(os.getenv("POLARIS_REBOOT_CPU_THRESHOLD",    "95"))
REBOOT_MEMORY_THRESHOLD = float(os.getenv("POLARIS_REBOOT_MEMORY_THRESHOLD", "95"))
REBOOT_SUSTAIN_SECONDS  = int(os.getenv("POLARIS_REBOOT_SUSTAIN", "180"))

NODE_EXPORTER_PORT = int(os.getenv("POLARIS_NODE_EXPORTER_PORT", "9100"))


def load_config() -> dict:
    if not AGENT_CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Agent not configured ({AGENT_CONFIG_FILE}). "
            "Run: polaris join --master-ip <IP> --token <TOKEN>"
        )
    with open(AGENT_CONFIG_FILE) as f:
        return json.load(f)


def save_config(data: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(AGENT_CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)
    if sys.platform != "win32":
        os.chmod(AGENT_CONFIG_FILE, 0o600)


def is_configured() -> bool:
    return AGENT_CONFIG_FILE.exists()
