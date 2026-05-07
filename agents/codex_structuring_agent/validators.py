from app.application.validators.agreement_validators import CategoryValidator, SalaryValidator
from app.domain.entities.agreement import Agreement


class FormulaValidator:
    def validate(self, agreement: Agreement) -> list[str]:
        warnings = []
        items = agreement.salary_model.remunerative_items + agreement.salary_model.non_remunerative_items
        for item in items:
            if item.calculation_type not in {"FIXED", "PERCENTAGE", "FORMULA"}:
                warnings.append(f"Formula invalida para {item.code}: calculation_type no soportado")
            if item.calculation_type == "FORMULA" and not item.formula:
                warnings.append(f"Formula faltante para {item.code}")
            if item.calculation_type == "PERCENTAGE" and item.rate is None:
                warnings.append(f"Porcentaje faltante para {item.code}")
        return warnings


class AgreementValidator:
    def __init__(self):
        self.category_validator = CategoryValidator()
        self.salary_validator = SalaryValidator()
        self.formula_validator = FormulaValidator()

    def validate_input(self, raw: dict) -> list[str]:
        warnings = []
        if not isinstance(raw, dict):
            return ["El input de Gemini debe ser un objeto JSON"]
        if "raw_categories" not in raw:
            warnings.append("Falta key intermedia raw_categories")
        if "raw_salary_rules" not in raw:
            warnings.append("Falta key intermedia raw_salary_rules")
        return warnings

    def validate_schema(self, agreement: Agreement) -> list[str]:
        warnings = []
        warnings.extend(self.category_validator.validate(agreement))
        warnings.extend(self.salary_validator.validate(agreement))
        warnings.extend(self.formula_validator.validate(agreement))
        return warnings


__all__ = ["AgreementValidator", "CategoryValidator", "SalaryValidator", "FormulaValidator"]
