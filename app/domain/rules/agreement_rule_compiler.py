from dataclasses import dataclass, field
from typing import Protocol

from app.domain.entities.agreement import Agreement, Deduction, SalaryItem
from app.domain.entities.employee import Employee
from app.domain.entities.monthly_event import Event, MonthlyEvent
from app.domain.entities.payroll import Payroll, PayrollDetail
from app.domain.rules.fiscal_rule import apply_fiscal_shields
from app.domain.rules.formula_engine import FormulaEngine
from app.domain.rules.liquidation_model import LiquidationModelResolver


@dataclass
class PayrollExecutionContext:
    agreement: Agreement
    employee: Employee
    monthly_event: MonthlyEvent
    base_salary: float
    formula_engine: FormulaEngine
    details: list[PayrollDetail] = field(default_factory=list)
    variables: dict[str, float] = field(default_factory=dict)
    monthly_hours: float = 200
    monthly_days: float = 30
    hourly_value: float = 0
    daily_value: float = 0
    category_name: str = ""

    def __post_init__(self) -> None:
        hourly_value = self.hourly_value or (self.base_salary / self.monthly_hours if self.monthly_hours else 0)
        daily_value = self.daily_value or (self.base_salary / self.monthly_days if self.monthly_days else 0)
        self.variables.update({
            "BASE_SALARY": self.base_salary,
            "BASIC": self.base_salary,
            "YEARS": self.employee.seniority_years,
            "MONTHLY_HOURS": self.monthly_hours,
            "DAYS_PER_MONTH": self.monthly_days,
            "DAILY_VALUE": daily_value,
            "VALOR_DIA": daily_value,
            "VALOR_JORNAL": daily_value,
            "HOURLY_VALUE": hourly_value,
            "VALOR_HORA": hourly_value,
            "REMUNERATIVE_TOTAL": 0,
            "NON_REMUNERATIVE_TOTAL": 0,
            "GROSS_SALARY": 0,
        })
        for item in self.agreement.salary_model.remunerative_items + self.agreement.salary_model.non_remunerative_items:
            if item.amount is None:
                continue
            self.variables[item.code] = item.amount
            self.variables[self.formula_engine.canonical_token(item.name)] = item.amount
            if "COMIDA" in self.formula_engine.canonical_token(item.name):
                self.variables["VALOR_COMIDA"] = item.amount
                self.variables["COMIDA"] = item.amount

    def add_detail(self, detail: PayrollDetail) -> None:
        self.details.append(detail)
        if detail.type == "REMUNERATIVE":
            self.variables["REMUNERATIVE_TOTAL"] = round(self.variables.get("REMUNERATIVE_TOTAL", 0) + detail.amount, 2)
        if detail.type == "NON_REMUNERATIVE":
            self.variables["NON_REMUNERATIVE_TOTAL"] = round(self.variables.get("NON_REMUNERATIVE_TOTAL", 0) + detail.amount, 2)
        if detail.type != "DEDUCTION":
            self.variables[detail.code] = detail.amount
            self.variables[self.formula_engine.canonical_token(detail.name)] = detail.amount

    def refresh_totals(self) -> None:
        remunerative = round(sum(detail.amount for detail in self.details if detail.type == "REMUNERATIVE"), 2)
        non_remunerative = round(sum(detail.amount for detail in self.details if detail.type == "NON_REMUNERATIVE"), 2)
        self.variables["REMUNERATIVE_TOTAL"] = remunerative
        self.variables["NON_REMUNERATIVE_TOTAL"] = non_remunerative
        self.variables["GROSS_SALARY"] = round(remunerative + non_remunerative, 2)

    def base(self, base_reference: str | None, default: str = "BASE_SALARY") -> float:
        token = self.formula_engine.canonical_token(base_reference or default)
        if not token or token == "NO_INDICADO":
            token = default
        return float(self.variables.get(token, self.variables.get(default, 0)))

    def has_effect_for_event(self, event: Event, effect: str) -> bool:
        if self._default_effect_for_event(event, effect):
            return True
        return any(
            rule.event_type == event.type
            and (rule.subtype is None or rule.subtype == event.subtype)
            and effect in rule.effects
            for rule in self.agreement.event_rules
        )

    def _default_effect_for_event(self, event: Event, effect: str) -> bool:
        event_type = str(event.type or "").upper()
        subtype = str(event.subtype or "").upper()
        if event_type == "ABSENCE" and subtype == "UNJUSTIFIED":
            return effect in {"DISCOUNT_DAY", "LOSE_ATTENDANCE"}
        if event_type == "HOLIDAY_WORKED" and subtype in {"", "WORKED"}:
            return effect == "PAY_OVERTIME_100"
        return False


