from pydantic import BaseModel
from datetime import datetime


class EventRequest(BaseModel):
    agent_id: str
    event_type: str
    message: str


class EventInfo(BaseModel):
    id: int
    agent_id: str
    event_type: str
    message: str
    created_at: datetime
