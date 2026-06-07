from fastapi import APIRouter, HTTPException
from models.node import RegisterRequest, RegisterResponse
from services import token_service, node_service
from prometheus.config_manager import add_target
from services.alert_service import create_event

router = APIRouter()


@router.post("/register", response_model=RegisterResponse)
def register_worker(req: RegisterRequest):
    if not token_service.validate_token(req.token):
        raise HTTPException(status_code=401, detail="Invalid or expired join token")

    agent_id = node_service.register_node(
        hostname=req.hostname,
        private_ip=req.private_ip,
        public_ip=req.public_ip,
        os_info=req.os_info,
        kernel_version=req.kernel_version,
        node_exporter_port=req.node_exporter_port,
    )

    # Dynamically add to Prometheus targets
    try:
        add_target(
            agent_id=agent_id,
            hostname=req.hostname,
            private_ip=req.private_ip,
            port=req.node_exporter_port,
        )
    except Exception as e:
        print(f"[WARN] Could not update Prometheus targets: {e}")

    create_event(agent_id, "registration", f"Node {req.hostname} registered from {req.private_ip}")

    return RegisterResponse(
        agent_id=agent_id,
        status="connected",
        message=f"Successfully joined master. Agent ID: {agent_id}",
    )
