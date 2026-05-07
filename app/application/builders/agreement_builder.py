from app.application.builders.category_builder import CategoryBuilder
from app.application.builders.compliance_builder import ComplianceBuilder
from app.application.builders.event_rules_builder import EventRulesBuilder
from app.application.builders.metadata_builder import MetadataBuilder
from app.application.builders.salary_model_builder import SalaryModelBuilder
from app.application.validators.agreement_validators import AgreementValidationService
from app.domain.entities.agreement import Agreement


class AgreementBuilder:
    def __init__(
        self,
        metadata_builder: MetadataBuilder | None = None,
        category_builder: CategoryBuilder | None = None,
        salary_model_builder: SalaryModelBuilder | None = None,
        event_rules_builder: EventRulesBuilder | None = None,
        compliance_builder: ComplianceBuilder | None = None,
        validators: AgreementValidationService | None = None,
    ):
        self.metadata_builder = metadata_builder or MetadataBuilder()
        self.category_builder = category_builder or CategoryBuilder()
        self.salary_model_builder = salary_model_builder or SalaryModelBuilder()
        self.event_rules_builder = event_rules_builder or EventRulesBuilder()
        self.compliance_builder = compliance_builder or ComplianceBuilder()
        self.validators = validators or AgreementValidationService()

    def build(self, raw: dict, source_document: str) -> tuple[Agreement, list[str]]:
        validation_warnings = self.validators.validate_raw(raw)
        status = "DRAFT" if validation_warnings else "ACTIVE"
        agreement = Agreement(
            metadata=self.metadata_builder.build(raw, source_document, status),
            categories=self.category_builder.build(raw),
            salary_model=self.salary_model_builder.build(raw),
            event_rules=self.event_rules_builder.build(raw),
            audit_rules=self.compliance_builder.build_audit_rules(raw),
        )
        validation_warnings.extend(self.validators.validate_agreement(agreement))
        if validation_warnings:
            agreement.metadata.status = "DRAFT"
        return agreement, [*raw.get("ambiguities", []), *validation_warnings]
