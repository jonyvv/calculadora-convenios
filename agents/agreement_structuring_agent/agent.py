from datetime import datetime, timezone
from typing import Any

from agents.agreement_structuring_agent.builders import (
    CategoryBuilder,
    ComplianceBuilder,
    EventRuleBuilder,
    FormulaBuilder,
    MetadataBuilder,
    SalaryModelBuilder,
)
from agents.agreement_structuring_agent.logger import AgreementStructuringLogger
from agents.agreement_structuring_agent.validators import AgreementTextInputValidator, AgreementValidator
from app.application.services.convention_test_generator import ConventionTestGenerator
from app.domain.entities.agreement import Agreement
from app.domain.repositories.agreement_repository import AgreementRepository


class AgreementStructuringAgent:
    """Internal Codex agent that structures plain text already extracted by Gemini.

    It never reads PDFs, DOCX, Excel files, or binary source documents.
    """

    name = "agreement_structuring_agent"

    def __init__(
        self,
        repository: AgreementRepository,
        metadata_builder: MetadataBuilder | None = None,
        category_builder: CategoryBuilder | None = None,
        salary_model_builder: SalaryModelBuilder | None = None,
        event_rule_builder: EventRuleBuilder | None = None,
        compliance_builder: ComplianceBuilder | None = None,
        formula_builder: FormulaBuilder | None = None,
        input_validator: AgreementTextInputValidator | None = None,
        agreement_validator: AgreementValidator | None = None,
        test_generator: ConventionTestGenerator | None = None,
        logger: AgreementStructuringLogger | None = None,
    ):
        self.repository = repository
        self.metadata_builder = metadata_builder or MetadataBuilder()
        self.category_builder = category_builder or CategoryBuilder()
        self.salary_model_builder = salary_model_builder or SalaryModelBuilder()
        self.event_rule_builder = event_rule_builder or EventRuleBuilder()
        self.compliance_builder = compliance_builder or ComplianceBuilder()
        self.formula_builder = formula_builder or FormulaBuilder()
        self.input_validator = input_validator or AgreementTextInputValidator()
        self.agreement_validator = agreement_validator or AgreementValidator()
        self.test_generator = test_generator or ConventionTestGenerator("tests/conventions")
        self.logger = logger or AgreementStructuringLogger()

    def process(self, gemini_text_json: dict[str, Any]) -> dict[str, Any]:
        try:
            input_warnings = self.input_validator.validate_input(gemini_text_json)
            status = "DRAFT" if input_warnings else "ACTIVE"
            metadata = self.metadata_builder.build(gemini_text_json, status)
            categories = self.category_builder.build(gemini_text_json)
            salary_model = self.salary_model_builder.build(gemini_text_json)
            event_rules = self.event_rule_builder.build(gemini_text_json)
            audit_rules = self.compliance_builder.build(event_rules, salary_model)
            agreement = Agreement(
                metadata=metadata,
                categories=categories,
                salary_model=salary_model,
                event_rules=event_rules,
                audit_rules=audit_rules,
            )
            agreement = self.formula_builder.build(agreement)

            schema_warnings = self.agreement_validator.validate_schema(agreement)
            warnings = [*input_warnings, *schema_warnings]
            if warnings:
                agreement.metadata.status = "DRAFT"

            saved = self.repository.save_version(Agreement.model_validate(agreement.model_dump()))
            self.repository.activate(saved.metadata.agreement_id, saved.metadata.version)
            test_path = self.test_generator.generate(saved)
            result = self._result("DRAFT" if saved.metadata.status == "DRAFT" else "SUCCESS", saved, warnings)
            log_path = self.logger.write({
                **result,
                "agent": self.name,
                "generated_test": str(test_path),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            })
            return {**result, "log_path": str(log_path), "generated_test": str(test_path)}
        except Exception as exc:
            result = {
                "status": "ERROR",
                "agreement_id": "",
                "version": "",
                "warnings": [str(exc)],
            }
            log_path = self.logger.write({
                **result,
                "agent": self.name,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            })
            return {**result, "log_path": str(log_path)}

    def _result(self, status: str, agreement: Agreement, warnings: list[str]) -> dict[str, Any]:
        return {
            "status": status,
            "agreement_id": agreement.metadata.agreement_id,
            "version": agreement.metadata.version,
            "warnings": warnings,
        }
