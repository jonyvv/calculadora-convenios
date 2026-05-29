from app.application.services.salary_scale_update_service import SalaryScaleUpdateService
from app.domain.repositories.agreement_repository import AgreementRepository


class ActualizarEscalaSalarial:
    def __init__(self, agreements: AgreementRepository, service: SalaryScaleUpdateService | None = None):
        self.agreements = agreements
        self.service = service or SalaryScaleUpdateService()

    def execute(self, agreement_id: str, filename: str, content: bytes, version: str | None = None) -> dict:
        agreement = self.agreements.get(agreement_id, version)
        updated_agreement, summary = self.service.update(agreement, filename, content)
        saved = self.agreements.save_version(updated_agreement)
        return {
            "agreement": saved.model_dump(),
            "summary": summary,
        }
