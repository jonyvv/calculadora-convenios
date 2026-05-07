from abc import ABC, abstractmethod

from app.domain.entities.monthly_event import MonthlyEvent


class EventRepository(ABC):
    @abstractmethod
    def save(self, monthly_event: MonthlyEvent) -> MonthlyEvent:
        raise NotImplementedError

    @abstractmethod
    def get(self, employee_id: str, period: str) -> MonthlyEvent:
        raise NotImplementedError
