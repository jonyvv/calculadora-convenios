from datetime import date

from app.domain.entities.employee import Employee
from app.domain.repositories.employee_repository import EmployeeRepository


class CrearEmpleado:
    def __init__(self, employees: EmployeeRepository):
        self.employees = employees

    def execute(self, payload: dict) -> dict:
        if payload.get("hire_date"):
            payload["seniority_years"] = self._seniority_years(payload["hire_date"])
        return self.employees.save(Employee.model_validate(payload)).model_dump()

    def _seniority_years(self, hire_date: str) -> int:
        try:
            start = date.fromisoformat(hire_date)
        except ValueError:
            return 0
        today = date.today()
        years = today.year - start.year
        if (today.month, today.day) < (start.month, start.day):
            years -= 1
        return max(years, 0)
