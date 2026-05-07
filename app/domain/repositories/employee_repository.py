from abc import ABC, abstractmethod

from app.domain.entities.employee import Employee


class EmployeeRepository(ABC):
    @abstractmethod
    def save(self, employee: Employee) -> Employee:
        raise NotImplementedError

    @abstractmethod
    def get(self, employee_id: str) -> Employee:
        raise NotImplementedError

    @abstractmethod
    def list(self) -> list[Employee]:
        raise NotImplementedError
