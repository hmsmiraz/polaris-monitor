from fastapi import APIRouter, HTTPException
from services import node_service

router = APIRouter()


@router.get("/nodes")
def list_nodes():
    nodes = node_service.get_all_nodes()
    return {
        "nodes": nodes,
        "total": len(nodes),
        "online": sum(1 for n in nodes if n["status"] == "online"),
        "offline": sum(1 for n in nodes if n["status"] == "offline"),
    }


@router.get("/nodes/{agent_id}")
def get_node(agent_id: str):
    node = node_service.get_node(agent_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {agent_id}")
    return node


@router.delete("/nodes/{agent_id}")
def remove_node(agent_id: str):
    from prometheus.config_manager import remove_target
    node = node_service.get_node(agent_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {agent_id}")

    node_service.deregister_node(agent_id)
    if node.get("private_ip"):
        try:
            remove_target(node["private_ip"], node.get("node_exporter_port", 9100))
        except Exception:
            pass

    return {"status": "removed", "agent_id": agent_id}
