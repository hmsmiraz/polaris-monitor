import subprocess
import psutil
import requests

_reason_cache = None


def _try_journal() -> str:
    """Detect via systemd journal (works on AWS stop/start where wtmp is cleared)."""
    try:
        r = subprocess.run(
            "journalctl --list-boots --no-pager 2>/dev/null | wc -l",
            shell=True, capture_output=True, text=True, timeout=5
        )
        boot_count = int(r.stdout.strip() or "0")
        if boot_count < 1:
            return ""
        if boot_count < 2:
            # Only one boot on record — fresh launch or stop/start with cleared journal
            return "system"
        # Check if previous boot ended with a reboot command (vs poweroff/crash)
        r2 = subprocess.run(
            "journalctl -b -1 -n 50 --no-pager 2>/dev/null | grep -ic 'reached target.*reboot\\|starting reboot'",
            shell=True, capture_output=True, text=True, timeout=10
        )
        return "manual" if int(r2.stdout.strip() or "0") > 0 else "system"
    except Exception:
        return ""


def _try_last() -> str:
    """Fall back to wtmp-based detection (works when journal is unavailable)."""
    try:
        r = subprocess.run(
            "last -x 2>/dev/null | grep -E '^reboot|^shutdown' | head -5",
            shell=True, capture_output=True, text=True, timeout=5
        )
        events = []
        for line in r.stdout.strip().split("\n"):
            s = line.strip()
            if s.startswith("reboot"):
                events.append("reboot")
            elif s.startswith("shutdown"):
                events.append("shutdown")
        if len(events) >= 2:
            return "manual" if events[1] == "shutdown" else "system"
        if len(events) == 1:
            return "system"
        return ""
    except Exception:
        return ""


def _detect_reboot_reason() -> str:
    """Check shutdown records to determine why the node last rebooted."""
    global _reason_cache
    if _reason_cache is not None:
        return _reason_cache
    _reason_cache = _try_journal() or _try_last() or "unknown"
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
