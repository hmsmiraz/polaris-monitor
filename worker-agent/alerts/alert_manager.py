import os
import time
import requests
from collector.metrics_collector import collect


# Track when each threshold was first breached
_breach_start: dict = {}


def _send_alert(master_ip: str, master_port: int, agent_id: str,
                alert_type: str, message: str, severity: str = "warning"):
    url = f"http://{master_ip}:{master_port}/api/v1/alerts"
    payload = {
        "agent_id": agent_id,
        "alert_type": alert_type,
        "message": message,
        "severity": severity,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print(f"[alert] Sent {alert_type}: {message}")
        return True
    except Exception as e:
        print(f"[alert] Failed to send {alert_type}: {e}")
        return False


def _check_threshold(
    key: str, current_value: float, threshold: float, sustain: int
) -> bool:
    """Returns True when value has been above threshold for sustain seconds."""
    now = time.time()
    if current_value >= threshold:
        if key not in _breach_start:
            _breach_start[key] = now
        elif now - _breach_start[key] >= sustain:
            return True
    else:
        _breach_start.pop(key, None)
    return False


def _do_reboot(reason: str, master_ip: str, master_port: int, agent_id: str):
    _send_alert(master_ip, master_port, agent_id,
                alert_type="auto_reboot",
                message=f"Auto-rebooting node: {reason}",
                severity="critical")
    time.sleep(2)
    print(f"[alert] Auto-reboot triggered: {reason}")
    os.system("reboot")


def check_and_alert(master_ip: str, master_port: int, agent_id: str):
    from config import (
        CPU_ALERT_THRESHOLD, MEMORY_ALERT_THRESHOLD,
        DISK_ALERT_THRESHOLD, ALERT_SUSTAIN_SECONDS,
        REBOOT_ENABLED, REBOOT_CPU_THRESHOLD,
        REBOOT_MEMORY_THRESHOLD, REBOOT_SUSTAIN_SECONDS,
    )

    metrics = collect()

    if _check_threshold("cpu", metrics["cpu_percent"], CPU_ALERT_THRESHOLD, ALERT_SUSTAIN_SECONDS):
        _send_alert(
            master_ip, master_port, agent_id,
            alert_type="high_cpu",
            message=f"CPU usage is {metrics['cpu_percent']:.1f}% (threshold: {CPU_ALERT_THRESHOLD}%)",
            severity="warning",
        )
        _breach_start.pop("cpu", None)

    if _check_threshold("memory", metrics["memory_percent"], MEMORY_ALERT_THRESHOLD, ALERT_SUSTAIN_SECONDS):
        _send_alert(
            master_ip, master_port, agent_id,
            alert_type="high_memory",
            message=f"Memory usage is {metrics['memory_percent']:.1f}% (threshold: {MEMORY_ALERT_THRESHOLD}%)",
            severity="warning",
        )
        _breach_start.pop("memory", None)

    if _check_threshold("disk", metrics["disk_percent"], DISK_ALERT_THRESHOLD, ALERT_SUSTAIN_SECONDS):
        _send_alert(
            master_ip, master_port, agent_id,
            alert_type="high_disk",
            message=f"Disk usage is {metrics['disk_percent']:.1f}% (threshold: {DISK_ALERT_THRESHOLD}%)",
            severity="critical",
        )
        _breach_start.pop("disk", None)

    if REBOOT_ENABLED:
        if _check_threshold("reboot_cpu", metrics["cpu_percent"],
                            REBOOT_CPU_THRESHOLD, REBOOT_SUSTAIN_SECONDS):
            _do_reboot(
                f"CPU {metrics['cpu_percent']:.1f}% >= {REBOOT_CPU_THRESHOLD}% "
                f"for {REBOOT_SUSTAIN_SECONDS}s",
                master_ip, master_port, agent_id,
            )
            return
        if _check_threshold("reboot_mem", metrics["memory_percent"],
                            REBOOT_MEMORY_THRESHOLD, REBOOT_SUSTAIN_SECONDS):
            _do_reboot(
                f"Memory {metrics['memory_percent']:.1f}% >= {REBOOT_MEMORY_THRESHOLD}% "
                f"for {REBOOT_SUSTAIN_SECONDS}s",
                master_ip, master_port, agent_id,
            )


def send_custom_alert(
    master_ip: str, master_port: int, agent_id: str,
    alert_type: str, message: str, severity: str = "warning"
):
    _send_alert(master_ip, master_port, agent_id, alert_type, message, severity)
