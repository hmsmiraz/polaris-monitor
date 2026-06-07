from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AlertRequest(BaseModel):
    agent_id: str
    alert_type: str
    message: str
    severity: str = "warning"


class AlertInfo(BaseModel):
    id: int
    agent_id: str
    alert_type: str
    message: str
    severity: str
    resolved: bool
    created_at: datetime
