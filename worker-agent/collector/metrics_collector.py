import platform
import socket
import time
import psutil
import requests


def collect() -> dict:
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    load = psutil.getloadavg()
    boot_time = psutil.boot_time()
    uptime = int(time.time() - boot_time)

    return {
        "cpu_percent": cpu,
        "memory_percent": mem.percent,
        "memory_total_mb": mem.total // (1024 * 1024),
        "memory_used_mb": mem.used // (1024 * 1024),
        "disk_percent": disk.percent,
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
        "disk_used_gb": round(disk.used / (1024 ** 3), 2),
        "load_avg_1": round(load[0], 2),
        "load_avg_5": round(load[1], 2),
        "load_avg_15": round(load[2], 2),
        "uptime_seconds": uptime,
        "hostname": socket.gethostname(),
        "private_ip": _get_private_ip(),
        "os_info": f"{platform.system()} {platform.release()}",
        "kernel_version": platform.uname().release,
    }


def _get_private_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def send_metrics(master_ip: str, master_port: int, agent_id: str):
    data = collect()
    data["agent_id"] = agent_id

    url = f"http://{master_ip}:{master_port}/api/v1/metrics"
    try:
        r = requests.post(url, json=data, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[metrics] Failed to send: {e}")
        return False
