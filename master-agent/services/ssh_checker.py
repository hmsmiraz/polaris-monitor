import socket
import threading
import time


def _check_port(ip: str, port: int = 22, timeout: float = 5.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def _run():
    from services.node_service import get_all_nodes, update_ssh_check
    while True:
        try:
            for node in get_all_nodes():
                ip = node.get("private_ip")
                if not ip:
                    continue
                status = "ok" if _check_port(ip) else "failed"
                update_ssh_check(node["agent_id"], status)
        except Exception as e:
            print(f"[ssh-checker] {e}")
        time.sleep(60)


def start():
    t = threading.Thread(target=_run, daemon=True, name="ssh-checker")
    t.start()
