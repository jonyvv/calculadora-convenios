from app.domain.entities.employee import Employee
from app.domain.repositories.employee_repository import EmployeeRepository
from app.infrastructure.storage.json_storage import JsonStorage
from app.shared.exceptions import NotFoundError


class JsonEmployeeRepository(EmployeeRepository):
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def save(self, employee: Employee) -> Employee:
        self.storage.write(f"employees/{employee.employee_id}.json", employee.model_dump())
        return employee

    def get(self, employee_id: str) -> Employee:
        path = f"employees/{employee_id}.json"
        if not self.storage.exists(path):
            raise NotFoundError("Employee not found")
        return Employee.model_validate(self.storage.read(path))

    def list(self) -> list[Employee]:
        employees = []
        for path in self.storage.glob("employees/*.json"):
            employees.append(Employee.model_validate(self.storage.read(str(path.relative_to(self.storage.root)))))
        return employees
