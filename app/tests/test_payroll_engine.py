from app.domain.entities.monthly_event import Event, MonthlyEvent
from app.application.use_cases.calcular_liquidacion import CalcularLiquidacion
from app.domain.entities.agreement import Agreement, EventRule
from app.domain.rules.agreement_rule_compiler import AgreementRuleCompiler
from app.domain.rules.formula_engine import FormulaEngine
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


def test_unjustified_absence_removes_attendance_bonus_even_without_declared_event_rule(agreement, employee):
    agreement = agreement.model_copy(deep=True)
    agreement.event_rules = []

    payroll = PayrollEngine().calculate(
        agreement,
        employee,
        MonthlyEvent(employee_id="E1", period="2026-04", events=[Event(type="ABSENCE", subtype="UNJUSTIFIED", days=6)]),
    )

    presentismo = next(detail for detail in payroll.details if detail.code == "PRESENTISMO")
    absence = next(detail for detail in payroll.details if detail.code == "ABSENCE_UNJUSTIFIED")
    assert presentismo.amount == 0
    assert absence.amount == -20000
    assert payroll.gross_salary == 88000


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

    without_event = PayrollEngine().calculate(agreement, employee, MonthlyEvent(employee_id="E1", period="2026-04"))
    payroll = PayrollEngine().calculate(
        agreement,
        employee,
        MonthlyEvent(employee_id="E1", period="2026-04", events=[Event(type="SALARY_ITEM", subtype="PLUS_ZONA", quantity=1)]),
    )

    assert all(detail.code != "PLUS_ZONA" for detail in without_event.details)
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


def test_formula_engine_resolves_payroll_variables():
    result = FormulaEngine().evaluate(
        "(BASE_SALARY / MONTHLY_HOURS) * MULTIPLIER * 8 + BASE_SALARY * 1% * YEARS",
        {"BASE_SALARY": 200000, "MONTHLY_HOURS": 200, "MULTIPLIER": 1.5, "YEARS": 3},
    )

    assert result == 18000


def test_agreement_rule_compiler_returns_executable_rules(agreement):
    compiled = AgreementRuleCompiler().compile_rules(agreement)

    assert compiled.salary_rules
    assert compiled.event_rules
    assert compiled.deduction_rules


def test_compiler_deduplicates_semantic_salary_rules(employee):
    employee = employee.model_copy(update={"zone": "Recoleccion Pluralidad Grupo I"})
    agreement = Agreement.model_validate({
        "metadata": {
            "agreement_id": "CCT_DUP",
            "name": "Convenio duplicado",
            "version": "2026_04",
            "valid_from": "2026-04-01",
            "valid_to": None,
            "source_document": "test.txt",
            "created_at": "2026-05-08T00:00:00+00:00",
        },
        "categories": [{"category_id": "A", "name": "Chofer", "basic_salary": 100000}],
        "salary_model": {
            "remunerative_items": [
                {"code": "PLUS_POR_PLURALIDAD_DE_TAREAS_GRUPO_I", "name": "Plus por Pluralidad de Tareas Grupo I", "type": "REMUNERATIVE", "calculation_type": "PERCENTAGE", "rate": 25, "base_reference": "BASIC"},
                {"code": "HR07", "name": "Pluralidad Tareas Grupo I", "type": "REMUNERATIVE", "calculation_type": "PERCENTAGE", "rate": 25, "base_reference": "BASIC"},
            ],
            "non_remunerative_items": [
                {"code": "HNR01", "name": "Comida", "type": "NON_REMUNERATIVE", "calculation_type": "FIXED", "amount": 10000},
                {"code": "DIFERENCIAL_RAMA_RECOLECCION", "name": "Diferencial Rama Recoleccion", "type": "NON_REMUNERATIVE", "calculation_type": "PERCENTAGE", "rate": 15, "base_reference": "Valor comida"},
            ],
            "deductions": [],
            "fiscal_shields": [],
            "overtime_rules": [],
        },
        "event_rules": [],
        "audit_rules": [],
    })

    without_event = PayrollEngine().calculate(agreement, employee, MonthlyEvent(employee_id="E1", period="2026-05"))
    payroll = PayrollEngine().calculate(
        agreement,
        employee,
        MonthlyEvent(employee_id="E1", period="2026-05", events=[
            Event(type="SALARY_ITEM", subtype="HR07", quantity=1),
            Event(type="SALARY_ITEM", subtype="DIFERENCIAL_RAMA_RECOLECCION", quantity=1),
        ]),
    )
    pluralidad = [detail for detail in payroll.details if "Pluralidad" in detail.name]
    diferencial = next(detail for detail in payroll.details if detail.code == "DIFERENCIAL_RAMA_RECOLECCION")

    assert all("Pluralidad" not in detail.name for detail in without_event.details)
    assert all(detail.code != "DIFERENCIAL_RAMA_RECOLECCION" for detail in without_event.details)
    assert len(pluralidad) == 1
    assert pluralidad[0].amount == 25000
    assert diferencial.type == "REMUNERATIVE"
    assert diferencial.amount == 1500


