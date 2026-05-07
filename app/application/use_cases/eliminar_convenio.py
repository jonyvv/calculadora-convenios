from app.domain.repositories.agreement_repository import AgreementRepository


class EliminarConvenio:
    def __init__(self, agreements: AgreementRepository):
        self.agreements = agreements

    def execute(self, agreement_id: str, version: str | None = None) -> dict:
        self.agreements.delete(agreement_id, version)
        return {"deleted": True, "agreement_id": agreement_id, "version": version}
