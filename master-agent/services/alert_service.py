from typing import List, Optional
from database.connection import get_db


def create_alert(
    agent_id: str,
    alert_type: str,
    message: str,
    severity: str = "warning",
) -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alerts (agent_id, alert_type, message, severity)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (agent_id, alert_type, message, severity),
            )
            return cur.fetchone()[0]


def get_alerts(
    agent_id: Optional[str] = None,
    resolved: Optional[bool] = None,
    limit: int = 100,
) -> List[dict]:
    conditions = []
    params = []

    if agent_id:
        conditions.append("agent_id = %s")
        params.append(agent_id)
    if resolved is not None:
        conditions.append("resolved = %s")
        params.append(resolved)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, agent_id, alert_type, message, severity, resolved, created_at
                FROM alerts
                {where}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                params,
            )
            return [_row_to_alert(r) for r in cur.fetchall()]


def resolve_alert(alert_id: int) -> bool:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE alerts SET resolved = TRUE WHERE id = %s",
                (alert_id,),
            )
            return cur.rowcount > 0


def create_event(agent_id: str, event_type: str, message: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (agent_id, event_type, message)
                VALUES (%s, %s, %s)
                """,
                (agent_id, event_type, message),
            )


def _row_to_alert(row: tuple) -> dict:
    return {
        "id": row[0],
        "agent_id": row[1],
        "alert_type": row[2],
        "message": row[3],
        "severity": row[4],
        "resolved": row[5],
        "created_at": row[6],
    }
