#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════╗
# ║          Polaris Monitor — Unified Installer                ║
# ║  Supports: Ubuntu · Debian · RHEL · CentOS · Rocky Linux   ║
# ║            AlmaLinux · Fedora · openSUSE                    ║
# ╚══════════════════════════════════════════════════════════════╝
#
# MASTER  →  sudo bash install.sh master
# AGENT   →  sudo bash install.sh agent --master-ip 10.0.0.10 --token abc123
#
# All options:
#   --master-ip  <IP>     Master server IP  (agent mode)
#   --token      <TOKEN>  Join token        (agent mode)
#   --master-port <PORT>  Master API port   (default: 8000)
#   --exporter-port <P>   Exporter port     (default: 9100)
#   --skip-exporter       Skip exporter install
#   --skip-init           Skip polaris-master init (master mode)

set -euo pipefail

# ── Colour helpers ─────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'
ok()      { echo -e "  ${GREEN}[✓]${NC} $*"; }
info()    { echo -e "  ${CYAN}[→]${NC} $*"; }
warn()    { echo -e "  ${YELLOW}[!]${NC} $*"; }
error()   { echo -e "  ${RED}[✗]${NC} $*" >&2; exit 1; }
step()    { echo -e "\n${BOLD}${CYAN}▶ $*${NC}"; }
banner()  {
  echo -e "\n${BOLD}${CYAN}"
  echo    "  ╔══════════════════════════════════════════════╗"
  printf  "  ║  %-44s║\n" "$1"
  echo    "  ╚══════════════════════════════════════════════╝"
  echo -e "${NC}"
}

# ── Parse arguments ────────────────────────────────────────────────────────────
MODE="${1:-}"; shift || true
MASTER_IP=""; MASTER_TOKEN=""; MASTER_PORT="8000"
EXPORTER_PORT="9100"; SKIP_EXPORTER=0; SKIP_INIT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --master-ip)      MASTER_IP="$2";       shift 2 ;;
    --token)          MASTER_TOKEN="$2";    shift 2 ;;
    --master-port)    MASTER_PORT="$2";     shift 2 ;;
    --exporter-port)  EXPORTER_PORT="$2";   shift 2 ;;
    --skip-exporter)  SKIP_EXPORTER=1;      shift   ;;
    --skip-init)      SKIP_INIT=1;          shift   ;;
    *) error "Unknown argument: $1" ;;
  esac
done

[[ "$MODE" == "master" || "$MODE" == "agent" ]] || {
  echo -e "${BOLD}Usage:${NC}"
  echo "  sudo bash install.sh master"
  echo "  sudo bash install.sh agent --master-ip <IP> --token <TOKEN>"
  exit 1
}

# ── Root check ─────────────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || error "Must be run as root.  Try: sudo bash install.sh $MODE"

# ── Constants ──────────────────────────────────────────────────────────────────
POLARIS_HOME="/opt/polaris"
MASTER_DIR="$POLARIS_HOME/master-agent"
AGENT_DIR="$POLARIS_HOME/worker-agent"
CONFIG_DIR="/etc/polaris"
LOG_DIR="/var/log/polaris"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── OS Detection ───────────────────────────────────────────────────────────────
detect_os() {
  PKG_MGR="apt-get"; OS_FAMILY="debian"; OS_NAME="unknown"
  if [[ -f /etc/os-release ]]; then
    # shellcheck source=/dev/null
    source /etc/os-release
    OS_NAME="${NAME:-unknown}"
    ID_COMBINED="${ID:-} ${ID_LIKE:-}"
    if echo "$ID_COMBINED" | grep -qiE "ubuntu|debian"; then
      PKG_MGR="apt-get"; OS_FAMILY="debian"
    elif echo "$ID_COMBINED" | grep -qiE "rhel|centos|fedora|rocky|almalinux|ol"; then
      command -v dnf &>/dev/null && PKG_MGR="dnf" || PKG_MGR="yum"
      OS_FAMILY="rhel"
    elif echo "$ID_COMBINED" | grep -qiE "opensuse|sles|suse"; then
      PKG_MGR="zypper"; OS_FAMILY="suse"
    fi
  fi
  info "Detected: $OS_NAME (family: $OS_FAMILY, pkg: $PKG_MGR)"
}

