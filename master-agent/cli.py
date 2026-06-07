#!/usr/bin/env python3
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import click
import requests
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def _get_private_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _get_public_ip() -> str:
    for url in ["http://169.254.169.254/latest/meta-data/public-ipv4",
                "https://ifconfig.me", "https://api.ipify.org"]:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                return r.text.strip()
        except Exception:
            continue
    return "unknown"


def _api_url(path: str) -> str:
    from config import API_PORT
    return f"http://localhost:{API_PORT}{path}"


def _save_master_config(token: str, private_ip: str, public_ip: str):
    from config import CONFIG_DIR, MASTER_CONFIG_FILE, API_PORT, PROMETHEUS_PORT, GRAFANA_PORT
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(MASTER_CONFIG_FILE, "w") as f:
        json.dump({
            "token": token,
            "private_ip": private_ip,
            "public_ip": public_ip,
            "api_port": API_PORT,
            "prometheus_port": PROMETHEUS_PORT,
            "grafana_port": GRAFANA_PORT,
        }, f, indent=2)
    os.chmod(MASTER_CONFIG_FILE, 0o600)


def _run_service(name: str) -> bool:
    return subprocess.run(f"systemctl start {name}", shell=True, capture_output=True).returncode == 0


def _enable_service(name: str):
    subprocess.run(f"systemctl enable {name}", shell=True, capture_output=True)


@click.group()
def cli():
    """Polaris Master Agent — Server Monitoring Platform"""
    pass


@cli.command()
@click.option("--skip-install", is_flag=True, help="Skip software installation (re-init only)")
def init(skip_install):
    """Initialize the master server — installs and configures all components."""
    if os.geteuid() != 0:
        console.print("[red]Error:[/red] This command must be run as root (sudo)")
        sys.exit(1)

    console.print("\n[bold cyan]Polaris Master Agent — Initialization[/bold cyan]\n")

    private_ip = _get_private_ip()
    public_ip  = _get_public_ip()

    if not skip_install:
        console.print("[bold]Step 1/6:[/bold] Setting up PostgreSQL...")
        from installers import postgres_installer
        postgres_installer.setup()

        console.print("[bold]Step 2/6:[/bold] Setting up Prometheus...")
        from installers import prometheus_installer
        prometheus_installer.setup()

        console.print("[bold]Step 3/6:[/bold] Setting up Grafana...")
        from installers import grafana_installer
        grafana_installer.setup()

    console.print("[bold]Step 4/6:[/bold] Configuring Prometheus...")
    from prometheus.config_manager import write_prometheus_config
    write_prometheus_config()
    Path("/etc/prometheus/file_sd").mkdir(parents=True, exist_ok=True)
    Path("/etc/prometheus/file_sd/targets.json").write_text("[]")
    subprocess.run("chown -R prometheus:prometheus /etc/prometheus", shell=True, capture_output=True)
    console.print("  [OK] Prometheus configured")

    console.print("[bold]Step 5/6:[/bold] Initializing database...")
    from database.connection import init_pool
    from database.schema import create_tables
    init_pool()
    create_tables()
    from services.token_service import create_token
    token = create_token()
    _save_master_config(token, private_ip, public_ip)
    console.print("  [OK] Database ready, join token generated")

    console.print("[bold]Step 6/6:[/bold] Starting all services...")
    _install_systemd_service()
    for svc in ["postgresql", "prometheus", "grafana-server", "polaris-master"]:
        _enable_service(svc)
        status = "[green]started[/green]" if _run_service(svc) else "[yellow]check manually[/yellow]"
        console.print(f"  {svc:<20} {status}")

    console.print("\n  Configuring Grafana dashboards...")
    from grafana.dashboard_manager import setup_grafana
    setup_grafana()

    from config import API_PORT, PROMETHEUS_PORT, GRAFANA_PORT
    console.print("\n" + "═" * 58)
    console.print("[bold green]  Polaris Master Initialized Successfully[/bold green]\n")
    console.print(f"  [bold]Master IP:[/bold]      {private_ip}")
    console.print(f"  [bold]Public IP:[/bold]      {public_ip}\n")
    console.print(f"  [bold yellow]Join Token:[/bold yellow]")
    console.print(f"  [bold white on blue]  {token}  [/bold white on blue]\n")
    console.print(f"  [bold]Master API:[/bold]     http://{private_ip}:{API_PORT}")
    console.print(f"  [bold]Prometheus:[/bold]     http://{private_ip}:{PROMETHEUS_PORT}")
    console.print(f"  [bold]Grafana:[/bold]        http://{private_ip}:{GRAFANA_PORT}\n")
    console.print(f"  [bold]Worker Join Command:[/bold]")
    console.print(f"  polaris join --master-ip {private_ip} --token {token}")
    console.print("═" * 58 + "\n")


