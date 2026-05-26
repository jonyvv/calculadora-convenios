from app.domain.repositories.agreement_repository import AgreementRepository
from app.domain.rules.agreement_rule_compiler import AgreementRuleCompiler


class ListarConvenios:
    def __init__(self, agreements: AgreementRepository):
        self.agreements = agreements
        self.rule_compiler = AgreementRuleCompiler()

    def execute(self) -> list[dict]:
        return [
            self.rule_compiler.normalize_agreement(agreement).model_dump()
            for agreement in self.agreements.list()
        ]
