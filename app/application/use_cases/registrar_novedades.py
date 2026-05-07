from app.domain.entities.monthly_event import MonthlyEvent
from app.domain.repositories.event_repository import EventRepository


class RegistrarNovedades:
    def __init__(self, events: EventRepository):
        self.events = events

    def execute(self, payload: dict) -> dict:
        return self.events.save(MonthlyEvent.model_validate(payload)).model_dump()
