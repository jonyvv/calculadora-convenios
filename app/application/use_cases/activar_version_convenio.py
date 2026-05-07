from app.domain.repositories.agreement_repository import AgreementRepository


class ActivarVersionConvenio:
    def __init__(self, agreements: AgreementRepository):
        self.agreements = agreements

    def execute(self, agreement_id: str, version: str) -> dict:
        return self.agreements.activate(agreement_id, version).model_dump()
