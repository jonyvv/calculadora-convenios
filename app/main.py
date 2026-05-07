from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.agreement_routes import router as agreement_router
from app.api.routes.employee_routes import router as employee_router
from app.api.routes.event_routes import router as event_router
from app.api.routes.payroll_routes import router as payroll_router
from app.shared.container import Container


def create_app() -> FastAPI:
    container = Container()
    api = FastAPI(title="Liquidacion de Sueldos Argentina", version="0.1.0")
    api.state.container = container
    api.include_router(agreement_router)
    api.include_router(employee_router)
    api.include_router(event_router)
    api.include_router(payroll_router)
    api.mount("/static", StaticFiles(directory="app/frontend"), name="static")

    @api.get("/", include_in_schema=False)
    def frontend():
        return FileResponse("app/frontend/index.html")

    return api


app = create_app()
