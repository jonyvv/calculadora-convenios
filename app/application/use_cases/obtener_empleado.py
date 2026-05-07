from app.domain.repositories.employee_repository import EmployeeRepository


class ObtenerEmpleado:
    def __init__(self, employees: EmployeeRepository):
        self.employees = employees

    def execute(self, employee_id: str) -> dict:
        return self.employees.get(employee_id).model_dump()
