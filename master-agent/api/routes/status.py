import subprocess
from datetime import datetime
from fastapi import APIRouter
from services import node_service

router = APIRouter()

SERVICES = ["polaris-master", "postgresql", "prometheus", "grafana-server"]


def _check_service(name: str) -> str:
    result = subprocess.run(
        f"systemctl is-active {name}",
        shell=True, capture_output=True, text=True
    )
    return result.stdout.strip() or "unknown"


@router.get("/status")
def system_status():
    nodes = node_service.get_all_nodes()
    online  = [n for n in nodes if n["status"] == "online"]
    offline = [n for n in nodes if n["status"] == "offline"]

    services = {svc: _check_service(svc) for svc in SERVICES}

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "nodes": {
            "total":   len(nodes),
            "online":  len(online),
            "offline": len(offline),
        },
        "services": services,
        "api": "running",
    }