def test_branch_allowances_are_manual_and_require_explicit_event(employee):
    agreement = Agreement.model_validate({
        "metadata": {
            "agreement_id": "CCT_BRANCH",
            "name": "Convenio ramas",
            "version": "2026_04",
            "valid_from": "2026-04-01",
            "valid_to": None,
            "source_document": "test.txt",
            "created_at": "2026-05-08T00:00:00+00:00",
        },
        "categories": [{"category_id": "A", "name": "Chofer", "basic_salary": 100000}],
        "salary_model": {
            "remunerative_items": [
                {"code": "HR03", "name": "Rama Caudales", "type": "REMUNERATIVE", "calculation_type": "PERCENTAGE", "rate": 20, "base_reference": "BASIC"},
                {"code": "HR04", "name": "Rama Recoleccion", "type": "REMUNERATIVE", "calculation_type": "PERCENTAGE", "rate": 15, "base_reference": "BASIC"},
                {"code": "HR05", "name": "Rama Lactea", "type": "REMUNERATIVE", "calculation_type": "PERCENTAGE", "rate": 15, "base_reference": "BASIC"},
            ],
            "non_remunerative_items": [],
            "deductions": [],
            "fiscal_shields": [],
            "overtime_rules": [],
        },
        "event_rules": [],
        "audit_rules": [],
    })

    without_event = PayrollEngine().calculate(
        agreement,
        employee.model_copy(update={"zone": "Recoleccion"}),
        MonthlyEvent(employee_id="E1", period="2026-05"),
    )
    with_event = PayrollEngine().calculate(
        agreement,
        employee.model_copy(update={"zone": "Recoleccion"}),
        MonthlyEvent(employee_id="E1", period="2026-05", events=[Event(type="SALARY_ITEM", subtype="HR04", quantity=1)]),
    )

    without_codes = {detail.code for detail in without_event.details}
    with_codes = {detail.code for detail in with_event.details}
    assert "HR04" not in without_codes
    assert "HR03" not in without_codes
    assert "HR05" not in without_codes
    assert "HR04" in with_codes
    assert next(detail for detail in with_event.details if detail.code == "HR04").amount == 15000


def test_holiday_worked_event_is_reflected_in_payroll(agreement, employee):
    agreement = agreement.model_copy(deep=True)
    agreement.event_rules = [EventRule(event_type="HOLIDAY_WORKED", subtype="WORKED", effects=["PAY_OVERTIME_100"])]

    payroll = PayrollEngine().calculate(
        agreement,
        employee,
        MonthlyEvent(employee_id="E1", period="2026-05", events=[Event(type="HOLIDAY_WORKED", subtype="WORKED", days=2)]),
    )

    holiday = next(detail for detail in payroll.details if detail.code == "HOLIDAY_WORKED_WORKED")
    assert holiday.amount == 13333.33


