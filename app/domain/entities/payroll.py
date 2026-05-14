from pydantic import BaseModel, Field


class PayrollDetail(BaseModel):
    code: str
    name: str
    type: str
    amount: float
    taxable: bool = True


class Payroll(BaseModel):
    employee_id: str
    period: str
    gross_salary: float
    deductions: float
    net_salary: float
    details: list[PayrollDetail] = Field(default_factory=list)
    estado: str = "ok"
    modelo_liquidacion: str = "sueldo_base"
    alertas: list[str] = Field(default_factory=list)
    datos_faltantes: list[str] = Field(default_factory=list)
    mensaje: str = ""