@cli.command()
@click.option("--new", is_flag=True, help="Generate a new token")
def token(new):
    """Show active join tokens, or generate a new one."""
    from database.connection import init_pool
    from services.token_service import get_active_tokens, create_token
    init_pool()
    if new:
        t = create_token()
        console.print(f"[bold green]New Join Token:[/bold green] {t}")
        return
    tokens = get_active_tokens()
    if not tokens:
        console.print("[yellow]No active tokens. Run: polaris-master token --new[/yellow]")
        return
    table = Table(title="Active Join Tokens", box=box.ROUNDED)
    table.add_column("Token", style="cyan")
    table.add_column("Created At")
    table.add_column("Expires At")
    for t in tokens:
        table.add_row(t["token"], str(t["created_at"])[:19],
                      str(t["expires_at"])[:19] if t["expires_at"] else "Never")
    console.print(table)


@cli.command()
@click.option("--watch", is_flag=True, help="Auto-refresh every 5 seconds")
def nodes(watch):
    """List all registered nodes."""
    from database.connection import init_pool
    from services.node_service import get_all_nodes
    init_pool()

    def _display():
        node_list = get_all_nodes()
        table = Table(title=f"Registered Nodes ({len(node_list)} total)", box=box.ROUNDED)
        table.add_column("Agent ID",   style="cyan")
        table.add_column("Hostname")
        table.add_column("Private IP")
        table.add_column("Public IP")
        table.add_column("OS",         max_width=22)
        table.add_column("Status")
        table.add_column("Last Seen")
        for n in node_list:
            sc = "green" if n["status"] == "online" else "red"
            table.add_row(n["agent_id"], n["hostname"] or "-",
                          n["private_ip"] or "-", n["public_ip"] or "-",
                          (n["os_info"] or "-")[:22],
                          f"[{sc}]{n['status']}[/{sc}]",
                          str(n["last_seen"])[:19])
        console.print(table)

    if watch:
        while True:
            console.clear()
            _display()
            time.sleep(5)
    else:
        _display()


@cli.command()
@click.option("--limit", default=20, help="Number of alerts to show")
def alerts(limit):
    """Show recent alerts from all nodes."""
    from database.connection import init_pool
    from services.alert_service import get_alerts
    init_pool()
    alert_list = get_alerts(limit=limit)
    if not alert_list:
        console.print("[green]No alerts.[/green]")
        return
    table = Table(title="Alerts", box=box.ROUNDED)
    table.add_column("ID",         style="dim")
    table.add_column("Agent ID",   style="cyan")
    table.add_column("Type")
    table.add_column("Severity")
    table.add_column("Message",    max_width=55)
    table.add_column("Status")
    table.add_column("Created At")
    for a in alert_list:
        sc  = "red" if a["severity"] == "critical" else "yellow"
        res = "[green]resolved[/green]" if a["resolved"] else "[red]active[/red]"
        table.add_row(str(a["id"]), a["agent_id"], a["alert_type"],
                      f"[{sc}]{a['severity']}[/{sc}]",
                      a["message"][:55], res, str(a["created_at"])[:19])
    console.print(table)


@cli.command()
def status():
    """Show live system status."""
    try:
        r = requests.get(_api_url("/api/v1/status"), timeout=5)
        data = r.json()
        console.print("\n[bold cyan]Polaris Master Agent — System Status[/bold cyan]\n")
        n = data["nodes"]
        console.print(f"[bold]Nodes:[/bold]  Total={n['total']}  "
                      f"Online=[green]{n['online']}[/green]  "
                      f"Offline=[red]{n['offline']}[/red]\n")
        console.print("[bold]Services:[/bold]")
        for svc, state in data.get("services", {}).items():
            color = "green" if state == "active" else "red"
            console.print(f"  {svc:<22} [{color}]{state}[/{color}]")
    except requests.ConnectionError:
        console.print("[red]Error:[/red] Cannot connect to Polaris Master API. Is it running?")
        sys.exit(1)


def _install_systemd_service():
    install_dir = Path(__file__).parent
    venv_python = install_dir / "venv" / "bin" / "python"
    python_bin  = str(venv_python) if venv_python.exists() else sys.executable
    service = f"""\
[Unit]
Description=Polaris Master Agent
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory={install_dir}
EnvironmentFile=/etc/polaris/master.env
ExecStart={python_bin} {install_dir}/main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    with open("/etc/systemd/system/polaris-master.service", "w") as f:
        f.write(service)
    subprocess.run("systemctl daemon-reload", shell=True, capture_output=True)


if __name__ == "__main__":
    cli()
