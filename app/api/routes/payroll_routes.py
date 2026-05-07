from fastapi import APIRouter, Depends, HTTPException

from app.api.controllers.dependencies import get_container
from app.api.controllers.payroll_controller import PayrollController
from app.application.dtos.payroll_dto import AuditPayrollRequest, CalculatePayrollRequest
from app.shared.container import Container
from app.shared.exceptions import NotFoundError

router = APIRouter(prefix="/payroll", tags=["payroll"])


@router.post("/calculate")
def calculate_payroll(payload: CalculatePayrollRequest, container: Container = Depends(get_container)):
    try:
        return PayrollController(container).calculate(payload)
    except (NotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/audit")
def audit_payroll(payload: AuditPayrollRequest, container: Container = Depends(get_container)):
    try:
        return PayrollController(container).audit(payload)
    except (NotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