def test_manual_salary_items_are_not_automatic_and_require_event(employee):
    agreement = Agreement.model_validate({
        "metadata": {
            "agreement_id": "CCT_MANUAL",
            "name": "Convenio manual",
            "version": "2026_05",
            "valid_from": "2026-05-01",
            "valid_to": None,
            "source_document": "test.txt",
            "created_at": "2026-05-08T00:00:00+00:00",
        },
        "categories": [{"category_id": "A", "name": "Chofer", "basic_salary": 100000}],
        "salary_model": {
            "remunerative_items": [],
            "non_remunerative_items": [
                {"code": "VIATICO_KM", "name": "Viatico por kilometro", "type": "NON_REMUNERATIVE", "calculation_type": "FIXED", "amount": 50, "input_mode": "MANUAL", "unit": "KM"},
            ],
            "deductions": [],
            "fiscal_shields": [],
            "overtime_rules": [],
        },
        "event_rules": [],
        "audit_rules": [],
    })

    without_event = PayrollEngine().calculate(agreement, employee, MonthlyEvent(employee_id="E1", period="2026-05"))
    with_event = PayrollEngine().calculate(
        agreement,
        employee,
        MonthlyEvent(employee_id="E1", period="2026-05", events=[Event(type="SALARY_ITEM", subtype="VIATICO_KM", quantity=120)]),
    )

    assert all(detail.code != "VIATICO_KM" for detail in without_event.details)
    viatico = next(detail for detail in with_event.details if detail.code == "VIATICO_KM")
    assert viatico.amount == 6000


def test_manual_salary_item_category_filter_accepts_chofer_conductor_equivalence(employee):
    agreement = Agreement.model_validate({
        "metadata": {
            "agreement_id": "CCT_MANUAL_CHOFERES",
            "name": "Convenio manual choferes",
            "version": "2026_05",
            "valid_from": "2026-05-01",
            "valid_to": None,
            "source_document": "test.txt",
            "created_at": "2026-05-08T00:00:00+00:00",
        },
        "categories": [{"category_id": "A", "name": "Conductores De Primera Categoria", "basic_salary": 100000}],
        "salary_model": {
            "remunerative_items": [
                {
                    "code": "RETRIB_KM",
                    "name": "Retribucion por KM",
                    "type": "REMUNERATIVE",
                    "calculation_type": "FIXED",
                    "amount": 120,
                    "applies_to_categories": ["CHOFERES"],
                    "input_mode": "MANUAL",
                    "unit": "KM",
                },
            ],
            "non_remunerative_items": [],
            "deductions": [],
            "fiscal_shields": [],
            "overtime_rules": [],
        },
        "event_rules": [],
        "audit_rules": [],
    })

    payroll = PayrollEngine().calculate(
        agreement,
        employee.model_copy(update={"category_id": "A"}),
        MonthlyEvent(employee_id="E1", period="2026-05", events=[Event(type="SALARY_ITEM", subtype="RETRIB_KM", quantity=10)]),
    )

    retribucion = next(detail for detail in payroll.details if detail.code == "RETRIB_KM")
    assert retribucion.amount == 1200


def test_unit_based_salary_items_are_treated_as_manual_even_if_marked_auto(employee):
    agreement = Agreement.model_validate({
        "metadata": {
            "agreement_id": "CCT_UNIT_AUTO",
            "name": "Convenio unidad auto",
            "version": "2026_05",
            "valid_from": "2026-05-01",
            "valid_to": None,
            "source_document": "test.txt",
            "created_at": "2026-05-08T00:00:00+00:00",
        },
        "categories": [{"category_id": "A", "name": "Chofer", "basic_salary": 100000}],
        "salary_model": {
            "remunerative_items": [
                {
                    "code": "ADIC_DIARIOS",
                    "name": "Adicional Diarios/Revistas",
                    "type": "REMUNERATIVE",
                    "calculation_type": "PERCENTAGE",
                    "rate": 12,
                    "base_reference": "BASIC",
                    "input_mode": "AUTO",
                    "unit": "DAY",
                },
            ],
            "non_remunerative_items": [],
            "deductions": [],
            "fiscal_shields": [],
            "overtime_rules": [],
        },
        "event_rules": [],
        "audit_rules": [],
    })

    without_event = PayrollEngine().calculate(agreement, employee, MonthlyEvent(employee_id="E1", period="2026-05"))
    with_event = PayrollEngine().calculate(
        agreement,
        employee,
        MonthlyEvent(employee_id="E1", period="2026-05", events=[Event(type="SALARY_ITEM", subtype="ADIC_DIARIOS", quantity=2)]),
    )

    assert all(detail.code != "ADIC_DIARIOS" for detail in without_event.details)
    adicional = next(detail for detail in with_event.details if detail.code == "ADIC_DIARIOS")
    assert adicional.amount == 24000


