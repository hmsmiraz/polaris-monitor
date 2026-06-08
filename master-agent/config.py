import os
import sys
from pathlib import Path

# ── Platform-aware paths ───────────────────────────────────────────────────────
if sys.platform == "win32":
    _base = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Polaris"
    PROMETHEUS_TARGETS_DIR = _base / "prometheus" / "file_sd"
    PROMETHEUS_CONFIG_FILE = _base / "prometheus" / "prometheus.yml"
    GRAFANA_PROVISIONING_DIR = _base / "grafana" / "provisioning"
else:
    _base = Path("/etc/polaris")
    PROMETHEUS_TARGETS_DIR = Path("/etc/prometheus/file_sd")
    PROMETHEUS_CONFIG_FILE = Path("/etc/prometheus/prometheus.yml")
    GRAFANA_PROVISIONING_DIR = Path("/etc/grafana/provisioning")

CONFIG_DIR = _base
MASTER_CONFIG_FILE = CONFIG_DIR / "master.json"
PROMETHEUS_TARGETS_FILE = PROMETHEUS_TARGETS_DIR / "targets.json"

# ── Database ───────────────────────────────────────────────────────────────────
DB_HOST = os.getenv("POLARIS_DB_HOST", "localhost")
DB_PORT = int(os.getenv("POLARIS_DB_PORT", "5432"))
DB_NAME = os.getenv("POLARIS_DB_NAME", "polaris")
DB_USER = os.getenv("POLARIS_DB_USER", "polaris")
DB_PASSWORD = os.getenv("POLARIS_DB_PASSWORD", "polaris_secret_2024")
DATABASE_DSN = (
    f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} "
    f"user={DB_USER} password={DB_PASSWORD}"
)

# ── API ────────────────────────────────────────────────────────────────────────
API_HOST = os.getenv("POLARIS_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("POLARIS_API_PORT", "8000"))

# ── Prometheus ─────────────────────────────────────────────────────────────────
PROMETHEUS_HOST = os.getenv("PROMETHEUS_HOST", "localhost")
PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "9090"))
PROMETHEUS_URL = f"http://{PROMETHEUS_HOST}:{PROMETHEUS_PORT}"

# ── Grafana ────────────────────────────────────────────────────────────────────
GRAFANA_HOST = os.getenv("GRAFANA_HOST", "localhost")
GRAFANA_PORT = int(os.getenv("GRAFANA_PORT", "3000"))
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "admin")
GRAFANA_URL = f"http://{GRAFANA_HOST}:{GRAFANA_PORT}"

# ── Behaviour ──────────────────────────────────────────────────────────────────
HEARTBEAT_TIMEOUT = int(os.getenv("HEARTBEAT_TIMEOUT", "120"))
NODE_EXPORTER_PORT = int(os.getenv("NODE_EXPORTER_PORT", "9100"))

# ── Email Alerts (optional) ────────────────────────────────────────────────────
SMTP_HOST = os.getenv("POLARIS_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("POLARIS_SMTP_PORT", "587"))
SMTP_USER = os.getenv("POLARIS_SMTP_USER", "")
SMTP_PASS = os.getenv("POLARIS_SMTP_PASS", "")
ALERT_EMAIL_TO = os.getenv("POLARIS_ALERT_EMAIL", "")
