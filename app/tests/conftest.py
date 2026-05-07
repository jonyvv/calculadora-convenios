from datetime import datetime, timezone

import pytest

from app.domain.entities.agreement import Agreement
from app.domain.entities.employee import Employee
from app.domain.entities.monthly_event import Event, MonthlyEvent


@pytest.fixture
def agreement() -> Agreement:
    return Agreement.model_validate({
        "metadata": {
            "agreement_id": "CCT_TEST",
            "name": "Convenio test",
            "version": "2026_01",
            "valid_from": "2026-01-01",
            "valid_to": None,
            "source_document": "test.txt",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "categories": [{"category_id": "A", "name": "A", "basic_salary": 100000}],
        "salary_model": {
            "remunerative_items": [
                {"code": "SENIORITY", "name": "Antiguedad", "type": "REMUNERATIVE", "rate": 1, "base_reference": "BASIC"},
                {"code": "PRESENTISMO", "name": "Presentismo", "type": "REMUNERATIVE", "rate": 10, "base_reference": "BASIC"}
            ],
            "non_remunerative_items": [{"code": "NR", "name": "No remunerativo", "type": "NON_REMUNERATIVE", "amount": 5000}],
            "deductions": [{"code": "JUBILACION", "name": "Jubilacion", "rate": 11, "base": "REMUNERATIVE_TOTAL"}],
            "fiscal_shields": [],
            "overtime_rules": [{"code": "OT_50", "multiplier": 1.5}]
        },
        "event_rules": [{"event_type": "ABSENCE", "subtype": "UNJUSTIFIED", "effects": ["LOSE_ATTENDANCE"]}],
        "audit_rules": [{"rule": "attendance_bonus_removed_if_unjustified_absence"}],
    })


@pytest.fixture
def employee() -> Employee:
    return Employee(employee_id="E1", agreement_id="CCT_TEST", category_id="A", seniority_years=3)


@pytest.fixture
def monthly_event() -> MonthlyEvent:
    return MonthlyEvent(
        employee_id="E1",
        period="2026-04",
        events=[Event(type="OVERTIME", subtype="OT_50", hours=8)],
    )
