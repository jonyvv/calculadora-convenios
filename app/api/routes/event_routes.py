from fastapi import APIRouter, Depends

from app.api.controllers.dependencies import get_container
from app.api.controllers.event_controller import EventController
from app.application.dtos.event_dto import RegisterEventsRequest
from app.shared.container import Container

router = APIRouter(prefix="/events", tags=["events"])


@router.post("")
def register_events(payload: RegisterEventsRequest, container: Container = Depends(get_container)):
    return EventController(container).register(payload)