def test_manual_day_formula_uses_quantity_as_days(employee):
    agreement = Agreement.model_validate({
        "metadata": {
            "agreement_id": "CCT_DAYS",
            "name": "Convenio dias",
            "version": "2026_05",
            "valid_from": "2026-05-01",
            "valid_to": None,
            "source_document": "test.txt",
            "created_at": "2026-05-08T00:00:00+00:00",
        },
        "categories": [{"category_id": "A", "name": "Chofer", "basic_salary": 300000}],
        "salary_model": {
            "remunerative_items": [
                {
                    "code": "VIAT_DIA",
                    "name": "Viatico diario",
                    "type": "REMUNERATIVE",
                    "calculation_type": "FORMULA",
                    "formula": "VALOR_DIA * DIAS",
                    "input_mode": "MANUAL",
                    "unit": "DAY",
                },
            ],
            "non_remunerative_items": [],
            "deductions": [],
            "fiscal_shields": [],
            "overtime_rules": [],
        },
        "event_rules": [],
        "audit_rules": [],
    })

    payroll = PayrollEngine().calculate(
        agreement,
        employee.model_copy(update={"category_id": "A"}),
        MonthlyEvent(employee_id="E1", period="2026-05", events=[Event(type="SALARY_ITEM", subtype="VIAT_DIA", quantity=3)]),
    )

    viatico = next(detail for detail in payroll.details if detail.code == "VIAT_DIA")
    assert viatico.amount == 30000


def test_sac_liquidation_type_adds_half_remunerative_total(employee):
    agreement = Agreement.model_validate({
        "metadata": {
            "agreement_id": "CCT_SAC",
            "name": "Convenio SAC",
            "version": "2026_06",
            "valid_from": "2026-06-01",
            "valid_to": None,
            "source_document": "test.txt",
            "created_at": "2026-05-08T00:00:00+00:00",
        },
        "categories": [{"category_id": "A", "name": "Administrativo", "basic_salary": 200000}],
        "salary_model": {
            "remunerative_items": [
                {"code": "PRESENTISMO", "name": "Presentismo", "type": "REMUNERATIVE", "calculation_type": "FIXED", "amount": 20000},
            ],
            "non_remunerative_items": [],
            "deductions": [],
            "fiscal_shields": [],
            "overtime_rules": [],
        },
        "event_rules": [],
        "audit_rules": [],
    })

    payroll = PayrollEngine().calculate(
        agreement,
        employee.model_copy(update={"category_id": "A"}),
        MonthlyEvent(employee_id="E1", period="2026-06", events=[Event(type="LIQUIDATION", subtype="SAC")]),
    )

    sac = next(detail for detail in payroll.details if detail.code == "SAC")
    assert sac.amount == 110000


def test_old_agreement_without_liquidation_model_defaults_to_base_salary(agreement, employee):
    payroll = PayrollEngine().calculate(agreement, employee, MonthlyEvent(employee_id="E1", period="2026-05"))

    assert payroll.estado == "ok"
    assert payroll.modelo_liquidacion == "sueldo_base"
    assert next(detail for detail in payroll.details if detail.code == "BASIC").amount == 100000


