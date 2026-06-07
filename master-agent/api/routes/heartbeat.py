from datetime import datetime
from fastapi import APIRouter, HTTPException
from models.node import HeartbeatRequest, HeartbeatResponse
from services import node_service

router = APIRouter()


@router.post("/heartbeat", response_model=HeartbeatResponse)
def heartbeat(req: HeartbeatRequest):
    updated = node_service.update_heartbeat(req.agent_id)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {req.agent_id}")

    return HeartbeatResponse(
        status="ok",
        timestamp=datetime.utcnow().isoformat(),
    )
