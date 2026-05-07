from app.domain.entities.agreement import Agreement
from app.domain.entities.employee import Employee
from app.domain.entities.monthly_event import MonthlyEvent
from app.domain.entities.payroll import Payroll


class AuditContextBuilder:
    def build(self, agreement: Agreement, employee: Employee, events: MonthlyEvent, payroll: Payroll) -> dict:
        return {
            "agreement": agreement.model_dump(),
            "employee": employee.model_dump(),
            "events": events.model_dump()["events"],
            "payroll": payroll.model_dump(),
        }