def test_hourly_liquidation_requires_worked_hours(employee):
    agreement = Agreement.model_validate({
        "metadata": {
            "agreement_id": "CCT_HORA",
            "name": "Convenio por hora",
            "version": "2026_05",
            "valid_from": "2026-05-01",
            "valid_to": None,
            "source_document": "test.txt",
            "created_at": "2026-05-08T00:00:00+00:00",
        },
        "modelo_liquidacion": {
            "tipo": "por_hora",
            "unidad_principal": "hora",
            "base_calculo": "valor_hora_categoria",
            "formula_base": "valor_hora_categoria * horas_trabajadas",
            "requiere_horas_trabajadas": True,
        },
        "categories": [{"category_id": "A", "name": "Operario por hora", "basic_salary": 0, "valor_hora": 2500}],
        "salary_model": {"remunerative_items": [], "non_remunerative_items": [], "deductions": [], "fiscal_shields": [], "overtime_rules": []},
        "event_rules": [],
        "audit_rules": [],
    })

    payroll = PayrollEngine().calculate(agreement, employee.model_copy(update={"category_id": "A"}), MonthlyEvent(employee_id="E1", period="2026-05"))

    assert payroll.estado == "faltan_datos"
    assert payroll.datos_faltantes == ["horas_trabajadas"]
    assert payroll.gross_salary == 0


def test_hourly_liquidation_uses_category_hour_value(employee):
    agreement = Agreement.model_validate({
        "metadata": {
            "agreement_id": "CCT_HORA",
            "name": "Convenio por hora",
            "version": "2026_05",
            "valid_from": "2026-05-01",
            "valid_to": None,
            "source_document": "test.txt",
            "created_at": "2026-05-08T00:00:00+00:00",
        },
        "modelo_liquidacion": {
            "tipo": "por_hora",
            "unidad_principal": "hora",
            "base_calculo": "valor_hora_categoria",
            "formula_base": "valor_hora_categoria * horas_trabajadas",
            "requiere_horas_trabajadas": True,
        },
        "categories": [{"category_id": "A", "name": "Operario por hora", "basic_salary": 0, "valor_hora": 2500}],
        "salary_model": {
            "remunerative_items": [{"code": "PRESENTISMO", "name": "Presentismo", "type": "REMUNERATIVE", "calculation_type": "PERCENTAGE", "rate": 10, "base_reference": "BASIC"}],
            "non_remunerative_items": [],
            "deductions": [],
            "fiscal_shields": [],
            "overtime_rules": [{"code": "OT_50", "multiplier": 1.5}],
        },
        "event_rules": [],
        "audit_rules": [],
    })

    payroll = PayrollEngine().calculate(
        agreement,
        employee.model_copy(update={"category_id": "A"}),
        MonthlyEvent(employee_id="E1", period="2026-05", events=[
            Event(type="WORKED_HOURS", subtype="HORAS_TRABAJADAS", hours=120),
            Event(type="OVERTIME", subtype="OT_50", hours=4),
        ]),
    )

    assert payroll.estado == "ok"
    assert payroll.modelo_liquidacion == "por_hora"
    assert next(detail for detail in payroll.details if detail.code == "BASIC").amount == 300000
    assert next(detail for detail in payroll.details if detail.code == "PRESENTISMO").amount == 30000
    assert next(detail for detail in payroll.details if detail.code == "OT_50").amount == 15000


