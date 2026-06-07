from fastapi import APIRouter, HTTPException
from models.metrics import MetricsRequest
from services import node_service
from database.connection import get_db

router = APIRouter()


@router.post("/metrics")
def receive_metrics(req: MetricsRequest):
    node = node_service.get_node(req.agent_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {req.agent_id}")

    # Store lightweight summary in DB (full time-series lives in Prometheus)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO metrics_summary
                    (agent_id, cpu_percent, memory_percent, disk_percent, load_avg_1, uptime_seconds)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    req.agent_id,
                    req.cpu_percent,
                    req.memory_percent,
                    req.disk_percent,
                    req.load_avg_1,
                    req.uptime_seconds,
                ),
            )

    # Update node heartbeat while we're at it
    node_service.update_heartbeat(req.agent_id)

    return {"status": "ok"}
