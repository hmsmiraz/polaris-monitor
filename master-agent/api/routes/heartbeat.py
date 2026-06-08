from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from models.node import HeartbeatRequest, HeartbeatResponse
from services import node_service

router = APIRouter()


@router.post("/heartbeat", response_model=HeartbeatResponse)
def heartbeat(req: HeartbeatRequest):
    updated = node_service.update_heartbeat(req.agent_id)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {req.agent_id}")

    if req.boot_time is not None:
        boot_dt = datetime.fromtimestamp(req.boot_time, tz=timezone.utc).replace(tzinfo=None)
        node_service.update_boot_time(req.agent_id, boot_dt)

    return HeartbeatResponse(
        status="ok",
        timestamp=datetime.utcnow().isoformat(),
    )
