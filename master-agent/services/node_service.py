import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from database.connection import get_db


def generate_agent_id(hostname: str) -> str:
    short_uuid = str(uuid.uuid4())[:8]
    safe_host = hostname.lower().replace(".", "-").replace("_", "-")[:20]
    return f"agent-{safe_host}-{short_uuid}"


def register_node(
    hostname: str,
    private_ip: str,
    public_ip: Optional[str],
    os_info: Optional[str],
    kernel_version: Optional[str],
    node_exporter_port: int = 9100,
) -> str:
    agent_id = generate_agent_id(hostname)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nodes (agent_id, hostname, private_ip, public_ip,
                                   os_info, kernel_version, node_exporter_port, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'online')
                ON CONFLICT (agent_id) DO UPDATE
                  SET hostname = EXCLUDED.hostname,
                      private_ip = EXCLUDED.private_ip,
                      public_ip = EXCLUDED.public_ip,
                      os_info = EXCLUDED.os_info,
                      kernel_version = EXCLUDED.kernel_version,
                      node_exporter_port = EXCLUDED.node_exporter_port,
                      status = 'online',
                      last_seen = NOW()
                """,
                (agent_id, hostname, private_ip, public_ip, os_info,
                 kernel_version, node_exporter_port),
            )
    return agent_id


def update_heartbeat(agent_id: str) -> bool:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nodes SET last_seen = NOW(), status = 'online'
                WHERE agent_id = %s
                """,
                (agent_id,),
            )
            return cur.rowcount > 0


def get_node(agent_id: str) -> Optional[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, agent_id, hostname, private_ip, public_ip,
                       os_info, kernel_version, node_exporter_port,
                       status, registered_at, last_seen
                FROM nodes WHERE agent_id = %s
                """,
                (agent_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return _row_to_node(row)


def get_all_nodes() -> List[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, agent_id, hostname, private_ip, public_ip,
                       os_info, kernel_version, node_exporter_port,
                       status, registered_at, last_seen
                FROM nodes
                ORDER BY registered_at DESC
                """
            )
            return [_row_to_node(row) for row in cur.fetchall()]


def mark_stale_nodes_offline(timeout_seconds: int = 120):
    cutoff = datetime.utcnow() - timedelta(seconds=timeout_seconds)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nodes SET status = 'offline'
                WHERE status = 'online' AND last_seen < %s
                """,
                (cutoff,),
            )
            return cur.rowcount


def deregister_node(agent_id: str) -> bool:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE nodes SET status = 'offline' WHERE agent_id = %s",
                (agent_id,),
            )
            return cur.rowcount > 0


def _row_to_node(row: tuple) -> dict:
    return {
        "id": row[0],
        "agent_id": row[1],
        "hostname": row[2],
        "private_ip": row[3],
        "public_ip": row[4],
        "os_info": row[5],
        "kernel_version": row[6],
        "node_exporter_port": row[7],
        "status": row[8],
        "registered_at": row[9],
        "last_seen": row[10],
    }
