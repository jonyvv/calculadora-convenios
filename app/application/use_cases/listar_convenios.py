from app.domain.repositories.agreement_repository import AgreementRepository


class ListarConvenios:
    def __init__(self, agreements: AgreementRepository):
        self.agreements = agreements

    def execute(self) -> list[dict]:
        return [agreement.model_dump() for agreement in self.agreements.list()]