# ── Python Installation ────────────────────────────────────────────────────────
install_python() {
  if command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
    if [[ $PY_MAJOR -ge 3 && $PY_MINOR -ge 9 ]]; then
      ok "Python $PY_VER already installed"; PYTHON=python3; return
    fi
  fi

  info "Installing Python 3.9+..."
  case "$OS_FAMILY" in
    debian)
      apt-get update -qq
      apt-get install -y -qq python3 python3-pip python3-venv
      ;;
    rhel)
      $PKG_MGR install -y python3 python3-pip
      # Older RHEL 8 may need python39
      python3 -c "import sys; assert sys.version_info >= (3,9)" 2>/dev/null || \
        $PKG_MGR install -y python39 python39-pip && \
        alternatives --set python3 /usr/bin/python3.9 2>/dev/null || true
      ;;
    suse)
      zypper install -y python3 python3-pip python3-venv
      ;;
  esac
  PYTHON=python3
  ok "Python installed: $($PYTHON --version)"
}

# ── System Dependencies ────────────────────────────────────────────────────────
install_deps() {
  info "Installing system dependencies..."
  case "$OS_FAMILY" in
    debian)
      apt-get update -qq
      apt-get install -y -qq curl wget git jq python3-venv python3-pip libpq-dev gcc
      ;;
    rhel)
      $PKG_MGR install -y curl wget git jq python3-pip libpq-devel gcc
      ;;
    suse)
      zypper install -y curl wget git jq python3-pip libpq5-devel gcc
      ;;
  esac
  ok "System dependencies ready"
}

# ── Copy Agent Files ───────────────────────────────────────────────────────────
install_files() {
  local SRC_DIR="$1"
  local DST_DIR="$2"
  mkdir -p "$DST_DIR"
  cp -r "$SRC_DIR/." "$DST_DIR/"
  ok "Files installed to $DST_DIR"
}

# ── Python Virtual Environment ─────────────────────────────────────────────────
setup_venv() {
  local DIR="$1"
  info "Creating Python virtual environment..."
  $PYTHON -m venv "$DIR/venv"
  "$DIR/venv/bin/pip" install --quiet --upgrade pip
  "$DIR/venv/bin/pip" install --quiet -r "$DIR/requirements.txt"
  ok "Python dependencies installed"
}

# ── Environment Config File ────────────────────────────────────────────────────
write_master_env() {
  mkdir -p "$CONFIG_DIR"
  [[ -f "$CONFIG_DIR/master.env" ]] && { ok "master.env already exists"; return; }
  cat > "$CONFIG_DIR/master.env" << 'EOF'
POLARIS_DB_HOST=localhost
POLARIS_DB_PORT=5432
POLARIS_DB_NAME=polaris
POLARIS_DB_USER=polaris
POLARIS_DB_PASSWORD=polaris_secret_2024
POLARIS_API_HOST=0.0.0.0
POLARIS_API_PORT=8000
PROMETHEUS_HOST=localhost
PROMETHEUS_PORT=9090
GRAFANA_HOST=localhost
GRAFANA_PORT=3000
GRAFANA_USER=admin
GRAFANA_PASSWORD=admin
HEARTBEAT_TIMEOUT=120
EOF
  chmod 600 "$CONFIG_DIR/master.env"
  ok "Config written: $CONFIG_DIR/master.env"
}

# ── Systemd Service Writers ────────────────────────────────────────────────────
write_master_service() {
  cat > /etc/systemd/system/polaris-master.service << EOF
[Unit]
Description=Polaris Master Agent
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=$MASTER_DIR
EnvironmentFile=$CONFIG_DIR/master.env
ExecStart=$MASTER_DIR/venv/bin/python $MASTER_DIR/main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  ok "polaris-master.service installed"
}

write_agent_service() {
  cat > /etc/systemd/system/polaris-agent.service << EOF
[Unit]
Description=Polaris Worker Agent
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$AGENT_DIR
ExecStart=$AGENT_DIR/venv/bin/python $AGENT_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  ok "polaris-agent.service installed"
}

# ── CLI Wrappers ───────────────────────────────────────────────────────────────
write_master_cli() {
  cat > /usr/local/bin/polaris-master << EOF
#!/usr/bin/env bash
cd "$MASTER_DIR"
exec "$MASTER_DIR/venv/bin/python" "$MASTER_DIR/cli.py" "\$@"
EOF
  chmod +x /usr/local/bin/polaris-master
  ok "CLI installed: polaris-master"
}

