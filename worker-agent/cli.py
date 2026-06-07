#!/usr/bin/env python3
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import click
import requests
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()
_IS_WINDOWS = sys.platform == "win32"


@click.group()
def cli():
    """Polaris Worker Agent — Node Management"""
    pass


@cli.command()
@click.option("--master-ip",           required=True,  help="Master server IP address")
@click.option("--master-port",         default=8000,   show_default=True, help="Master API port")
@click.option("--token",               required=True,  help="Join token from master")
@click.option("--node-exporter-port",  default=9100,   show_default=True, help="Exporter metrics port")
@click.option("--skip-install",        is_flag=True,   help="Skip exporter installation")
def join(master_ip, master_port, token, node_exporter_port, skip_install):
    """Join this node to a Polaris master server."""
    if not _IS_WINDOWS and os.geteuid() != 0:
        console.print("[red]Error:[/red] This command must be run as root (sudo)")
        sys.exit(1)

    if _IS_WINDOWS:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            console.print("[red]Error:[/red] This command must be run as Administrator")
            sys.exit(1)

    console.print(f"\n[bold cyan]Joining Polaris Master at {master_ip}:{master_port}...[/bold cyan]\n")

    # Step 1: Register
    console.print("[bold]Step 1/3:[/bold] Registering with master...")
    from registration.client import register
    try:
        agent_id = register(master_ip, master_port, token, node_exporter_port)
    except requests.HTTPError as e:
        msg = "Invalid or expired token" if e.response.status_code == 401 else str(e)
        console.print(f"[red]Error:[/red] {msg}")
        sys.exit(1)
    except requests.ConnectionError:
        console.print(f"[red]Error:[/red] Cannot reach master at {master_ip}:{master_port}")
        sys.exit(1)
    console.print(f"  [OK] Registered — Agent ID: [bold cyan]{agent_id}[/bold cyan]")

    # Step 2: Save config
    console.print("[bold]Step 2/3:[/bold] Saving configuration...")
    from config import save_config
    save_config({
        "agent_id":            agent_id,
        "master_ip":           master_ip,
        "master_port":         master_port,
        "token":               token,
        "node_exporter_port":  node_exporter_port,
    })
    console.print("  [OK] Configuration saved")

    # Step 3: Install exporter
    if not skip_install:
        console.print("[bold]Step 3/3:[/bold] Installing metrics exporter...")
        from services.node_exporter import setup
        setup(port=node_exporter_port)
    else:
        console.print("[bold]Step 3/3:[/bold] [dim]Skipping exporter install[/dim]")

    # Install and start agent service
    _install_agent_service()
    _start_agent_service()

    console.print("\n" + "═" * 50)
    console.print("[bold green]  Successfully Joined Master[/bold green]\n")
    console.print(f"  [bold]Agent ID:[/bold]       {agent_id}")
    console.print(f"  [bold]Master:[/bold]         {master_ip}:{master_port}")
    console.print(f"  [bold]Exporter port:[/bold]  {node_exporter_port}")
    console.print(f"  [bold]Status:[/bold]         [green]Connected[/green]")
    console.print("═" * 50 + "\n")
    console.print("Run [bold]polaris status[/bold] to verify the agent is running.")


@cli.command()
def status():
    """Show agent status and live system metrics."""
    from config import load_config, is_configured
    if not is_configured():
        console.print("[yellow]Not configured. Run: polaris join --master-ip <IP> --token <TOKEN>[/yellow]")
        sys.exit(1)

    cfg = load_config()
    svc_status = _service_status()

    from collector.metrics_collector import collect
    metrics = collect()

    console.print("\n[bold cyan]Polaris Worker Agent — Status[/bold cyan]\n")
    table = Table(box=box.ROUNDED, show_header=False)
    table.add_column("Key",   style="bold", min_width=20)
    table.add_column("Value")

    sc = "green" if svc_status == "active" else "red"
    table.add_row("Agent ID",           cfg["agent_id"])
    table.add_row("Master",             f"{cfg['master_ip']}:{cfg['master_port']}")
    table.add_row("Service",            f"[{sc}]{svc_status}[/{sc}]")
    table.add_row("Platform",           sys.platform)
    table.add_row("",                   "")
    table.add_row("Hostname",           metrics["hostname"])
    table.add_row("CPU Usage",          f"{metrics['cpu_percent']:.1f}%")
    table.add_row("Memory Usage",       f"{metrics['memory_percent']:.1f}%  "
                                         f"({metrics['memory_used_mb']} MB / {metrics['memory_total_mb']} MB)")
    table.add_row("Disk Usage",         f"{metrics['disk_percent']:.1f}%  "
                                         f"({metrics['disk_used_gb']} GB / {metrics['disk_total_gb']} GB)")
    table.add_row("Load Avg (1/5/15m)", f"{metrics['load_avg_1']} / {metrics['load_avg_5']} / {metrics['load_avg_15']}")
    uptime_h = metrics["uptime_seconds"] // 3600
    uptime_m = (metrics["uptime_seconds"] % 3600) // 60
    table.add_row("Uptime",             f"{uptime_h}h {uptime_m}m")
    table.add_row("OS",                 metrics["os_info"])
    console.print(table)


