from app.domain.entities.monthly_event import Event, MonthlyEvent
from app.application.use_cases.calcular_liquidacion import CalcularLiquidacion
from app.domain.entities.agreement import Agreement, EventRule
from app.domain.rules.payroll_engine import PayrollEngine


def test_calculates_payroll_from_metamodel(agreement, employee, monthly_event):
    payroll = PayrollEngine().calculate(agreement, employee, monthly_event)

    assert payroll.gross_salary == 124000
    assert payroll.deductions == 13090
    assert payroll.net_salary == 110910
    assert {detail.code for detail in payroll.details} >= {"BASIC", "SENIORITY", "PRESENTISMO", "OT_50", "JUBILACION"}


def test_unjustified_absence_removes_attendance_bonus(agreement, employee):
    events = MonthlyEvent(employee_id="E1", period="2026-04", events=[Event(type="ABSENCE", subtype="UNJUSTIFIED", days=1)])
    payroll = PayrollEngine().calculate(agreement, employee, events)

    presentismo = next(detail for detail in payroll.details if detail.code == "PRESENTISMO")
    assert presentismo.amount == 0


def test_calculate_payroll_rejects_employee_category_outside_active_agreement(agreement, employee, monthly_event):
    class AgreementRepo:
        def get_active(self, agreement_id):
            return agreement

    class EmployeeRepo:
        def get(self, employee_id):
            changed = employee.model_copy()
            changed.category_id = "NO_EXISTE"
            return changed

    class EventRepo:
        def get(self, employee_id, period):
            return monthly_event

    use_case = CalcularLiquidacion(AgreementRepo(), EmployeeRepo(), EventRepo(), PayrollEngine())

    try:
        use_case.execute("E1", "2026-04")
    except ValueError as exc:
        assert "categoria del empleado" in str(exc)
    else:
        raise AssertionError("Expected category validation error")


def test_calculator_uses_agreement_defined_bases_formulas_and_deduction_aliases(employee):
    agreement = Agreement.model_validate({
        "metadata": {
            "agreement_id": "CCT_GENERAL",
            "name": "Convenio general",
            "version": "2026_04",
            "valid_from": "2026-04-01",
            "valid_to": None,
            "source_document": "test.txt",
            "created_at": "2026-05-07T00:00:00+00:00",
        },
        "categories": [{"category_id": "A", "name": "Chofer", "basic_salary": 200000}],
        "salary_model": {
            "remunerative_items": [
                {"code": "PLUS_ZONA", "name": "Zona", "type": "REMUNERATIVE", "calculation_type": "FORMULA", "formula": "Salario Básico * 20%"},
                {"code": "PRESENTISMO", "name": "Premio por presentismo", "type": "REMUNERATIVE", "calculation_type": "FIXED", "amount": 15000},
            ],
            "non_remunerative_items": [
                {"code": "VIATICO", "name": "Viatico", "type": "NON_REMUNERATIVE", "calculation_type": "FIXED", "amount": 10000},
            ],
            "deductions": [{"code": "APORTE", "name": "Aporte", "rate": 10, "base": "Total Remunerativo"}],
            "fiscal_shields": [],
            "overtime_rules": [],
        },
        "event_rules": [],
        "audit_rules": [],
    })

    payroll = PayrollEngine().calculate(agreement, employee, MonthlyEvent(employee_id="E1", period="2026-04"))

    assert next(detail for detail in payroll.details if detail.code == "PLUS_ZONA").amount == 40000
    assert payroll.gross_salary == 265000
    assert payroll.deductions == 25500
    assert payroll.net_salary == 239500


def test_calculator_applies_discount_day_from_event_rules(agreement, employee):
    agreement = agreement.model_copy(deep=True)
    agreement.event_rules = [EventRule(event_type="ABSENCE", subtype="UNJUSTIFIED", effects=["DISCOUNT_DAY", "LOSE_ATTENDANCE"])]

    payroll = PayrollEngine().calculate(
        agreement,
        employee,
        MonthlyEvent(employee_id="E1", period="2026-04", events=[Event(type="ABSENCE", subtype="UNJUSTIFIED", days=2)]),
    )

    discount = next(detail for detail in payroll.details if detail.code == "ABSENCE_UNJUSTIFIED")
    assert discount.amount == -6666.67
    assert payroll.gross_salary == 101333.33
