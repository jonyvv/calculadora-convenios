from app.domain.entities.monthly_event import MonthlyEvent
from app.domain.repositories.event_repository import EventRepository
from app.infrastructure.storage.json_storage import JsonStorage
from app.shared.exceptions import NotFoundError


class JsonEventRepository(EventRepository):
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def save(self, monthly_event: MonthlyEvent) -> MonthlyEvent:
        self.storage.write(f"events/{monthly_event.employee_id}/{monthly_event.period}.json", monthly_event.model_dump())
        return monthly_event

    def get(self, employee_id: str, period: str) -> MonthlyEvent:
        path = f"events/{employee_id}/{period}.json"
        if not self.storage.exists(path):
            raise NotFoundError("Monthly events not found")
        return MonthlyEvent.model_validate(self.storage.read(path))
