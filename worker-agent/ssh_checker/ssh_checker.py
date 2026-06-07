"""
SSH health checker — Linux only.
On Windows, OpenSSH is optional and managed differently; we skip silently.
"""
import socket
import subprocess
import sys
import time

from alerts.alert_manager import send_custom_alert


def _is_windows() -> bool:
    return sys.platform == "win32"


def _is_port_open(host: str = "127.0.0.1", port: int = 22, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _is_ssh_service_active() -> bool:
    for name in ("sshd", "ssh"):
        r = subprocess.run(f"systemctl is-active {name}",
                           shell=True, capture_output=True, text=True)
        if r.stdout.strip() == "active":
            return True
    return False


def _restart_ssh() -> bool:
    for name in ("sshd", "ssh"):
        r = subprocess.run(f"systemctl restart {name}",
                           shell=True, capture_output=True)
        if r.returncode == 0:
            time.sleep(3)
            return True
    return False


def check(master_ip: str, master_port: int, agent_id: str):
    if _is_windows():
        # SSH is optional on Windows; skip silently
        return

    service_ok = _is_ssh_service_active()
    port_ok    = _is_port_open()

    if service_ok and port_ok:
        return

    print(f"[ssh-checker] Issue detected — service={service_ok}, port={port_ok}")

    restarted = _restart_ssh()

    if restarted and _is_ssh_service_active() and _is_port_open():
        send_custom_alert(master_ip, master_port, agent_id,
                          alert_type="ssh_recovered",
                          message="SSH was down and has been restarted successfully.",
                          severity="warning")
        print("[ssh-checker] SSH restarted successfully")
        return

    send_custom_alert(master_ip, master_port, agent_id,
                      alert_type="ssh_failure",
                      message=(f"SSH failure — service_active={service_ok}, "
                               f"port_open={port_ok}, restart_tried={restarted}"),
                      severity="critical")
    print("[ssh-checker] SSH failure — could not recover automatically")
