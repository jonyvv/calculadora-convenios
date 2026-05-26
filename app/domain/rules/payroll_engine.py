from app.domain.entities.agreement import Agreement
from app.domain.entities.employee import Employee
from app.domain.entities.monthly_event import MonthlyEvent
from app.domain.entities.payroll import Payroll
from app.domain.rules.agreement_rule_compiler import AgreementRuleCompiler


class PayrollEngine:
    def __init__(self, rule_compiler: AgreementRuleCompiler | None = None):
        self.rule_compiler = rule_compiler or AgreementRuleCompiler()

    def calculate(self, agreement: Agreement, employee: Employee, monthly_event: MonthlyEvent) -> Payroll:
        normalized_agreement = self.rule_compiler.normalize_agreement(agreement)
        compiled_rules = self.rule_compiler.compile_rules(normalized_agreement)
        return compiled_rules.execute(normalized_agreement, employee, monthly_event)
