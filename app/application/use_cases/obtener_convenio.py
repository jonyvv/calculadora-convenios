from app.domain.repositories.agreement_repository import AgreementRepository


class ObtenerConvenio:
    def __init__(self, agreements: AgreementRepository):
        self.agreements = agreements

    def execute(self, agreement_id: str, version: str | None = None) -> dict:
        return self.agreements.get(agreement_id, version).model_dump()
