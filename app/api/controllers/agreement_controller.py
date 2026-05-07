from fastapi import UploadFile

from app.application.dtos.agreement_dto import ActivateAgreementRequest
from app.shared.container import Container


class AgreementController:
    def __init__(self, container: Container):
        self.container = container

    async def upload(self, file: UploadFile) -> dict:
        content = await file.read()
        return self.container.importar_convenio().execute(file.filename or "document.txt", content)

    async def upload_files(self, files: list[UploadFile]) -> dict:
        documents = []
        for file in files:
            documents.append((file.filename or "document.txt", await file.read()))
        return self.container.importar_convenio().execute_many(documents)

    def list(self) -> list[dict]:
        return self.container.listar_convenios().execute()

    def get(self, agreement_id: str, version: str | None = None) -> dict:
        return self.container.obtener_convenio().execute(agreement_id, version)

    def activate(self, agreement_id: str, payload: ActivateAgreementRequest) -> dict:
        return self.container.activar_version_convenio().execute(agreement_id, payload.version)

    def update(self, agreement_id: str, payload: dict) -> dict:
        return self.container.actualizar_convenio().execute(agreement_id, payload)

    def delete(self, agreement_id: str, version: str | None = None) -> dict:
        return self.container.eliminar_convenio().execute(agreement_id, version)
