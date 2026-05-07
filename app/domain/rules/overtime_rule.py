from app.domain.entities.agreement import Agreement


def overtime_multiplier(agreement: Agreement, code: str) -> float:
    for rule in agreement.salary_model.overtime_rules:
        if rule.code == code:
            return rule.multiplier
    return 1.0
