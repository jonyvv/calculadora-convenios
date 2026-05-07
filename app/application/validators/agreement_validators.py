from app.domain.entities.agreement import Agreement


class CategoryValidator:
    def validate(self, agreement: Agreement) -> list[str]:
        warnings = []
        if not agreement.categories:
            warnings.append("Faltan categorias del convenio")
        for category in agreement.categories:
            if category.basic_salary <= 0:
                warnings.append(f"Categoria {category.category_id} sin sueldo basico valido")
        return warnings


class SalaryValidator:
    def validate(self, agreement: Agreement) -> list[str]:
        warnings = []
        if not agreement.salary_model.deductions:
            warnings.append("Faltan deducciones")
        for deduction in agreement.salary_model.deductions:
            if deduction.rate <= 0:
                warnings.append(f"Deduccion {deduction.code} sin alicuota valida")
        for rule in agreement.salary_model.overtime_rules:
            if rule.multiplier <= 1:
                warnings.append(f"Hora extra {rule.code} sin multiplicador valido")
        return warnings


class EventRulesValidator:
    def validate(self, agreement: Agreement) -> list[str]:
        return ["No se detectaron reglas de novedades"] if not agreement.event_rules else []


class ComplianceValidator:
    def validate(self, agreement: Agreement) -> list[str]:
        return ["No se detectaron reglas de auditoria/compliance"] if not agreement.audit_rules else []


class AgreementValidationService:
    def __init__(self):
        self.category_validator = CategoryValidator()
        self.salary_validator = SalaryValidator()
        self.event_rules_validator = EventRulesValidator()
        self.compliance_validator = ComplianceValidator()

    def validate_raw(self, raw: dict) -> list[str]:
        required = ["raw_categories", "raw_salary_rules"]
        return [f"Falta key intermedia {key}" for key in required if key not in raw]

    def validate_agreement(self, agreement: Agreement) -> list[str]:
        warnings = []
        warnings.extend(self.category_validator.validate(agreement))
        warnings.extend(self.salary_validator.validate(agreement))
        warnings.extend(self.event_rules_validator.validate(agreement))
        warnings.extend(self.compliance_validator.validate(agreement))
        return warnings