@cli.command()
def leave():
    """Unregister this node from the master server."""
    from config import load_config, is_configured
    if not is_configured():
        console.print("[yellow]Agent is not configured.[/yellow]")
        sys.exit(1)
    cfg = load_config()
    console.print(f"Leaving master {cfg['master_ip']}...")
    from registration.client import leave as do_leave
    do_leave(cfg["master_ip"], cfg["master_port"], cfg["agent_id"])
    _stop_agent_service()
    console.print("[green]Successfully left master. Agent stopped.[/green]")


# ── Service management helpers ─────────────────────────────────────────────────

def _service_status() -> str:
    if _IS_WINDOWS:
        r = subprocess.run("sc query polaris-agent", shell=True, capture_output=True, text=True)
        return "active" if "RUNNING" in r.stdout else "inactive"
    r = subprocess.run("systemctl is-active polaris-agent", shell=True, capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def _install_agent_service():
    if _IS_WINDOWS:
        _install_windows_service()
    else:
        _install_systemd_service()


def _start_agent_service():
    if _IS_WINDOWS:
        subprocess.run("sc start polaris-agent", shell=True, capture_output=True)
    else:
        subprocess.run("systemctl enable polaris-agent", shell=True, capture_output=True)
        subprocess.run("systemctl start polaris-agent",  shell=True, capture_output=True)


def _stop_agent_service():
    if _IS_WINDOWS:
        subprocess.run("sc stop polaris-agent", shell=True, capture_output=True)
    else:
        subprocess.run("systemctl stop    polaris-agent", shell=True, capture_output=True)
        subprocess.run("systemctl disable polaris-agent", shell=True, capture_output=True)


def _install_systemd_service():
    agent_dir   = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(agent_dir, "venv", "bin", "python")
    python_bin  = venv_python if os.path.exists(venv_python) else sys.executable
    service = f"""\
[Unit]
Description=Polaris Worker Agent
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory={agent_dir}
ExecStart={python_bin} {agent_dir}/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    with open("/etc/systemd/system/polaris-agent.service", "w") as f:
        f.write(service)
    subprocess.run("systemctl daemon-reload", shell=True, capture_output=True)


def _install_windows_service():
    agent_dir   = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(agent_dir, "venv", "Scripts", "python.exe")
    python_bin  = venv_python if os.path.exists(venv_python) else sys.executable
    main_script = os.path.join(agent_dir, "main.py")

    nssm = _find_nssm()
    if nssm:
        subprocess.run(f'"{nssm}" install polaris-agent "{python_bin}" "{main_script}"',
                       shell=True, capture_output=True)
        subprocess.run(f'"{nssm}" set polaris-agent AppDirectory "{agent_dir}"',
                       shell=True, capture_output=True)
        subprocess.run(f'"{nssm}" set polaris-agent DisplayName "Polaris Worker Agent"',
                       shell=True, capture_output=True)
        subprocess.run(f'"{nssm}" set polaris-agent Start SERVICE_AUTO_START',
                       shell=True, capture_output=True)
    else:
        console.print("[yellow]  NSSM not found. Service not installed automatically.[/yellow]")
        console.print(f"  Manual start: {python_bin} {main_script}")


def _find_nssm() -> str:
    for loc in [r"C:\nssm\nssm.exe", r"C:\Windows\System32\nssm.exe",
                r"C:\ProgramData\chocolatey\bin\nssm.exe"]:
        if os.path.exists(loc):
            return loc
    r = subprocess.run("where nssm", shell=True, capture_output=True, text=True)
    if r.returncode == 0:
        return r.stdout.strip().splitlines()[0]
    return ""


if __name__ == "__main__":
    cli()
