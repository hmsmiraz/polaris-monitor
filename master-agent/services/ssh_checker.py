import socket
import threading
import time

# Track previous SSH status per agent_id to only alert on changes
_prev_status: dict = {}


def _check_port(ip: str, port: int = 22, timeout: float = 5.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def _run():
    from services.node_service import get_all_nodes, update_ssh_check
    from services.alert_service import create_alert
    from services.email_notifier import send_alert_email

    while True:
        try:
            for node in get_all_nodes():
                ip = node.get("private_ip")
                agent_id = node["agent_id"]
                hostname = node.get("hostname", agent_id)
                if not ip:
                    continue

                status = "ok" if _check_port(ip) else "failed"
                update_ssh_check(agent_id, status)

                prev = _prev_status.get(agent_id)
                if prev == status:
                    continue  # No change — skip alert

                _prev_status[agent_id] = status

                if status == "failed":
                    msg = f"SSH port 22 unreachable on {hostname} ({ip})"
                    create_alert(agent_id=agent_id, alert_type="ssh_failure",
                                 message=msg, severity="critical")
                    send_alert_email(alert_type="ssh_failure", message=msg,
                                     hostname=hostname, private_ip=ip,
                                     severity="critical")
                    print(f"[ssh-checker] FAILED: {hostname} ({ip})")
                elif prev == "failed":
                    msg = f"SSH port 22 is reachable again on {hostname} ({ip})"
                    create_alert(agent_id=agent_id, alert_type="ssh_recovered",
                                 message=msg, severity="warning")
                    send_alert_email(alert_type="ssh_recovered", message=msg,
                                     hostname=hostname, private_ip=ip,
                                     severity="warning")
                    print(f"[ssh-checker] RECOVERED: {hostname} ({ip})")

        except Exception as e:
            print(f"[ssh-checker] {e}")
        time.sleep(60)


def start():
    t = threading.Thread(target=_run, daemon=True, name="ssh-checker")
    t.start()
