from app.domain.entities.agreement import Agreement
from app.domain.repositories.agreement_repository import AgreementRepository


class ActualizarConvenio:
    def __init__(self, agreements: AgreementRepository):
        self.agreements = agreements

    def execute(self, agreement_id: str, payload: dict) -> dict:
        agreement = Agreement.model_validate(payload)
        if agreement.metadata.agreement_id != agreement_id:
            raise ValueError("El agreement_id del path no coincide con el payload")
        saved = self.agreements.save_version(agreement)
        return saved.model_dump()
