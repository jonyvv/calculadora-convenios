from app.application.dtos.payroll_dto import AuditPayrollRequest, CalculatePayrollRequest
from app.shared.container import Container


class PayrollController:
    def __init__(self, container: Container):
        self.container = container

    def calculate(self, payload: CalculatePayrollRequest) -> dict:
        return self.container.calcular_liquidacion().execute(payload.employee_id, payload.period)

    def audit(self, payload: AuditPayrollRequest) -> dict:
        return self.container.auditar_liquidacion().execute(payload.employee_id, payload.period)