class ExecutableRule(Protocol):
    def execute(self, context: PayrollExecutionContext) -> None:
        ...


class SalaryRuleStrategy:
    def __init__(self, item: SalaryItem):
        self.item = item

    def execute(self, context: PayrollExecutionContext) -> None:
        if self.item.input_mode == "MANUAL":
            return
        if not self._applies_to_employee(context):
            return
        amount = self.amount(context)
        if self.item.type == "NON_REMUNERATIVE":
            amount = apply_fiscal_shields(context.agreement, amount, self.item.code)
        context.add_detail(PayrollDetail(
            code=self.item.code,
            name=self.item.name,
            type=self.item.type,
            amount=round(amount, 2),
            taxable=self.item.type == "REMUNERATIVE",
        ))

    def amount(self, context: PayrollExecutionContext) -> float:
        raise NotImplementedError

    def _applies_to_employee(self, context: PayrollExecutionContext) -> bool:
        category_filters = {context.formula_engine.canonical_token(value) for value in self.item.applies_to_categories}
        if category_filters:
            category_values = {
                context.formula_engine.canonical_token(context.employee.category_id),
                context.formula_engine.canonical_token(context.category_name),
            }
            if not any(self._category_tokens_match(category_filter, category_value) for category_filter in category_filters for category_value in category_values):
                return False

        tag_filters = {context.formula_engine.canonical_token(value) for value in self.item.applies_to_tags}
        if not tag_filters:
            return True
        employee_tags = {
            context.formula_engine.canonical_token(context.employee.zone),
            context.formula_engine.canonical_token(context.employee.workday),
            context.formula_engine.canonical_token(context.category_name),
        }
        employee_blob = "_".join(sorted(value for value in employee_tags if value))
        return any(tag in employee_tags or tag in employee_blob for tag in tag_filters)

    def _category_tokens_match(self, category_filter: str, category_value: str) -> bool:
        if not category_filter or not category_value:
            return False
        if category_filter == category_value or category_filter in category_value or category_value in category_filter:
            return True
        equivalents = (
            ("CHOFER", "CHOFERES", "CONDUCTOR", "CONDUCTORES"),
            ("AUXILIAR", "AYUDANTE", "AYUDANTES"),
            ("PEON", "PEONES"),
            ("RECOLECTOR", "RECOLECTORES", "RECOLECCION", "RESIDUOS"),
            ("ADMINISTRATIVO", "ADMINISTRACION"),
        )
        return any(
            any(token in category_filter for token in group)
            and any(token in category_value for token in group)
            for group in equivalents
        )


class FixedSalaryRule(SalaryRuleStrategy):
    def amount(self, context: PayrollExecutionContext) -> float:
        return float(self.item.amount or 0)


class PercentageSalaryRule(SalaryRuleStrategy):
    def amount(self, context: PayrollExecutionContext) -> float:
        base = context.base(self.item.base_reference)
        return base * float(self.item.rate or 0) / 100


class FormulaSalaryRule(SalaryRuleStrategy):
    def amount(self, context: PayrollExecutionContext) -> float:
        return context.formula_engine.evaluate(self.item.formula or "0", context.variables)


