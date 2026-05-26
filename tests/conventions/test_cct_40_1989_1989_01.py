from pathlib import Path

import pytest

from app.domain.entities.agreement import Agreement


def load_agreement():
    path = Path("storage/convenios/CCT_40_1989/1989_01.json")
    if not path.exists():
        pytest.skip(f"Generated convention JSON not found: {path}")
    return Agreement.model_validate_json(path.read_text(encoding="utf-8"))


def test_convention_json_is_valid():
    agreement = load_agreement()
    assert agreement.metadata.agreement_id == "CCT_40_1989"


def test_convention_categories_are_valid():
    agreement = load_agreement()
    assert agreement.categories
    assert all(category.category_id and category.basic_salary > 0 for category in agreement.categories)


def test_convention_overtime_rules_are_valid():
    agreement = load_agreement()
    assert all(rule.code and rule.multiplier > 1 for rule in agreement.salary_model.overtime_rules)


def test_convention_deductions_are_valid():
    agreement = load_agreement()
    assert agreement.salary_model.deductions
    assert all(deduction.code and deduction.rate > 0 for deduction in agreement.salary_model.deductions)


def test_convention_formulas_are_valid():
    agreement = load_agreement()
    items = agreement.salary_model.remunerative_items + agreement.salary_model.non_remunerative_items
    assert all(item.calculation_type in {"FIXED", "PERCENTAGE", "FORMULA"} for item in items)
