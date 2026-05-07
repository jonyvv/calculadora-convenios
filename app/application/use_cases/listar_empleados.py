from app.domain.repositories.employee_repository import EmployeeRepository


class ListarEmpleados:
    def __init__(self, employees: EmployeeRepository):
        self.employees = employees

    def execute(self) -> list[dict]:
        return [employee.model_dump() for employee in self.employees.list()]
