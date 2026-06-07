# Polaris Monitor

A lightweight Python-based server monitoring and node management platform.
One master controls many workers — everything installs with a single command.

```
sudo bash install.sh master                                  # on master
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
- [Ports & Firewall Rules](#ports--firewall-rules)
- [Auto-Recovery](#auto-recovery)
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
│  │  /api/v1/alerts      │──▶│  /etc/prometheus/file_sd/       │  │
│  │  /api/v1/nodes       │   │  targets.json  (auto-updated)   │  │
│  │  /api/v1/status      │   └──────────────┬──────────────────┘  │
│  └─────────────────────┘                   │                     │
│                                            ▼                     │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  Prometheus  :9090                                      │     │
│  │  Scrapes worker exporters every 15 s via file_sd        │     │
│  └───────────────────────┬─────────────────────────────────┘     │
│                          │                                       │
│  ┌───────────────────────▼─────────────────────────────────┐     │
│  │  Grafana  :3000  (auto-provisioned dashboard)           │     │
│  └─────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
              ▲  register / heartbeat / metrics / alerts
              │           HTTP  :8000
  ┌───────────┴──────────────────────────────────────────────────┐
  │           WORKER NODE  (Linux or Windows)                    │
  │                                                              │
  │  Thread 1  Heartbeat      →  every  60 s                    │
  │  Thread 2  Metrics        →  every  30 s                    │
  │  Thread 3  Alert Checker  →  every  30 s                    │
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
│   │       ├── alerts.py            GET/POST /api/v1/alerts
│   │       ├── nodes.py             GET /api/v1/nodes[/{id}]
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
│   │   └── alert_service.py         Alert CRUD
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
    ├── config.py                    Cross-platform config paths
    ├── requirements.txt
    │
    ├── registration/client.py       Register with master → receive agent_id
    ├── collector/metrics_collector.py   psutil metrics
    ├── heartbeat/heartbeat.py       POST /api/v1/heartbeat
    ├── alerts/alert_manager.py      Threshold checks + sustain window
    ├── ssh_checker/ssh_checker.py   Linux: check/restart SSH; Windows: skip
    └── services/node_exporter.py    Linux: node_exporter; Windows: windows_exporter
```

---

## Part 1 — Master Setup (Linux)

### Step 1 — Clone the Repository

```bash
git clone https://github.com/your-org/polaris-monitor.git
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
git clone https://github.com/your-org/polaris-monitor.git
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
| Password | `admin` |

Go to **Dashboards → Polaris Monitor — Node Overview**. Panels:

| Panel | Shows |
|---|---|
| Online Nodes | Live count |
| Offline Nodes | Live count |
| Total Nodes | All registered |
| CPU Usage % | Time series per node |
| Memory Usage % | Time series per node |
| Disk Usage % | Time series per node |
| Load Average (1m) | Time series per node |
| Network Receive | Bytes/sec per interface |
| Network Transmit | Bytes/sec per interface |
| Node Status Table | Instance / Status / Colour |

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
| `POST` | `/alerts` | Worker sends an alert |
| `GET` | `/nodes` | List all nodes |
| `GET` | `/nodes/{agent_id}` | Node details |
| `DELETE` | `/nodes/{agent_id}` | Remove a node |
| `GET` | `/alerts` | List alerts (`?resolved=false&agent_id=…`) |
| `PUT` | `/alerts/{id}/resolve` | Resolve an alert |
| `GET` | `/status` | Service health + node counts |

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

### Worker — environment variables

| Variable | Default | Description |
|---|---|---|
| `POLARIS_CPU_THRESHOLD` | `90` | CPU % alert threshold |
| `POLARIS_MEMORY_THRESHOLD` | `90` | Memory % alert threshold |
| `POLARIS_DISK_THRESHOLD` | `90` | Disk % alert threshold |
| `POLARIS_METRICS_INTERVAL` | `30` | Metrics send interval (s) |
| `POLARIS_HEARTBEAT_INTERVAL` | `60` | Heartbeat interval (s) |
| `POLARIS_SSH_CHECK_INTERVAL` | `1800` | SSH check interval (s) |
| `POLARIS_ALERT_SUSTAIN` | `300` | Sustain seconds before alerting |

Config file location per OS:

| OS | Path |
|---|---|
| Linux | `/etc/polaris/agent.json` |
| Windows | `C:\ProgramData\Polaris\agent.json` |

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
| 22 | Admin IPs | SSH |
| 9100 | Master IP | Node / Windows Exporter scraping |

---

## Auto-Recovery

### SSH Failure (Linux only)

When SSH is not running or port 22 is closed:

1. Attempts `systemctl restart sshd` (or `ssh`)
2. Rechecks after 3 seconds
3. If recovered → sends `ssh_recovered` alert (warning)
4. If still failing → sends `ssh_failure` alert (critical)

> On Windows, SSH is optional. The SSH checker skips silently.

### High Resource Usage

When CPU / Memory / Disk exceeds the threshold **continuously** for `POLARIS_ALERT_SUSTAIN`
seconds (default 5 minutes):

1. Sends alert to master
2. Resets the sustain timer
3. Alerts again if threshold remains breached for another 5 minutes

> Servers are **never automatically rebooted** in this version.
> The architecture supports adding a reboot command via the master API in future.

---

## Alert Thresholds

| Alert Type | Default | Severity | Sustain Window |
|---|---|---|---|
| `high_cpu` | CPU > 90% | warning | 5 min |
| `high_memory` | Memory > 90% | warning | 5 min |
| `high_disk` | Disk > 90% | critical | 5 min |
| `ssh_failure` | SSH down | critical | immediate |
| `ssh_recovered` | SSH back up | warning | immediate |

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
  polaris-master init        Initialize all components
  polaris-master token       Show join token
  polaris-master token --new Generate new token
  polaris-master nodes       List nodes
  polaris-master nodes --watch  Live node view
  polaris-master alerts      Recent alerts
  polaris-master status      Service health

  WORKER CLI
  polaris join --master-ip X --token Y   Join master
  polaris status                          Live metrics
  polaris leave                           Leave master

  DASHBOARDS
  http://<MASTER_IP>:8000   Polaris API  (admin)
  http://<MASTER_IP>:8000/docs   Swagger UI
  http://<MASTER_IP>:9090   Prometheus
  http://<MASTER_IP>:3000   Grafana  (admin / admin)
─────────────────────────────────────────────────────────────────────
```