class AttendanceGuardRule:
    """Applies event-driven effects to already compiled salary rules."""

    def execute(self, context: PayrollExecutionContext) -> None:
        loses_attendance = any(context.has_effect_for_event(event, "LOSE_ATTENDANCE") for event in context.monthly_event.events)
        if not loses_attendance:
            return
        for detail in context.details:
            value = f"{detail.code} {detail.name}".upper()
            if any(token in value for token in ("PRESENTISMO", "ATTENDANCE", "ASISTENCIA")):
                context.variables["REMUNERATIVE_TOTAL"] = round(context.variables["REMUNERATIVE_TOTAL"] - detail.amount, 2)
                detail.amount = 0
                context.variables[detail.code] = 0
        context.refresh_totals()


class EventRuleStrategy:
    def execute(self, context: PayrollExecutionContext) -> None:
        for event in context.monthly_event.events:
            if context.has_effect_for_event(event, "DISCOUNT_DAY") and event.days:
                amount = round(context.daily_value * event.days, 2)
                context.add_detail(PayrollDetail(
                    code=f"{event.type}_{event.subtype or 'DISCOUNT'}",
                    name=event.description or "Descuento por novedad",
                    type="REMUNERATIVE",
                    amount=-amount,
                ))
            if context.has_effect_for_event(event, "PAY_OVERTIME_100") and event.days:
                amount = round(context.daily_value * 2 * event.days, 2)
                context.add_detail(PayrollDetail(
                    code=f"{event.type}_{event.subtype or 'WORKED'}",
                    name=event.description or "Feriado trabajado",
                    type="REMUNERATIVE",
                    amount=amount,
                ))


class OvertimeRuleStrategy:
    def execute(self, context: PayrollExecutionContext) -> None:
        multipliers = {rule.code: rule.multiplier for rule in context.agreement.salary_model.overtime_rules}
        for event in context.monthly_event.events:
            if event.type != "OVERTIME" or not event.hours:
                continue
            multiplier = float(multipliers.get(event.subtype or "", 1))
            variables = {**context.variables, "MULTIPLIER": multiplier}
            hourly_value = context.formula_engine.evaluate("HOURLY_VALUE", variables)
            context.add_detail(PayrollDetail(
                code=event.subtype or "OVERTIME",
                name=event.description or "Horas extra",
                type="REMUNERATIVE",
                amount=round(hourly_value * multiplier * event.hours, 2),
            ))


class BonusEventRuleStrategy:
    def execute(self, context: PayrollExecutionContext) -> None:
        for event in context.monthly_event.events:
            if event.type == "BONUS" and event.amount:
                context.add_detail(PayrollDetail(
                    code=event.subtype or "BONUS",
                    name=event.description or "Adicional",
                    type="REMUNERATIVE",
                    amount=round(event.amount, 2),
                ))


class SettlementTypeRuleStrategy:
    def execute(self, context: PayrollExecutionContext) -> None:
        for event in context.monthly_event.events:
            if event.type != "LIQUIDATION":
                continue
            subtype = str(event.subtype or "").upper()
            if subtype == "SAC":
                context.refresh_totals()
                amount = round(context.variables.get("REMUNERATIVE_TOTAL", 0) * 0.5, 2)
                if amount > 0:
                    context.add_detail(PayrollDetail(
                        code="SAC",
                        name=event.description or "SAC",
                        type="REMUNERATIVE",
                        amount=amount,
                    ))


