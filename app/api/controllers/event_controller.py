from app.application.dtos.event_dto import RegisterEventsRequest
from app.shared.container import Container


class EventController:
    def __init__(self, container: Container):
        self.container = container

    def register(self, payload: RegisterEventsRequest) -> dict:
        return self.container.registrar_novedades().execute(payload.model_dump())
