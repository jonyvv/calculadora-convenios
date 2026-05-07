from app.application.builders.category_builder import CategoryBuilder
from app.application.builders.compliance_builder import ComplianceBuilder
from app.application.builders.event_rules_builder import EventRulesBuilder as EventRuleBuilder
from app.application.builders.metadata_builder import MetadataBuilder
from app.application.builders.salary_model_builder import SalaryModelBuilder
from app.domain.entities.agreement import Agreement


class FormulaBuilder:
    def build(self, agreement: Agreement) -> Agreement:
        for item in agreement.salary_model.remunerative_items + agreement.salary_model.non_remunerative_items:
            if item.formula:
                continue
            if item.calculation_type == "PERCENTAGE":
                item.formula = f"{item.base_reference or 'BASIC'} * {item.rate}%"
            elif item.calculation_type == "FIXED":
                item.formula = str(item.amount or 0)
        return agreement


__all__ = [
    "MetadataBuilder",
    "CategoryBuilder",
    "SalaryModelBuilder",
    "EventRuleBuilder",
    "ComplianceBuilder",
    "FormulaBuilder",
]
