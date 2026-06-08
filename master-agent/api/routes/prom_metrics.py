from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from services.node_service import get_all_nodes

router = APIRouter()


def _labels(n: dict) -> str:
    agent_id  = (n["agent_id"]  or "").replace('"', '')
    hostname  = (n["hostname"]  or "").replace('"', '')
    private_ip = (n["private_ip"] or "").replace('"', '')
    return f'agent_id="{agent_id}",hostname="{hostname}",private_ip="{private_ip}"'


@router.get("/prom-metrics", response_class=PlainTextResponse, include_in_schema=False)
def prom_metrics():
    nodes = get_all_nodes()
    lines = []

    lines += [
        "# HELP polaris_node_up Heartbeat status: 1=online 0=offline",
        "# TYPE polaris_node_up gauge",
    ]
    for n in nodes:
        lines.append(f'polaris_node_up{{{_labels(n)}}} {1 if n["status"] == "online" else 0}')

    lines += [
        "# HELP polaris_node_ssh SSH port-22 reachability: 1=ok 0=failed",
        "# TYPE polaris_node_ssh gauge",
    ]
    for n in nodes:
        ssh = n.get("ssh_status", "unknown")
        val = 1 if ssh == "ok" else (0 if ssh == "failed" else -1)
        lines.append(f'polaris_node_ssh{{{_labels(n)}}} {val}')

    lines += [
        "# HELP polaris_node_last_seen_seconds Unix timestamp of last heartbeat",
        "# TYPE polaris_node_last_seen_seconds gauge",
    ]
    for n in nodes:
        ts = n["last_seen"]
        if ts:
            lines.append(f'polaris_node_last_seen_seconds{{{_labels(n)}}} {ts.timestamp():.0f}')

    lines += [
        "# HELP polaris_node_last_ssh_check_seconds Unix timestamp of last SSH check",
        "# TYPE polaris_node_last_ssh_check_seconds gauge",
    ]
    for n in nodes:
        ts = n.get("last_ssh_check")
        if ts:
            lines.append(f'polaris_node_last_ssh_check_seconds{{{_labels(n)}}} {ts.timestamp():.0f}')

    return "\n".join(lines) + "\n"
