from app.domain.entities.agreement import Agreement


def apply_fiscal_shields(agreement: Agreement, amount: float, code: str) -> float:
    for shield in agreement.salary_model.fiscal_shields:
        if shield.get("code") == code and shield.get("cap") is not None:
            return min(amount, float(shield["cap"]))
    return amount
