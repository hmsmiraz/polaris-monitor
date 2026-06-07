import socket
import platform
import requests


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
    # Try AWS metadata first, fall back to public service
    for url in [
        "http://169.254.169.254/latest/meta-data/public-ipv4",
        "https://ifconfig.me",
        "https://api.ipify.org",
    ]:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                return r.text.strip()
        except Exception:
            continue
    return None


def register(master_ip: str, master_port: int, token: str, node_exporter_port: int = 9100) -> str:
    hostname = socket.gethostname()
    private_ip = _get_private_ip()
    public_ip = _get_public_ip()
    os_info = f"{platform.system()} {platform.release()}"
    kernel = platform.uname().release

    payload = {
        "token": token,
        "hostname": hostname,
        "private_ip": private_ip,
        "public_ip": public_ip,
        "os_info": os_info,
        "kernel_version": kernel,
        "node_exporter_port": node_exporter_port,
    }

    url = f"http://{master_ip}:{master_port}/api/v1/register"
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()

    data = r.json()
    return data["agent_id"]


def leave(master_ip: str, master_port: int, agent_id: str):
    url = f"http://{master_ip}:{master_port}/api/v1/nodes/{agent_id}"
    try:
        requests.delete(url, timeout=10)
    except Exception:
        pass
