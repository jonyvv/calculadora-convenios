from app.application.services.convention_structuring_service import ConventionStructuringService
from app.domain.entities.agreement import Agreement


class DocumentImportService:
    def __init__(self, convention_structuring_service: ConventionStructuringService):
        self.convention_structuring_service = convention_structuring_service

    def import_document(self, filename: str, content: bytes) -> tuple[Agreement, list[str]]:
        agreement, _raw, warnings, _test_path, _extractions = self.convention_structuring_service.upload_convention([(filename, content)])
        return agreement, warnings

    def import_documents(self, documents: list[tuple[str, bytes]]) -> tuple[Agreement, list[str]]:
        agreement, _raw, warnings, _test_path, _extractions = self.convention_structuring_service.upload_convention(documents)
        return agreement, warnings

    def upload_convention(self, documents: list[tuple[str, bytes]]) -> dict:
        agreement, raw, warnings, test_path, extractions = self.convention_structuring_service.upload_convention(documents)
        return {"agreement": agreement, "raw": raw, "warnings": warnings, "test_path": test_path, "extractions": extractions}
