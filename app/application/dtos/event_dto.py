from app.domain.entities.monthly_event import Event
from pydantic import BaseModel


class RegisterEventsRequest(BaseModel):
    employee_id: str
    period: str
    events: list[Event]
