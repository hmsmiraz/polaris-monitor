from pydantic import BaseModel
from typing import Optional


class MetricsRequest(BaseModel):
    agent_id: str
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    load_avg_1: float
    load_avg_5: float
    load_avg_15: float
    uptime_seconds: int
    hostname: str
    private_ip: str
    public_ip: Optional[str] = None
    os_info: Optional[str] = None
    kernel_version: Optional[str] = None
