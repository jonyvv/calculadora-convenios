from pydantic import BaseModel


class Employee(BaseModel):
    employee_id: str
    agreement_id: str
    category_id: str
    seniority_years: int = 0
    cuil: str | None = None
    hire_date: str | None = None
    zone: str | None = None
    workday: str | None = None
    active: bool = True
