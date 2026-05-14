from app.application.services.document_import_service import DocumentImportService
from app.domain.repositories.agreement_repository import AgreementRepository


class ImportarConvenio:
    def __init__(self, importer: DocumentImportService, agreements: AgreementRepository):
        self.importer = importer
        self.agreements = agreements

    def execute(self, filename: str, content: bytes) -> dict:
        agreement, warnings = self.importer.import_document(filename, content)
        self.agreements.activate(agreement.metadata.agreement_id, agreement.metadata.version)
        return {"agreement": agreement.model_dump(), "warnings": warnings}

    def execute_many(self, documents: list[tuple[str, bytes]]) -> dict:
        result = self.importer.upload_convention(documents)
        agreement = result["agreement"]
        warnings = result["warnings"]
        self.agreements.activate(agreement.metadata.agreement_id, agreement.metadata.version)
        return {
            "agreement": agreement.model_dump(),
            "codex_input": result["raw"],
            "extractions": [
                {"filename": item["filename"], "source": item["source"], "text_length": len(item["text"])}
                for item in result.get("extractions", [])
            ],
            "warnings": warnings,
            "generated_test": result["test_path"],
            "stages": [
                {"name": "Archivo recibido", "status": "DONE"},
                {"name": "Extrayendo con Gemini", "status": "DONE"},
                {"name": "Codex estructurando", "status": "DONE"},
                {"name": "Validacion de schema", "status": "DONE" if agreement.metadata.status == "ACTIVE" else "WARNING"},
                {"name": "Convenio listo", "status": agreement.metadata.status},
            ],
        }
