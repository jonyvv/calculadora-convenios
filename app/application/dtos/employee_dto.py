from pydantic import BaseModel, Field


class CreateEmployeeRequest(BaseModel):
    employee_id: str
    agreement_id: str
    category_id: str
    seniority_years: int | None = None
    cuil: str | None = None
    hire_date: str | None = None
    zone: str | None = None
    workday: str | None = None
    union_affiliated: bool = False
    enabled_deductions: list[str] = Field(default_factory=list)
