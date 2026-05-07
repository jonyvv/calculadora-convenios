from app.domain.entities.agreement import Agreement


def calculate_deductions(
    agreement: Agreement,
    remunerative_total: float,
    non_remunerative_total: float = 0,
    gross_salary: float | None = None,
) -> list[tuple[str, str, float]]:
    bases = {
        "REMUNERATIVE_TOTAL": remunerative_total,
        "TOTAL_REMUNERATIVO": remunerative_total,
        "TOTAL REMUNERATIVO": remunerative_total,
        "HABERES_REMUNERATIVOS": remunerative_total,
        "NON_REMUNERATIVE_TOTAL": non_remunerative_total,
        "TOTAL_NO_REMUNERATIVO": non_remunerative_total,
        "TOTAL NO REMUNERATIVO": non_remunerative_total,
        "GROSS_SALARY": gross_salary if gross_salary is not None else remunerative_total + non_remunerative_total,
        "TOTAL_HABERES": gross_salary if gross_salary is not None else remunerative_total + non_remunerative_total,
        "TOTAL HABERES": gross_salary if gross_salary is not None else remunerative_total + non_remunerative_total,
    }
    normalized_bases = {_normalize_base(key): value for key, value in bases.items()}
    results: list[tuple[str, str, float]] = []
    for deduction in agreement.salary_model.deductions:
        base = normalized_bases.get(_normalize_base(deduction.base), remunerative_total)
        amount = round(base * deduction.rate / 100, 2)
        results.append((deduction.code, deduction.name or deduction.code, amount))
    return results


def _normalize_base(value: str) -> str:
    return " ".join(str(value or "REMUNERATIVE_TOTAL").upper().replace("_", " ").split())