class ManualSalaryItemRuleStrategy:
    def execute(self, context: PayrollExecutionContext) -> None:
        items = {
            item.code: self._normalize_manual_item(item)
            for item in context.agreement.salary_model.remunerative_items + context.agreement.salary_model.non_remunerative_items
            if self._is_manual_like(item)
        }
        for event in context.monthly_event.events:
            if event.type not in {"SALARY_ITEM", "MANUAL_CONCEPT"} or not event.subtype:
                continue
            item = items.get(event.subtype)
            if not item:
                continue
            amount = self._amount(item, event, context)
            if amount <= 0:
                continue
            context.add_detail(PayrollDetail(
                code=item.code,
                name=event.description or item.name,
                type=item.type,
                amount=round(amount, 2),
                taxable=item.type == "REMUNERATIVE",
            ))

    def _amount(self, item: SalaryItem, event: Event, context: PayrollExecutionContext) -> float:
        if event.amount is not None and event.amount > 0:
            return float(event.amount)
        quantity = float(event.quantity or event.days or event.hours or 0)
        if quantity <= 0:
            return 0
        variables = {**context.variables, **self._quantity_variables(item, event, quantity)}
        if item.calculation_type == "FORMULA" and item.formula:
            amount = context.formula_engine.evaluate(item.formula, variables)
            formula_token = item.formula.upper()
            if not any(token in formula_token for token in ("QUANTITY", "CANTIDAD", "DAYS", "DIAS", "HOURS", "HORAS")):
                amount *= quantity
            return amount
        unit_value = float(item.amount or 0)
        if item.rate is not None:
            unit_value = context.base(item.base_reference) * float(item.rate) / 100
        return unit_value * quantity

    def _quantity_variables(self, item: SalaryItem, event: Event, quantity: float) -> dict[str, float]:
        unit = str(item.unit or self._infer_unit(item) or "").upper()
        days = float(event.days or 0)
        hours = float(event.hours or 0)
        if unit == "DAY" and days <= 0:
            days = quantity
        if unit == "HOUR" and hours <= 0:
            hours = quantity
        return {
            "QUANTITY": quantity,
            "CANTIDAD": quantity,
            "DAYS": days,
            "DIAS": days,
            "HOURS": hours,
            "HORAS": hours,
        }

    def _normalize_manual_item(self, item: SalaryItem) -> SalaryItem:
        updates = {"input_mode": "MANUAL", "unit": item.unit or self._infer_unit(item)}
        value = self._ascii(f"{item.code} {item.name} {item.base_reference}")
        is_percentage = item.rate is not None or item.calculation_type == "PERCENTAGE"
        looks_like_wage_additional = any(token in value for token in ("RAMA", "DIFERENCIAL", "RECOLECCION", "PLURALIDAD"))
        if item.type == "NON_REMUNERATIVE" and is_percentage and looks_like_wage_additional:
            updates["type"] = "REMUNERATIVE"
        return item.model_copy(update=updates)

    def _is_manual_like(self, item: SalaryItem) -> bool:
        if item.input_mode == "MANUAL" or item.unit:
            return True
        value = self._ascii(f"{item.code} {item.name} {item.base_reference}")
        if self._is_core_auto_item(value):
            return False
        if item.applies_to_categories or item.applies_to_tags:
            return True
        if any(token in value for token in ("ADIC", "ADICIONAL", "PLUS", "RAMA", "DIFERENCIAL", "PLURALIDAD")):
            return True
        manual_tokens = (
            "KM",
            "KILOMETRO",
            "KILOMETROS",
            "VIAJE",
            "VIAJES",
            "DIARIO",
            "DIARIOS",
            "REVISTAS",
            "COMISION",
            "COMISIONES",
            "PRODUCTIVIDAD",
        )
        return any(token in value for token in manual_tokens)

    def _is_core_auto_item(self, value: str) -> bool:
        return any(token in value for token in ("ANTIG", "ANTIGUEDAD", "SENIORITY", "PRESENTISMO", "ATTENDANCE", "ASISTENCIA"))

    def _infer_unit(self, item: SalaryItem) -> str | None:
        value = self._ascii(f"{item.code} {item.name} {item.base_reference}")
        if "KM" in value or "KILOMETRO" in value:
            return "KM"
        if "DIA" in value or "DIARIO" in value or "REVISTA" in value or "COMIDA" in value:
            return "DAY"
        if "VIAJE" in value:
            return "TRIP"
        if "PERNOCT" in value:
            return "NIGHT"
        if "COMISION" in value:
            return "AMOUNT"
        return None

    def _ascii(self, value: str) -> str:
        replacements = {
            "Ã¡": "a", "Ã©": "e", "Ã­": "i", "Ã³": "o", "Ãº": "u", "Ã¼": "u", "Ã±": "n",
            "Ã": "A", "Ã‰": "E", "Ã": "I", "Ã“": "O", "Ãš": "U", "Ãœ": "U", "Ã‘": "N",
            "ÃƒÂ¡": "a", "ÃƒÂ©": "e", "ÃƒÂ­": "i", "ÃƒÂ³": "o", "ÃƒÂº": "u", "ÃƒÂ¼": "u", "ÃƒÂ±": "n",
            "ÃƒÂ": "A", "Ãƒâ€°": "E", "ÃƒÂ": "I", "Ãƒâ€œ": "O", "ÃƒÅ¡": "U", "ÃƒÅ“": "U", "Ãƒâ€˜": "N",
        }
        for source, target in replacements.items():
            value = value.replace(source, target)
        return "".join(char if char.isalnum() else "_" for char in value.upper()).strip("_")


