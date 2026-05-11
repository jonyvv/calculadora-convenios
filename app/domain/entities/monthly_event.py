from pydantic import BaseModel, Field


class Event(BaseModel):
    type: str
    subtype: str | None = None
    days: float | None = None
    hours: float | None = None
    quantity: float | None = None
    amount: float | None = None
    description: str | None = None


class MonthlyEvent(BaseModel):
    employee_id: str
    period: str
    events: list[Event] = Field(default_factory=list)
