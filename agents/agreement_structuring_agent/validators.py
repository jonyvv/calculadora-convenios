from agents.codex_structuring_agent.validators import FormulaValidator
from app.application.validators.agreement_validators import CategoryValidator, SalaryValidator
from app.domain.entities.agreement import Agreement


class AgreementTextInputValidator:
    def validate_input(self, payload: dict) -> list[str]:
        warnings = []
        if not isinstance(payload, dict):
            return ["El input debe ser un objeto JSON con document_metadata y full_text"]
        if "full_text" not in payload or not str(payload.get("full_text") or "").strip():
            warnings.append("Falta full_text extraido por Gemini")
        if "document_metadata" not in payload:
            warnings.append("Falta document_metadata")
        return warnings


class AgreementValidator:
    def __init__(self):
        self.category_validator = CategoryValidator()
        self.salary_validator = SalaryValidator()
        self.formula_validator = FormulaValidator()

    def validate_schema(self, agreement: Agreement) -> list[str]:
        warnings = []
        warnings.extend(self.category_validator.validate(agreement))
        warnings.extend(self.salary_validator.validate(agreement))
        warnings.extend(self.formula_validator.validate(agreement))
        return warnings