class DeductionRuleStrategy:
    def __init__(self, deduction: Deduction):
        self.deduction = deduction

    def execute(self, context: PayrollExecutionContext) -> None:
        base = context.base(self.deduction.base, "REMUNERATIVE_TOTAL")
        amount = round(base * self.deduction.rate / 100, 2)
        context.add_detail(PayrollDetail(
            code=self.deduction.code,
            name=self.deduction.name or self.deduction.code,
            type="DEDUCTION",
            amount=-amount,
            taxable=False,
        ))


@dataclass
class CompiledAgreementRules:
    salary_rules: list[ExecutableRule]
    event_rules: list[ExecutableRule]
    deduction_rules: list[ExecutableRule]
    formula_engine: FormulaEngine
    liquidation_model_resolver: LiquidationModelResolver = field(default_factory=LiquidationModelResolver)

    def execute(self, agreement: Agreement, employee: Employee, monthly_event: MonthlyEvent) -> Payroll:
        category = next((category for category in agreement.categories if category.category_id == employee.category_id), None)
        if category is None:
            raise ValueError("Employee category is not present in agreement")
        validation = self.liquidation_model_resolver.validate(agreement, monthly_event)
        if validation.estado != "ok":
            return Payroll(
                employee_id=employee.employee_id,
                period=monthly_event.period,
                gross_salary=0,
                deductions=0,
                net_salary=0,
                estado=validation.estado,
                modelo_liquidacion=validation.modelo_liquidacion,
                alertas=validation.alertas,
                datos_faltantes=validation.datos_faltantes,
                mensaje=validation.mensaje,
            )
        liquidation_base = self.liquidation_model_resolver.compute_base(agreement, category, monthly_event)

        context = PayrollExecutionContext(
            agreement=agreement,
            employee=employee,
            monthly_event=monthly_event,
            base_salary=liquidation_base.bruto_base,
            formula_engine=self.formula_engine,
            monthly_hours=self._monthly_hours(agreement, employee),
            monthly_days=self._monthly_days(agreement),
            hourly_value=liquidation_base.valor_hora,
            daily_value=liquidation_base.valor_jornal,
            category_name=category.name,
        )
        context.add_detail(PayrollDetail(
            code="BASIC",
            name="Sueldo basico",
            type="REMUNERATIVE",
            amount=round(liquidation_base.bruto_base, 2),
        ))

        for rule in self.salary_rules:
            rule.execute(context)
        context.refresh_totals()
        for rule in self.event_rules:
            rule.execute(context)
        context.refresh_totals()
        for rule in self.deduction_rules:
            rule.execute(context)

        remunerative_total = round(sum(detail.amount for detail in context.details if detail.type == "REMUNERATIVE"), 2)
        non_remunerative_total = round(sum(detail.amount for detail in context.details if detail.type == "NON_REMUNERATIVE"), 2)
        deduction_total = round(sum(abs(detail.amount) for detail in context.details if detail.type == "DEDUCTION"), 2)
        gross_salary = round(remunerative_total + non_remunerative_total, 2)
        return Payroll(
            employee_id=employee.employee_id,
            period=monthly_event.period,
            gross_salary=gross_salary,
            deductions=deduction_total,
            net_salary=round(gross_salary - deduction_total, 2),
            details=context.details,
            modelo_liquidacion=validation.modelo_liquidacion,
        )

    def _monthly_hours(self, agreement: Agreement, employee: Employee) -> float:
        jornada = agreement.jornada_tiempos.jornada_estandar or {}
        for key in ("horas_mensuales", "monthly_hours"):
            value = jornada.get(key)
            if value:
                return float(value)
        workday = self.formula_engine.canonical_token(employee.workday)
        if any(token in workday for token in ("PARCIAL", "REDUCIDA", "MEDIA")):
            return 100
        return 200

    def _monthly_days(self, agreement: Agreement) -> float:
        return self.liquidation_model_resolver.monthly_days(agreement)


