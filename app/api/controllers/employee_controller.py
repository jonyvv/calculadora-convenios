from app.application.dtos.employee_dto import CreateEmployeeRequest
from app.shared.container import Container


class EmployeeController:
    def __init__(self, container: Container):
        self.container = container

    def create(self, payload: CreateEmployeeRequest) -> dict:
        return self.container.crear_empleado().execute(payload.model_dump())

    def list(self) -> list[dict]:
        return self.container.listar_empleados().execute()

    def get(self, employee_id: str) -> dict:
        return self.container.obtener_empleado().execute(employee_id)

    def update(self, employee_id: str, payload: CreateEmployeeRequest) -> dict:
        data = payload.model_dump()
        data["employee_id"] = employee_id
        return self.container.crear_empleado().execute(data)
