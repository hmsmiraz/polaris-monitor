# Polaris Monitor

A lightweight Python-based server monitoring and node management platform.
One master controls many workers — everything installs with a single command.

```
sudo bash install.sh master                                       # on master
sudo bash install.sh agent --master-ip 10.0.0.10 --token TOKEN   # on each worker
```

---

## Supported Operating Systems

| OS | Master | Worker |
|---|:---:|:---:|
| Ubuntu 20.04 / 22.04 / 24.04 | ✅ | ✅ |
| Debian 11 / 12 | ✅ | ✅ |
| RHEL 8 / 9 | ✅ | ✅ |
| CentOS Stream 8 / 9 | ✅ | ✅ |
| Rocky Linux 8 / 9 | ✅ | ✅ |
| AlmaLinux 8 / 9 | ✅ | ✅ |
| Fedora 38 / 39 / 40 | ✅ | ✅ |
| openSUSE Leap 15 | ✅ | ✅ |
| Windows 10 / 11 | — | ✅ |
| Windows Server 2019 / 2022 | — | ✅ |

> **Master on Windows is not supported** — PostgreSQL, Prometheus, and Grafana
> are production-deployed on Linux. Workers run on any OS.

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Part 1 — Master Setup (Linux)](#part-1--master-setup-linux)
- [Part 2 — Worker Setup (Linux)](#part-2--worker-setup-linux)
- [Part 3 — Worker Setup (Windows)](#part-3--worker-setup-windows)
- [Part 4 — Accessing Dashboards](#part-4--accessing-dashboards)
- [CLI Reference — Master](#cli-reference--master)
- [CLI Reference — Worker](#cli-reference--worker)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Email Alerts](#email-alerts)
- [Ports & Firewall Rules](#ports--firewall-rules)
- [Auto-Recovery & Auto-Reboot](#auto-recovery--auto-reboot)
- [Alert Thresholds](#alert-thresholds)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        MASTER SERVER (Linux)                     │
│                                                                  │
│  ┌─────────────────────┐   ┌─────────────────────────────────┐  │
│  │  Polaris Master API  │──▶│  PostgreSQL                     │  │
│  │  FastAPI  :8000      │   │  nodes · alerts · events        │  │
│  │                      │   │  join_tokens · metrics_summary  │  │
│  │  /api/v1/register    │   └─────────────────────────────────┘  │
│  │  /api/v1/heartbeat   │                                        │
│  │  /api/v1/metrics     │   ┌─────────────────────────────────┐  │
│  │  /api/v1/alerts ─────┼──▶│  Email Notifier (SMTP)          │  │
│  │  /api/v1/nodes       │   │  optional — Gmail / any SMTP    │  │
│  │  /api/v1/status      │   └─────────────────────────────────┘  │
│  └──────────┬──────────┘                                        │
│             │               ┌─────────────────────────────────┐  │
│             └──────────────▶│  /etc/prometheus/file_sd/       │  │
│                             │  targets.json  (auto-updated)   │  │
│  ┌──────────────────────┐   └──────────────┬──────────────────┘  │
│  │  SSH Checker Thread  │                  │                     │
│  │  TCP :22 every 60s   │                  ▼                     │
│  └──────────────────────┘   ┌─────────────────────────────────┐  │
│                             │  Prometheus  :9090              │  │
│                             │  Scrapes exporters via file_sd  │  │
│                             └───────────────┬─────────────────┘  │
│                                             │                    │
│                             ┌───────────────▼─────────────────┐  │
│                             │  Grafana  :3000  (auto-provisioned dashboard) │  │
│                             └─────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
              ▲  register / heartbeat / metrics / alerts
              │           HTTP  :8000
  ┌───────────┴──────────────────────────────────────────────────┐
  │           WORKER NODE  (Linux or Windows)                    │
  │                                                              │
  │  Thread 1  Heartbeat      →  every  60 s  (boot_time + reason) │
  │  Thread 2  Metrics        →  every  30 s                    │
  │  Thread 3  Alert Checker  →  every  30 s  (+ auto-reboot)   │
  │  Thread 4  SSH Checker    →  every  30 min  (Linux only)    │
  │                                                              │
  │  Linux:   node_exporter     :9100/metrics                   │
  │  Windows: windows_exporter  :9100/metrics                   │
  └──────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
polaris-monitor/
├── install.sh                       ← Linux one-command installer (master + agent)
├── install.ps1                      ← Windows PowerShell installer (agent)
│
├── master-agent/
│   ├── main.py                      API server entry point
│   ├── cli.py                       polaris-master CLI
│   ├── config.py                    All settings & env vars (POLARIS_*)
│   ├── requirements.txt
│   │
│   ├── api/
│   │   ├── app.py                   FastAPI app + offline-detection thread
│   │   └── routes/
│   │       ├── register.py          POST /api/v1/register
│   │       ├── heartbeat.py         POST /api/v1/heartbeat
│   │       ├── metrics.py           POST /api/v1/metrics
│   │       ├── alerts.py            GET/POST /api/v1/alerts  (+ email notify)
│   │       ├── nodes.py             GET /api/v1/nodes[/{id}]
│   │       ├── prom_metrics.py      GET /api/v1/prom-metrics (Prometheus endpoint)
│   │       └── status.py            GET /api/v1/status
│   │
│   ├── database/
│   │   ├── connection.py            psycopg2 ThreadedConnectionPool
│   │   └── schema.py                Table definitions + indexes
│   │
│   ├── models/                      Pydantic request/response models
│   ├── services/
│   │   ├── token_service.py         Join token generate / validate
│   │   ├── node_service.py          Node CRUD + stale-heartbeat detection
│   │   ├── alert_service.py         Alert CRUD
│   │   ├── ssh_checker.py           Background TCP-22 checker (master-side)
│   │   └── email_notifier.py        SMTP email on every alert (optional)
│   │
│   ├── prometheus/
│   │   └── config_manager.py        Writes file_sd/targets.json on worker join
│   ├── grafana/
│   │   └── dashboard_manager.py     Grafana HTTP API — datasource + dashboard
│   └── installers/
│       ├── postgres_installer.py    apt / dnf / yum / zypper
│       ├── prometheus_installer.py  Binary download (all Linux)
│       └── grafana_installer.py     apt repo / RPM repo / zypper
│
└── worker-agent/
    ├── main.py                      Daemon — 4 background threads
    ├── cli.py                       polaris CLI (Linux + Windows)
    ├── config.py                    Cross-platform config paths + thresholds
    ├── requirements.txt
    │
    ├── registration/client.py       Register with master → receive agent_id
    ├── collector/metrics_collector.py   psutil metrics
    ├── heartbeat/heartbeat.py       POST /api/v1/heartbeat (boot_time + reboot reason)
    ├── alerts/alert_manager.py      Threshold checks + sustain window + auto-reboot
    ├── ssh_checker/ssh_checker.py   Linux: check/restart SSH; Windows: skip
    └── services/node_exporter.py    Linux: node_exporter; Windows: windows_exporter
```

---

## Part 1 — Master Setup (Linux)

### Step 1 — Clone the Repository

```bash
git clone https://github.com/hmsmiraz/polaris-monitor.git
cd polaris-monitor
```

### Step 2 — Run the Installer

One command does everything: installs Python, PostgreSQL, Prometheus, Grafana,
configures them, generates a join token, starts all services, and provisions the
Grafana dashboard.

```bash
sudo bash install.sh master
```

<details>
<summary>Expected output</summary>

```
  +----------------------------------------------+
  |  Polaris Monitor - Master Installation       |
  +----------------------------------------------+

  ▶ 1/6  Detecting OS & installing dependencies
  [→]  Detected: Ubuntu 22.04.3 LTS (family: debian, pkg: apt-get)
  [✓]  Python 3.10.12 already installed
  [✓]  System dependencies ready

  ▶ 2/6  Installing Polaris Master Agent
  [✓]  Files installed to /opt/polaris/master-agent
  [✓]  Python dependencies installed
  [✓]  Config written: /etc/polaris/master.env
  [✓]  polaris-master.service installed
  [✓]  CLI installed: polaris-master

  ▶ 3/6  Installing PostgreSQL
  [✓]  PostgreSQL installed
  [✓]  Database ready

  ▶ 4/6  Installing Prometheus
  [✓]  Prometheus binary installed
  [✓]  Prometheus service configured

  ▶ 5/6  Installing Grafana
  [✓]  Grafana installed
  [✓]  Grafana service configured

  ▶ 6/6  Initializing Polaris Master

  ══════════════════════════════════════════════════════════
    Polaris Master Initialized Successfully

    Master IP:       10.0.0.10
    Public IP:       54.210.x.x

    Join Token:
    ██ abc123XYZ789def456GHI012jkl ██

    Master API:      http://10.0.0.10:8000
    Prometheus:      http://10.0.0.10:9090
    Grafana:         http://10.0.0.10:3000

    Worker Join Command:
    polaris join --master-ip 10.0.0.10 --token abc123XYZ789def456GHI012jkl
  ══════════════════════════════════════════════════════════
```
</details>

> **Save the Join Token.** You'll need it for every worker.
> Retrieve it any time with `polaris-master token`.

### Step 3 — Verify

```bash
polaris-master status
```

```
Polaris Master Agent — System Status

Nodes:  Total=0  Online=0  Offline=0

Services:
  polaris-master         active
  postgresql             active
  prometheus             active
  grafana-server         active
```

---

## Part 2 — Worker Setup (Linux)

Repeat on **every** Linux worker server.

### Option A — One Command with Auto-Join (Recommended)

Paste the join command shown at the end of master init.
The installer will install the agent, install Node Exporter, and join automatically.

```bash
sudo bash install.sh agent \
  --master-ip 10.0.0.10 \
  --token     abc123XYZ789def456GHI012jkl
```

Expected output:

```
  +----------------------------------------------+
  |  Polaris Monitor - Agent Installation        |
  +----------------------------------------------+

  ▶ 1/4  Detecting OS & installing dependencies
  [✓]  Detected: Ubuntu 22.04 LTS (family: debian, pkg: apt-get)

  ▶ 2/4  Installing Polaris Worker Agent
  [✓]  Files installed to /opt/polaris/worker-agent
  [✓]  Python dependencies installed

  ▶ 3/4  Installing Metrics Exporter
  [✓]  Node Exporter installed and started

  ▶ 4/4  Joining Master Server

  ══════════════════════════════════════════════
    Successfully Joined Master

    Agent ID:       polaris-worker01-a1b2c3d4
    Master:         10.0.0.10:8000
    Exporter port:  9100
    Status:         Connected
  ══════════════════════════════════════════════
```

### Option B — Install First, Join Later

```bash
# Install only
sudo bash install.sh agent

# Join when ready
sudo polaris join --master-ip 10.0.0.10 --token abc123XYZ789def456GHI012jkl
```

### Verify on the Worker

```bash
polaris status
```

```
  Agent ID        polaris-worker01-a1b2c3d4
  Master          10.0.0.10:8000
  Service         active
  Platform        linux
  ─────────────────────────────────────────
  Hostname        worker-01
  CPU Usage       8.4%
  Memory Usage    32.1%  (1312 MB / 4096 MB)
  Disk Usage      24.6%  (12.3 GB / 50.0 GB)
  Load Avg        0.12 / 0.09 / 0.07
  Uptime          3h 42m
  OS              Linux 5.15.0-1035-aws
```

### Verify on the Master

```bash
polaris-master nodes
```

```
┌──────────────────────────────────────────────────────────────────┐
│ Registered Nodes (1 total)                                       │
├────────────────────────────┬──────────┬────────────┬────────┬────┤
│ Agent ID                   │ Hostname │ Private IP │ Status │ … │
├────────────────────────────┼──────────┼────────────┼────────┼────┤
│ polaris-worker01-a1b2c3d4  │ worker-01│ 10.0.0.20  │ online │ … │
└────────────────────────────┴──────────┴────────────┴────────┴────┘
```

---

## Part 3 — Worker Setup (Windows)

### Prerequisites

- Windows 10 / 11 or Windows Server 2019 / 2022
- PowerShell 5.1 or later
- Run as **Administrator**

### Step 1 — Clone or Download the Repository

```powershell
git clone https://github.com/hmsmiraz/polaris-monitor.git
cd polaris-monitor
```

### Step 2 — Run the Installer

#### Option A — One Command with Auto-Join (Recommended)

```powershell
.\install.ps1 -MasterIP 10.0.0.10 -Token abc123XYZ789def456GHI012jkl
```

#### Option B — Interactive (Prompts for Master IP and Token)

```powershell
.\install.ps1
```

The installer will prompt:
```
  Enter Master IP address: 10.0.0.10
  Enter Join Token: abc123XYZ789def456GHI012jkl
```

#### Option C — Install Only, Join Later

```powershell
.\install.ps1 -SkipJoin

# Then join manually
polaris join --master-ip 10.0.0.10 --token abc123XYZ789def456GHI012jkl
```

What the Windows installer does automatically:

| Step | Action |
|---|---|
| 1 | Detects or installs Python 3.11 via `winget` |
| 2 | Copies agent files to `C:\Program Files\Polaris\` |
| 3 | Creates Python virtual environment |
| 4 | Downloads and installs **NSSM** (service manager) |
| 5 | Downloads and installs **Windows Exporter** as a Windows Service |
| 6 | Installs **polaris-agent** as a Windows Service |
| 7 | Creates `polaris.bat` CLI wrapper, adds to system PATH |
| 8 | Joins master if `--MasterIP` and `--Token` were provided |

### Step 3 — Verify

```powershell
polaris status
```

```
  Agent ID        polaris-worker01-a1b2c3d4
  Master          10.0.0.10:8000
  Service         active
  Platform        win32
  ─────────────────────────────────────────
  Hostname        WIN-WORKER01
  CPU Usage       11.2%
  Memory Usage    44.8%  (7270 MB / 16384 MB)
  ...
```

### Windows Services Created

| Service Name | Description |
|---|---|
| `polaris-agent` | Polaris Worker Agent daemon |
| `polaris-node-exporter` | Windows Exporter (metrics) |

Manage from Services panel (`services.msc`) or PowerShell:

```powershell
Start-Service  polaris-agent
Stop-Service   polaris-agent
Restart-Service polaris-agent
Get-Service    polaris-agent
```

---

## Part 4 — Accessing Dashboards

### Prometheus

```
http://<MASTER_IP>:9090
```

Navigate to **Status → Targets** — all workers appear within 30 seconds of joining:

```
node_exporter  /  worker-01 (10.0.0.20:9100)    UP    2.1ms
node_exporter  /  worker-02 (10.0.0.21:9100)    UP    1.8ms
node_exporter  /  WIN-WORKER (10.0.0.30:9100)   UP    3.4ms
```

### Grafana

```
http://<MASTER_IP>:3000
```

| Field | Value |
|---|---|
| Username | `admin` |
| Password | shown at end of `install.sh master` output |

Go to **Dashboards → Polaris Monitor — Node Overview**. Panels:

| Panel | Shows |
|---|---|
| Online Nodes | Live count (green) |
| Offline Nodes | Live count (red) |
| Total Nodes | All registered |
| CPU Usage % | Time series per node |
| Memory Usage % | Time series per node |
| Disk Usage % | Time series per node |
| Load Average (1m) | Time series per node |
| Network Receive | Bytes/sec per interface |
| Network Transmit | Bytes/sec per interface |
| Node Status Table | Agent ID / Hostname / IP / Online-Offline |
| SSH Check Status | Last SSH check time, last seen, OK / Failed per node |
| Reboot History | Last reboot time + reason: Manual / System / Agent Auto-Reboot |

New workers appear automatically — no dashboard changes needed.

### API Docs (Swagger)

```
http://<MASTER_IP>:8000/docs
```

---

## CLI Reference — Master

### `polaris-master init`

Install all components and initialize the platform.

```bash
sudo polaris-master init

# Re-configure without reinstalling software
sudo polaris-master init --skip-install
```

### `polaris-master token`

```bash
polaris-master token          # list active tokens
polaris-master token --new    # generate a new token
```

### `polaris-master nodes`

```bash
polaris-master nodes           # one-time listing
polaris-master nodes --watch   # live refresh every 5 s
```

### `polaris-master alerts`

```bash
polaris-master alerts           # last 20 alerts
polaris-master alerts --limit 100
```

### `polaris-master status`

```bash
polaris-master status    # service states + node counts
```

---

## CLI Reference — Worker

### `polaris join`

```bash
# Minimal
sudo polaris join --master-ip 10.0.0.10 --token abc123

# All options
sudo polaris join \
  --master-ip          10.0.0.10 \
  --master-port        8000 \
  --token              abc123 \
  --node-exporter-port 9100 \
  --skip-install           # skip exporter install
```

### `polaris status`

```bash
polaris status    # live metrics + service state
```

### `polaris leave`

```bash
sudo polaris leave    # unregister and stop agent
```

---

## API Reference

Base URL: `http://<MASTER_IP>:8000/api/v1`

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/register` | Worker registers, receives `agent_id` |
| `POST` | `/heartbeat` | Worker sends heartbeat every 60 s |
| `POST` | `/metrics` | Worker sends metrics summary every 30 s |
| `POST` | `/alerts` | Worker sends an alert (triggers email if configured) |
| `GET` | `/nodes` | List all nodes |
| `GET` | `/nodes/{agent_id}` | Node details |
| `DELETE` | `/nodes/{agent_id}` | Remove a node |
| `GET` | `/alerts` | List alerts (`?resolved=false&agent_id=…`) |
| `PUT` | `/alerts/{id}/resolve` | Resolve an alert |
| `GET` | `/status` | Service health + node counts |
| `GET` | `/prom-metrics` | Prometheus text-format metrics endpoint |

---

## Configuration

### Master — `/etc/polaris/master.env`

| Variable | Default | Description |
|---|---|---|
| `POLARIS_DB_HOST` | `localhost` | PostgreSQL host |
| `POLARIS_DB_PORT` | `5432` | PostgreSQL port |
| `POLARIS_DB_NAME` | `polaris` | Database name |
| `POLARIS_DB_USER` | `polaris` | Database user |
| `POLARIS_DB_PASSWORD` | `polaris_secret_2024` | Database password |
| `POLARIS_API_HOST` | `0.0.0.0` | API bind address |
| `POLARIS_API_PORT` | `8000` | API listen port |
| `PROMETHEUS_PORT` | `9090` | Prometheus port |
| `GRAFANA_PORT` | `3000` | Grafana port |
| `GRAFANA_PASSWORD` | `admin` | Grafana admin password |
| `HEARTBEAT_TIMEOUT` | `120` | Seconds before node → offline |
| `POLARIS_SMTP_HOST` | _(empty)_ | SMTP server hostname (enables email alerts) |
| `POLARIS_SMTP_PORT` | `587` | SMTP port (TLS/STARTTLS) |
| `POLARIS_SMTP_USER` | _(empty)_ | SMTP login username |
| `POLARIS_SMTP_PASS` | _(empty)_ | SMTP password / app password |
| `POLARIS_ALERT_EMAIL` | _(empty)_ | Recipient address for alert emails |

### Worker — `/opt/polaris/worker-agent/config.py`

Edit the file directly or set environment variables before starting the service.

| Variable | Default | Description |
|---|---|---|
| `POLARIS_CPU_THRESHOLD` | `90` | CPU % to trigger a `high_cpu` alert |
| `POLARIS_MEMORY_THRESHOLD` | `90` | Memory % to trigger a `high_memory` alert |
| `POLARIS_DISK_THRESHOLD` | `90` | Disk % to trigger a `high_disk` alert |
| `POLARIS_METRICS_INTERVAL` | `30` | Metrics send interval (s) |
| `POLARIS_HEARTBEAT_INTERVAL` | `60` | Heartbeat interval (s) |
| `POLARIS_ALERT_SUSTAIN` | `0` | Seconds threshold must be breached before alerting (`0` = immediate) |
| `POLARIS_REBOOT_CPU_THRESHOLD` | `95` | CPU % to trigger auto-reboot |
| `POLARIS_REBOOT_MEMORY_THRESHOLD` | `95` | Memory % to trigger auto-reboot |
| `POLARIS_REBOOT_SUSTAIN` | `180` | Seconds threshold must be breached before auto-reboot (3 min) |

To **enable auto-reboot**, set `REBOOT_ENABLED = True` in config.py (disabled by default):

```bash
sudo nano /opt/polaris/worker-agent/config.py
# Set: REBOOT_ENABLED = True
sudo systemctl restart polaris-agent
```

Config file location per OS:

| OS | Path |
|---|---|
| Linux | `/etc/polaris/agent.json` |
| Windows | `C:\ProgramData\Polaris\agent.json` |

---

## Email Alerts

Polaris sends an email for every alert (high CPU, high memory, high disk, SSH failure, auto-reboot) when SMTP is configured. No extra dependencies — uses Python's built-in `smtplib`.

### Option 1 — Gmail (Recommended)

1. **Enable 2-Step Verification** on your Google account.
2. Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) and create an App Password (select "Mail" + "Other").
3. Copy the 16-character password shown.

Edit `/etc/polaris/master.env` on the master:

```bash
sudo nano /etc/polaris/master.env
```

Uncomment and fill in the SMTP block:

```env
POLARIS_SMTP_HOST=smtp.gmail.com
POLARIS_SMTP_PORT=587
POLARIS_SMTP_USER=you@gmail.com
POLARIS_SMTP_PASS=abcd efgh ijkl mnop
POLARIS_ALERT_EMAIL=alerts@example.com
```

Restart the master:

```bash
sudo systemctl restart polaris-master
```

### Option 2 — Other SMTP Providers

| Provider | Host | Port |
|---|---|---|
| Outlook / Hotmail | `smtp.office365.com` | `587` |
| Yahoo Mail | `smtp.mail.yahoo.com` | `587` |
| SendGrid | `smtp.sendgrid.net` | `587` |
| Custom / self-hosted | your SMTP host | `587` or `465` |

Use the same env vars — just change `POLARIS_SMTP_HOST` and credentials.

### Test Email

Trigger a test by sending a manual alert via the API:

```bash
curl -X POST http://localhost:8000/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "<your-agent-id>",
    "alert_type": "test_alert",
    "message": "This is a test alert from Polaris Monitor",
    "severity": "warning"
  }'
```

Check the master logs to confirm delivery:

```bash
journalctl -u polaris-master -n 20 --no-pager | grep email
# Expected: [email] Alert sent: [WARNING] test_alert — worker-01
```

### Email Format

Each alert email contains:
- Severity badge (color-coded: red = critical, orange = warning)
- Node hostname and IP address
- Alert type and message
- UTC timestamp

---

## Ports & Firewall Rules

### Master Server (inbound)

| Port | From | Purpose |
|---|---|---|
| 22 | Admin IPs | SSH |
| 8000 | Worker subnet | Polaris Master API |
| 9090 | Admin IPs | Prometheus UI |
| 3000 | Admin IPs | Grafana UI |

### Worker Servers (inbound)

| Port | From | Purpose |
|---|---|---|
| 22 | Admin IPs + Master IP | SSH (master checks this every 60 s) |
| 9100 | Master IP | Node / Windows Exporter scraping |

---

## Auto-Recovery & Auto-Reboot

### SSH Check (Master-side, Linux workers only)

The master checks TCP port 22 on every registered Linux worker every **60 seconds**.
Results appear in the **SSH Check Status** table in Grafana (OK / Failed, last check time).

When the worker's own SSH checker detects a failure locally:

1. Attempts `systemctl restart sshd`
2. Rechecks after 3 seconds
3. If recovered → sends `ssh_recovered` alert (warning)
4. If still failing → sends `ssh_failure` alert (critical)

> On Windows, SSH is optional. The SSH checker skips silently.

### Auto-Reboot (Worker-side, Linux only)

When CPU or Memory stays above the reboot threshold continuously for `REBOOT_SUSTAIN_SECONDS`:

1. Sends `auto_reboot` alert to master (triggers email if configured)
2. Master pre-marks the node's reboot reason as `agent_triggered`
3. Worker executes `reboot`
4. After reboot, the **Reboot History** table in Grafana shows **Agent Auto-Reboot**

Auto-reboot is **disabled by default**. To enable:

```bash
sudo nano /opt/polaris/worker-agent/config.py
```

```python
REBOOT_ENABLED = True
REBOOT_CPU_THRESHOLD    = 95   # reboot if CPU  >= 95% for REBOOT_SUSTAIN_SECONDS
REBOOT_MEMORY_THRESHOLD = 95   # reboot if RAM  >= 95% for REBOOT_SUSTAIN_SECONDS
REBOOT_SUSTAIN_SECONDS  = 180  # 3 minutes
```

```bash
sudo systemctl restart polaris-agent
```

### Reboot Reason Detection

The **Reboot History** table classifies each reboot:

| Reason | Meaning |
|---|---|
| **Manual** | Node was rebooted with `sudo reboot` or `sudo shutdown -r` |
| **System / Crash** | Kernel panic, OOM kill, power failure, or AWS stop/start |
| **Agent Auto-Reboot** | Polaris agent triggered the reboot due to sustained high resource usage |

Detection uses the systemd journal (`journalctl`), which persists across AWS stop/start.

---

## Alert Thresholds

| Alert Type | Default Threshold | Severity | Sustain Window |
|---|---|---|---|
| `high_cpu` | CPU > 90% | warning | immediate |
| `high_memory` | Memory > 90% | warning | immediate |
| `high_disk` | Disk > 90% | critical | immediate |
| `ssh_failure` | SSH port 22 unreachable | critical | immediate |
| `ssh_recovered` | SSH back up | warning | immediate |
| `auto_reboot` | CPU > 95% or Memory > 95% | critical | 3 min (180s) |

All thresholds are configurable — see [Worker Configuration](#worker----optpolarisworker-agentconfigpy).

---

## Troubleshooting

### Master API not responding

```bash
systemctl status polaris-master
journalctl -u polaris-master -n 50 --no-pager

# Common fix: PostgreSQL not ready
systemctl restart postgresql
systemctl restart polaris-master
```

### Worker cannot connect to master

```bash
# Test from the worker
curl http://10.0.0.10:8000/
# Expected: {"service":"Polaris Master Agent","version":"1.0.0",...}
```

If it fails: verify port 8000 is open in the master's security group / firewall.

### Token rejected (401)

```bash
polaris-master token        # list active tokens
polaris-master token --new  # generate new one
```

### Node shows as Offline

```bash
# On worker
systemctl status polaris-agent
journalctl -u polaris-agent -n 30 --no-pager
sudo systemctl restart polaris-agent
```

### Prometheus shows no workers

```bash
cat /etc/prometheus/file_sd/targets.json   # should have worker entries
curl http://localhost:9090/api/v1/targets   # Prometheus target state
sudo systemctl restart prometheus
```

### Grafana shows no data

```bash
# Re-run Grafana setup
sudo polaris-master init --skip-install
```

### Email alerts not arriving

```bash
# Check master logs
journalctl -u polaris-master -n 30 --no-pager | grep -i email

# Verify settings are loaded
sudo grep SMTP /etc/polaris/master.env

# Common issues:
# - Gmail: use an App Password, not your account password
# - Gmail: 2-Step Verification must be enabled first
# - Firewall: master must be able to reach port 587 outbound
```

### SSH Check always shows "Failed" after stopping sshd

On modern Ubuntu, stopping `ssh.service` alone is not enough because the socket
(`ssh.socket`) keeps port 22 open. Stop both:

```bash
sudo systemctl stop ssh.socket ssh
# To restore:
sudo systemctl start ssh.socket ssh
```

### Windows — polaris command not found

```powershell
# Refresh PATH in current session
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("PATH","User")

# Or open a new Administrator PowerShell window
```

### Windows — service won't start

```powershell
# Check NSSM service log
Get-Content "$env:ProgramData\Polaris\logs\agent-error.log" -Tail 30

# Restart
Restart-Service polaris-agent
```

### View all logs

```bash
# Linux — master
journalctl -u polaris-master    -f
journalctl -u prometheus        -f
journalctl -u grafana-server    -f

# Linux — worker
journalctl -u polaris-agent     -f
journalctl -u node-exporter     -f
```

```powershell
# Windows — worker
Get-Content "$env:ProgramData\Polaris\logs\agent.log"       -Tail 50 -Wait
Get-Content "$env:ProgramData\Polaris\logs\agent-error.log" -Tail 50 -Wait
```

### Reset a worker completely

```bash
# Linux
sudo polaris leave
sudo systemctl stop node-exporter
sudo systemctl disable node-exporter
sudo polaris join --master-ip 10.0.0.10 --token <NEW_TOKEN>
```

```powershell
# Windows
polaris leave
Stop-Service polaris-node-exporter; sc.exe delete polaris-node-exporter
polaris join --master-ip 10.0.0.10 --token <NEW_TOKEN>
```

---

## Quick Reference Card

```
─────────────────────────────────────────────────────────────────────
  INSTALL
  sudo bash install.sh master                    # Master (Linux)
  sudo bash install.sh agent \                   # Agent  (Linux)
       --master-ip 10.0.0.10 --token TOKEN
  .\install.ps1 -MasterIP 10.0.0.10 -Token TOKEN # Agent  (Windows)

  MASTER CLI
  polaris-master init           Initialize all components
  polaris-master token          Show join token
  polaris-master token --new    Generate new token
  polaris-master nodes          List nodes
  polaris-master nodes --watch  Live node view
  polaris-master alerts         Recent alerts
  polaris-master status         Service health

  WORKER CLI
  polaris join --master-ip X --token Y   Join master
  polaris status                          Live metrics
  polaris leave                           Leave master

  DASHBOARDS
  http://<MASTER_IP>:8000        Polaris API
  http://<MASTER_IP>:8000/docs   Swagger UI
  http://<MASTER_IP>:9090        Prometheus
  http://<MASTER_IP>:3000        Grafana

  EMAIL ALERTS  (edit /etc/polaris/master.env)
  POLARIS_SMTP_HOST=smtp.gmail.com
  POLARIS_SMTP_PORT=587
  POLARIS_SMTP_USER=you@gmail.com
  POLARIS_SMTP_PASS=<16-char-app-password>
  POLARIS_ALERT_EMAIL=alerts@example.com
─────────────────────────────────────────────────────────────────────
```
