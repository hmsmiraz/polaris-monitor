import psutil
import requests


def send(master_ip: str, master_port: int, agent_id: str) -> bool:
    url = f"http://{master_ip}:{master_port}/api/v1/heartbeat"
    try:
        r = requests.post(url, json={
            "agent_id": agent_id,
            "boot_time": psutil.boot_time(),
        }, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[heartbeat] Failed: {e}")
        return False
