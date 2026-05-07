from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.api.controllers.agreement_controller import AgreementController
from app.api.controllers.dependencies import get_container
from app.application.dtos.agreement_dto import ActivateAgreementRequest
from app.shared.container import Container
from app.shared.exceptions import NotFoundError

router = APIRouter(prefix="/agreements", tags=["agreements"])


@router.post("/upload")
async def upload_agreement(file: UploadFile = File(...), container: Container = Depends(get_container)):
    try:
        return await AgreementController(container).upload(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/upload-files")
async def upload_agreement_files(files: list[UploadFile] = File(...), container: Container = Depends(get_container)):
    try:
        if not files:
            raise ValueError("At least one agreement file is required")
        return await AgreementController(container).upload_files(files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("")
def list_agreements(container: Container = Depends(get_container)):
    return AgreementController(container).list()


@router.get("/{agreement_id}")
def get_agreement(agreement_id: str, version: str | None = Query(default=None), container: Container = Depends(get_container)):
    try:
        return AgreementController(container).get(agreement_id, version)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{agreement_id}")
def update_agreement(agreement_id: str, payload: dict, container: Container = Depends(get_container)):
    try:
        return AgreementController(container).update(agreement_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{agreement_id}")
def delete_agreement(agreement_id: str, version: str | None = Query(default=None), container: Container = Depends(get_container)):
    try:
        return AgreementController(container).delete(agreement_id, version)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{agreement_id}/activate")
def activate_agreement(agreement_id: str, payload: ActivateAgreementRequest, container: Container = Depends(get_container)):
    try:
        return AgreementController(container).activate(agreement_id, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
