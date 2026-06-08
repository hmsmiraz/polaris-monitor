from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from services.node_service import get_all_nodes

router = APIRouter()


def _safe(v) -> str:
    return (v or "").replace('"', '').replace('\\', '')


def _fmt_ts(dt) -> str:
    if not dt:
        return "never"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


@router.get("/prom-metrics", response_class=PlainTextResponse, include_in_schema=False)
def prom_metrics():
    nodes = get_all_nodes()
    lines = []

    lines += [
        "# HELP polaris_node_up Heartbeat status: 1=online 0=offline",
        "# TYPE polaris_node_up gauge",
    ]
    for n in nodes:
        lbl = (f'agent_id="{_safe(n["agent_id"])}",'
               f'hostname="{_safe(n["hostname"])}",'
               f'private_ip="{_safe(n["private_ip"])}"')
        lines.append(f'polaris_node_up{{{lbl}}} {1 if n["status"] == "online" else 0}')

    lines += [
        "# HELP polaris_node_ssh SSH port-22 reachability: 1=ok 0=failed -1=unknown",
        "# TYPE polaris_node_ssh gauge",
    ]
    for n in nodes:
        ssh = n.get("ssh_status", "unknown")
        val = 1 if ssh == "ok" else (0 if ssh == "failed" else -1)
        lbl = (f'agent_id="{_safe(n["agent_id"])}",'
               f'hostname="{_safe(n["hostname"])}",'
               f'private_ip="{_safe(n["private_ip"])}",'
               f'last_ssh_check="{_fmt_ts(n.get("last_ssh_check"))}",'
               f'last_seen="{_fmt_ts(n.get("last_seen"))}"')
        lines.append(f'polaris_node_ssh{{{lbl}}} {val}')

    return "\n".join(lines) + "\n"