write_agent_cli() {
  cat > /usr/local/bin/polaris << EOF
#!/usr/bin/env bash
cd "$AGENT_DIR"
exec "$AGENT_DIR/venv/bin/python" "$AGENT_DIR/cli.py" "\$@"
EOF
  chmod +x /usr/local/bin/polaris
  ok "CLI installed: polaris"
}

# ════════════════════════════════════════════════════════════════
#  MASTER INSTALLATION
# ════════════════════════════════════════════════════════════════
install_master() {
  banner "Polaris Master — Installation"

  step "1/6  Detecting OS & installing dependencies"
  detect_os
  install_deps
  install_python

  step "2/6  Installing Polaris Master Agent"
  [[ -d "$SCRIPT_DIR/master-agent" ]] || error "master-agent/ not found. Run from the repo root."
  install_files "$SCRIPT_DIR/master-agent" "$MASTER_DIR"
  setup_venv "$MASTER_DIR"
  write_master_env
  write_master_service
  write_master_cli
  mkdir -p "$LOG_DIR"

  step "3/6  Installing PostgreSQL"
  "$MASTER_DIR/venv/bin/python" - << 'PYEOF'
import sys; sys.path.insert(0, "$MASTER_DIR")
from installers import postgres_installer
postgres_installer.setup()
PYEOF

  step "4/6  Installing Prometheus"
  "$MASTER_DIR/venv/bin/python" - << 'PYEOF'
import sys; sys.path.insert(0, "$MASTER_DIR")
from installers import prometheus_installer
prometheus_installer.setup()
PYEOF

  step "5/6  Installing Grafana"
  "$MASTER_DIR/venv/bin/python" - << 'PYEOF'
import sys; sys.path.insert(0, "$MASTER_DIR")
from installers import grafana_installer
grafana_installer.setup()
PYEOF

  step "6/6  Initializing Polaris Master"
  if [[ $SKIP_INIT -eq 1 ]]; then
    warn "Skipping init (--skip-init)"
    echo -e "\n  Run [bold]polaris-master init[/bold] when ready."
  else
    polaris-master init --skip-install
  fi
}

# ════════════════════════════════════════════════════════════════
#  AGENT INSTALLATION
# ════════════════════════════════════════════════════════════════
install_agent() {
  banner "Polaris Worker Agent — Installation"

  step "1/4  Detecting OS & installing dependencies"
  detect_os
  install_deps
  install_python

  step "2/4  Installing Polaris Worker Agent"
  [[ -d "$SCRIPT_DIR/worker-agent" ]] || error "worker-agent/ not found. Run from the repo root."
  install_files "$SCRIPT_DIR/worker-agent" "$AGENT_DIR"
  setup_venv "$AGENT_DIR"
  write_agent_service
  write_agent_cli
  mkdir -p "$CONFIG_DIR" "$LOG_DIR"
  ok "Polaris Worker Agent installed"

  step "3/4  Installing Metrics Exporter"
  if [[ $SKIP_EXPORTER -eq 1 ]]; then
    warn "Skipping exporter install (--skip-exporter)"
  else
    "$AGENT_DIR/venv/bin/python" - << PYEOF
import sys; sys.path.insert(0, "$AGENT_DIR")
from services.node_exporter import setup
setup(port=$EXPORTER_PORT)
PYEOF
  fi

  step "4/4  Joining Master Server"
  if [[ -n "$MASTER_IP" && -n "$MASTER_TOKEN" ]]; then
    polaris join \
      --master-ip   "$MASTER_IP" \
      --master-port "$MASTER_PORT" \
      --token       "$MASTER_TOKEN" \
      --node-exporter-port "$EXPORTER_PORT" \
      --skip-install
  else
    warn "No --master-ip / --token provided. Join manually:"
    echo ""
    echo -e "  ${BOLD}polaris join --master-ip <IP> --token <TOKEN>${NC}"
    echo ""
  fi
}

# ── Entry point ────────────────────────────────────────────────────────────────
case "$MODE" in
  master) install_master ;;
  agent)  install_agent  ;;
esac
