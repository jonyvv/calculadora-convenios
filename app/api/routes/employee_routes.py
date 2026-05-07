from fastapi import APIRouter, Depends, HTTPException

from app.api.controllers.dependencies import get_container
from app.api.controllers.employee_controller import EmployeeController
from app.application.dtos.employee_dto import CreateEmployeeRequest
from app.shared.container import Container
from app.shared.exceptions import NotFoundError

router = APIRouter(prefix="/employees", tags=["employees"])


@router.post("")
def create_employee(payload: CreateEmployeeRequest, container: Container = Depends(get_container)):
    return EmployeeController(container).create(payload)


@router.get("")
def list_employees(container: Container = Depends(get_container)):
    return EmployeeController(container).list()


@router.get("/{employee_id}")
def get_employee(employee_id: str, container: Container = Depends(get_container)):
    try:
        return EmployeeController(container).get(employee_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{employee_id}")
def update_employee(employee_id: str, payload: CreateEmployeeRequest, container: Container = Depends(get_container)):
    return EmployeeController(container).update(employee_id, payload)
