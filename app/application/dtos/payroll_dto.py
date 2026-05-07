from pydantic import BaseModel


class CalculatePayrollRequest(BaseModel):
    employee_id: str
    period: str


class AuditPayrollRequest(BaseModel):
    employee_id: str
    period: str
