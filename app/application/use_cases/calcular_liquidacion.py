from app.domain.repositories.agreement_repository import AgreementRepository
from app.domain.repositories.employee_repository import EmployeeRepository
from app.domain.repositories.event_repository import EventRepository
from app.domain.rules.payroll_engine import PayrollEngine


class CalcularLiquidacion:
    def __init__(self, agreements: AgreementRepository, employees: EmployeeRepository, events: EventRepository, engine: PayrollEngine):
        self.agreements = agreements
        self.employees = employees
        self.events = events
        self.engine = engine

    def execute(self, employee_id: str, period: str) -> dict:
        employee = self.employees.get(employee_id)
        agreement = self.agreements.get_active(employee.agreement_id)
        if not any(category.category_id == employee.category_id for category in agreement.categories):
            raise ValueError("La categoria del empleado no pertenece al convenio activo")
        monthly_events = self.events.get(employee_id, period)
        return self.engine.calculate(agreement, employee, monthly_events).model_dump()