class AgreementRuleCompiler:
    def __init__(self, formula_engine: FormulaEngine | None = None):
        self.formula_engine = formula_engine or FormulaEngine()

    def compile_rules(self, agreement: Agreement) -> CompiledAgreementRules:
        return CompiledAgreementRules(
            salary_rules=self._compile_salary_rules(agreement),
            event_rules=[
                AttendanceGuardRule(),
                EventRuleStrategy(),
                OvertimeRuleStrategy(),
                BonusEventRuleStrategy(),
                ManualSalaryItemRuleStrategy(),
                SettlementTypeRuleStrategy(),
            ],
            deduction_rules=[DeductionRuleStrategy(deduction) for deduction in agreement.salary_model.deductions],
            formula_engine=self.formula_engine,
            liquidation_model_resolver=LiquidationModelResolver(),
        )

    def _monthly_hours(self, agreement: Agreement, employee: Employee) -> float:
        jornada = agreement.jornada_tiempos.jornada_estandar or {}
        for key in ("horas_mensuales", "monthly_hours"):
            value = jornada.get(key)
            if value:
                return float(value)
        workday = self._ascii(employee.workday)
        if any(token in workday for token in ("PARCIAL", "REDUCIDA", "MEDIA")):
            return 100
        return 200

    def _monthly_days(self, agreement: Agreement) -> float:
        jornada = agreement.jornada_tiempos.jornada_estandar or {}
        for key in ("dias_mensuales", "monthly_days"):
            value = jornada.get(key)
            if value:
                return float(value)
        return 30

    def _compile_salary_rules(self, agreement: Agreement) -> list[ExecutableRule]:
        rules: list[ExecutableRule] = []
        items = agreement.salary_model.remunerative_items + agreement.salary_model.non_remunerative_items
        seen_semantics = set()
        for item in items:
            if item.code == "BASIC":
                continue
            item = self._normalize_item(item)
            semantic_key = self._semantic_key(item)
            if semantic_key in seen_semantics:
                continue
            seen_semantics.add(semantic_key)
            rules.append(self._compile_salary_item(item))
        return rules

    def _compile_salary_item(self, item: SalaryItem) -> ExecutableRule:
        if item.calculation_type == "FORMULA" and item.formula:
            if self._uses_years(item) and "YEAR" not in item.formula.upper() and "ANIO" not in item.formula.upper():
                item = item.model_copy(update={"formula": f"({item.formula}) * YEARS"})
            return FormulaSalaryRule(item)
        if item.rate is not None and self._uses_years(item):
            item = item.model_copy(update={
                "calculation_type": "FORMULA",
                "formula": f"{item.base_reference or 'BASE_SALARY'} * {item.rate}% * YEARS",
            })
            return FormulaSalaryRule(item)
        if item.rate is not None:
            return PercentageSalaryRule(item)
        return FixedSalaryRule(item)

    def _uses_years(self, item: SalaryItem) -> bool:
        token = f"{item.code} {item.name}".upper()
        return any(value in token for value in ("SENIORITY", "ANTIG", "ANTIGUEDAD"))

    def _normalize_item(self, item: SalaryItem) -> SalaryItem:
        value = self._ascii(f"{item.code} {item.name} {item.base_reference}")
        is_percentage = item.rate is not None or item.calculation_type == "PERCENTAGE"
        looks_like_wage_additional = any(token in value for token in ("RAMA", "DIFERENCIAL", "RECOLECCION", "PLURALIDAD"))
        inferred_tags = self._inferred_tags(item)
        if self._is_manual_like(item):
            item = item.model_copy(update={"input_mode": "MANUAL", "unit": item.unit or self._infer_unit(item)})
        if inferred_tags and not item.applies_to_tags:
            item = item.model_copy(update={"applies_to_tags": inferred_tags})
        if item.type == "NON_REMUNERATIVE" and is_percentage and looks_like_wage_additional:
            return item.model_copy(update={"type": "REMUNERATIVE"})
        return item

    def _is_manual_like(self, item: SalaryItem) -> bool:
        if item.input_mode == "MANUAL" or item.unit:
            return True
        value = self._ascii(f"{item.code} {item.name} {item.base_reference}")
        if self._is_core_auto_item(value):
            return False
        if item.applies_to_categories or item.applies_to_tags:
            return True
        if any(token in value for token in ("ADIC", "ADICIONAL", "PLUS", "RAMA", "DIFERENCIAL", "PLURALIDAD")):
            return True
        manual_tokens = (
            "KM",
            "KILOMETRO",
            "KILOMETROS",
            "VIAJE",
            "VIAJES",
            "DIARIO",
            "DIARIOS",
            "REVISTAS",
            "COMISION",
            "COMISIONES",
            "PRODUCTIVIDAD",
        )
        return any(token in value for token in manual_tokens)

    def _is_core_auto_item(self, value: str) -> bool:
        return any(token in value for token in ("ANTIG", "ANTIGUEDAD", "SENIORITY", "PRESENTISMO", "ATTENDANCE", "ASISTENCIA"))

    def _infer_unit(self, item: SalaryItem) -> str | None:
        value = self._ascii(f"{item.code} {item.name} {item.base_reference}")
        if "KM" in value or "KILOMETRO" in value:
            return "KM"
        if "DIA" in value or "DIARIO" in value or "REVISTA" in value or "COMIDA" in value:
            return "DAY"
        if "VIAJE" in value:
            return "TRIP"
        if "PERNOCT" in value:
            return "NIGHT"
        if "COMISION" in value:
            return "AMOUNT"
        return None

    def _inferred_tags(self, item: SalaryItem) -> list[str]:
        value = self._ascii(f"{item.code} {item.name} {item.base_reference}")
        tags = []
        tag_map = {
            "CAUDALES": ("CAUDALES",),
            "RECOLECCION": ("RECOLECCION", "RESIDUOS"),
            "LACTEA": ("LACTEA", "LACTEO"),
            "AUXILIO": ("AUXILIO", "REMOLQUE"),
            "PLURALIDAD_GRUPO_III": ("PLURALIDAD", "GRUPO_III"),
            "PLURALIDAD_GRUPO_I": ("PLURALIDAD", "GRUPO_I"),
        }
        for tag, tokens in tag_map.items():
            if any(token in value for token in tokens):
                tags.append(tag)
        return tags

    def _semantic_key(self, item: SalaryItem) -> str:
        value = self._ascii(f"{item.code} {item.name}")
        if "ANTIG" in value or "SENIORITY" in value:
            return "SENIORITY"
        if "PRESENTISMO" in value or "ATTENDANCE" in value or "ASISTENCIA" in value:
            return "PRESENTISMO"
        if "PLURALIDAD" in value:
            if "GRUPO_III" in value or "GRUPO_3" in value or value.endswith("_III") or "_III_" in value:
                return "PLURALIDAD_GRUPO_III"
            if "GRUPO_I" in value or "GRUPO_1" in value or value.endswith("_I") or "_I_" in value:
                return "PLURALIDAD_GRUPO_I"
            return "PLURALIDAD"
        return value

    def _ascii(self, value: str) -> str:
        replacements = {
            "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n",
            "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U", "Ñ": "N",
            "Ã¡": "a", "Ã©": "e", "Ã­": "i", "Ã³": "o", "Ãº": "u", "Ã¼": "u", "Ã±": "n",
            "Ã": "A", "Ã‰": "E", "Ã": "I", "Ã“": "O", "Ãš": "U", "Ãœ": "U", "Ã‘": "N",
        }
        for source, target in replacements.items():
            value = value.replace(source, target)
        return "".join(char if char.isalnum() else "_" for char in value.upper()).strip("_")
