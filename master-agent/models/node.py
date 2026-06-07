from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RegisterRequest(BaseModel):
    token: str
    hostname: str
    private_ip: str
    public_ip: Optional[str] = None
    os_info: Optional[str] = None
    kernel_version: Optional[str] = None
    node_exporter_port: int = 9100


class RegisterResponse(BaseModel):
    agent_id: str
    status: str
    message: str


class HeartbeatRequest(BaseModel):
    agent_id: str


class HeartbeatResponse(BaseModel):
    status: str
    timestamp: str


class NodeInfo(BaseModel):
    id: int
    agent_id: str
    hostname: Optional[str]
    private_ip: Optional[str]
    public_ip: Optional[str]
    os_info: Optional[str]
    kernel_version: Optional[str]
    node_exporter_port: int
    status: str
    registered_at: datetime
    last_seen: datetime