def test_jornal_liquidation_uses_worked_days(employee):
    agreement = Agreement.model_validate({
        "metadata": {
            "agreement_id": "CCT_JORNAL",
            "name": "Convenio jornal",
            "version": "2026_05",
            "valid_from": "2026-05-01",
            "valid_to": None,
            "source_document": "test.txt",
            "created_at": "2026-05-08T00:00:00+00:00",
        },
        "modelo_liquidacion": {
            "tipo": "jornal",
            "unidad_principal": "dia",
            "base_calculo": "valor_jornal_categoria",
            "formula_base": "valor_jornal_categoria * dias_trabajados",
            "requiere_dias_trabajados": True,
        },
        "categories": [{"category_id": "A", "name": "Jornalero", "basic_salary": 0, "valor_jornal": 15000}],
        "salary_model": {"remunerative_items": [], "non_remunerative_items": [], "deductions": [], "fiscal_shields": [], "overtime_rules": []},
        "event_rules": [],
        "audit_rules": [],
    })

    payroll = PayrollEngine().calculate(
        agreement,
        employee.model_copy(update={"category_id": "A"}),
        MonthlyEvent(employee_id="E1", period="2026-05", events=[Event(type="WORKED_DAYS", subtype="DIAS_TRABAJADOS", days=18)]),
    )

    assert payroll.estado == "ok"
    assert payroll.modelo_liquidacion == "jornal"
    assert next(detail for detail in payroll.details if detail.code == "BASIC").amount == 270000


def test_liquidation_model_pre_audit_requires_confirmation_for_outlier_hours(employee):
    agreement = Agreement.model_validate({
        "metadata": {
            "agreement_id": "CCT_HORA_ALERTA",
            "name": "Convenio por hora alerta",
            "version": "2026_05",
            "valid_from": "2026-05-01",
            "valid_to": None,
            "source_document": "test.txt",
            "created_at": "2026-05-08T00:00:00+00:00",
        },
        "modelo_liquidacion": {"tipo": "por_hora", "unidad_principal": "hora", "requiere_horas_trabajadas": True},
        "categories": [{"category_id": "A", "name": "Operario", "basic_salary": 200000, "valor_hora": 2000}],
        "salary_model": {"remunerative_items": [], "non_remunerative_items": [], "deductions": [], "fiscal_shields": [], "overtime_rules": []},
        "event_rules": [],
        "audit_rules": [],
    })

    payroll = PayrollEngine().calculate(
        agreement,
        employee.model_copy(update={"category_id": "A"}),
        MonthlyEvent(employee_id="E1", period="2026-05", events=[Event(type="WORKED_HOURS", subtype="HORAS_TRABAJADAS", hours=300)]),
    )

    assert payroll.estado == "requiere_confirmacion"
    assert payroll.alertas
    assert payroll.gross_salary == 0


def test_mixed_liquidation_keeps_base_salary_and_existing_concepts(employee):
    agreement = Agreement.model_validate({
        "metadata": {
            "agreement_id": "CCT_MIXTO",
            "name": "Convenio mixto",
            "version": "2026_05",
            "valid_from": "2026-05-01",
            "valid_to": None,
            "source_document": "test.txt",
            "created_at": "2026-05-08T00:00:00+00:00",
        },
        "modelo_liquidacion": {"tipo": "mixto", "unidad_principal": "mixto", "base_calculo": "combinado"},
        "categories": [{"category_id": "A", "name": "Mixto", "basic_salary": 200000}],
        "salary_model": {
            "remunerative_items": [{"code": "BONO_FIJO", "name": "Bono fijo", "type": "REMUNERATIVE", "calculation_type": "FIXED", "amount": 20000}],
            "non_remunerative_items": [],
            "deductions": [],
            "fiscal_shields": [],
            "overtime_rules": [{"code": "OT_50", "multiplier": 1.5}],
        },
        "event_rules": [],
        "audit_rules": [],
    })

    payroll = PayrollEngine().calculate(
        agreement,
        employee.model_copy(update={"category_id": "A"}),
        MonthlyEvent(employee_id="E1", period="2026-05", events=[Event(type="OVERTIME", subtype="OT_50", hours=2)]),
    )

    assert payroll.modelo_liquidacion == "mixto"
    assert next(detail for detail in payroll.details if detail.code == "BASIC").amount == 200000
    assert next(detail for detail in payroll.details if detail.code == "BONO_FIJO").amount == 20000
    assert next(detail for detail in payroll.details if detail.code == "OT_50").amount == 3000
