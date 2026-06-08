import subprocess
import psutil
import requests

_reason_cache = None


def _detect_reboot_reason() -> str:
    """Check last shutdown records to determine why the node rebooted."""
    global _reason_cache
    if _reason_cache is not None:
        return _reason_cache
    try:
        result = subprocess.run(
            ["last", "-x", "-n", "10"],
            capture_output=True, text=True, timeout=5
        )
        events = []
        for line in result.stdout.strip().split("\n"):
            if line.startswith("reboot"):
                events.append("reboot")
            elif line.startswith("shutdown"):
                events.append("shutdown")
        # events are newest-first; events[0]=current boot, events[1]=what ended last session
        if len(events) >= 2:
            _reason_cache = "manual" if events[1] == "shutdown" else "system"
        else:
            _reason_cache = "unknown"
    except Exception:
        _reason_cache = "unknown"
    return _reason_cache


def send(master_ip: str, master_port: int, agent_id: str) -> bool:
    url = f"http://{master_ip}:{master_port}/api/v1/heartbeat"
    try:
        r = requests.post(url, json={
            "agent_id": agent_id,
            "boot_time": psutil.boot_time(),
            "reboot_reason": _detect_reboot_reason(),
        }, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[heartbeat] Failed: {e}")
        return False
