from fastapi import APIRouter, HTTPException
from typing import Optional
from models.alert import AlertRequest, AlertInfo
from services import alert_service, node_service
from services.email_notifier import send_alert_email

router = APIRouter()


@router.post("/alerts")
def receive_alert(req: AlertRequest):
    node = node_service.get_node(req.agent_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {req.agent_id}")

    alert_id = alert_service.create_alert(
        agent_id=req.agent_id,
        alert_type=req.alert_type,
        message=req.message,
        severity=req.severity,
    )

    # Pre-mark reboot reason so next heartbeat knows why it rebooted
    if req.alert_type == "auto_reboot":
        from database.connection import get_db
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE nodes SET reboot_reason = 'agent_triggered' WHERE agent_id = %s",
                    (req.agent_id,),
                )

    # Send email notification (no-op if SMTP not configured)
    send_alert_email(
        alert_type=req.alert_type,
        message=req.message,
        hostname=node.get("hostname", req.agent_id),
        private_ip=node.get("private_ip", ""),
        severity=req.severity,
    )

    return {"status": "received", "alert_id": alert_id}


@router.get("/alerts")
def list_alerts(
    agent_id: Optional[str] = None,
    resolved: Optional[bool] = None,
    limit: int = 100,
):
    alerts = alert_service.get_alerts(agent_id=agent_id, resolved=resolved, limit=limit)
    return {"alerts": alerts, "total": len(alerts)}


@router.put("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int):
    resolved = alert_service.resolve_alert(alert_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "resolved"}
