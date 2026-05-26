from app.domain.repositories.agreement_repository import AgreementRepository
from app.domain.rules.agreement_rule_compiler import AgreementRuleCompiler


class ObtenerConvenio:
    def __init__(self, agreements: AgreementRepository):
        self.agreements = agreements
        self.rule_compiler = AgreementRuleCompiler()

    def execute(self, agreement_id: str, version: str | None = None) -> dict:
        agreement = self.agreements.get(agreement_id, version)
        return self.rule_compiler.normalize_agreement(agreement).model_dump()
