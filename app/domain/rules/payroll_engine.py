import ast
import operator
import re

from app.domain.entities.agreement import Agreement
from app.domain.entities.agreement import SalaryItem
from app.domain.entities.employee import Employee
from app.domain.entities.monthly_event import Event
from app.domain.entities.monthly_event import MonthlyEvent
from app.domain.entities.payroll import Payroll, PayrollDetail
from app.domain.rules.attendance_rule import loses_attendance_bonus
from app.domain.rules.deduction_rule import calculate_deductions
from app.domain.rules.fiscal_rule import apply_fiscal_shields
from app.domain.rules.overtime_rule import overtime_multiplier


class PayrollEngine:
    HOURS_PER_MONTH = 200
    DAYS_PER_MONTH = 30

    def calculate(self, agreement: Agreement, employee: Employee, monthly_event: MonthlyEvent) -> Payroll:
        category = next((c for c in agreement.categories if c.category_id == employee.category_id), None)
        if category is None:
            raise ValueError("Employee category is not present in agreement")

        context = {
            "BASIC": category.basic_salary,
            "BASICO": category.basic_salary,
            "SALARIO_BASICO": category.basic_salary,
            "SENIORITY_YEARS": employee.seniority_years,
            "ANTIGUEDAD_ANIOS": employee.seniority_years,
            "HOURS_PER_MONTH": self.HOURS_PER_MONTH,
            "DAYS_PER_MONTH": self.DAYS_PER_MONTH,
        }
        details: list[PayrollDetail] = [
            PayrollDetail(code="BASIC", name="Sueldo basico", type="REMUNERATIVE", amount=round(category.basic_salary, 2))
        ]
        context["REMUNERATIVE_TOTAL"] = category.basic_salary
        context["TOTAL_REMUNERATIVO"] = category.basic_salary

        for item in agreement.salary_model.remunerative_items:
            if item.code == "BASIC":
                continue
            amount = self._calculate_item(item, context)
            if self._is_attendance_item(item) and loses_attendance_bonus(agreement, monthly_event.events):
                amount = 0
            details.append(PayrollDetail(code=item.code, name=item.name, type="REMUNERATIVE", amount=amount))
            context[item.code.upper()] = amount
            context["REMUNERATIVE_TOTAL"] = round(context["REMUNERATIVE_TOTAL"] + amount, 2)
            context["TOTAL_REMUNERATIVO"] = context["REMUNERATIVE_TOTAL"]

        for detail in self._event_adjustments(agreement, category.basic_salary, monthly_event.events):
            details.append(detail)

        for event in monthly_event.events:
            if event.type == "OVERTIME" and event.hours:
                multiplier = overtime_multiplier(agreement, event.subtype or "")
                hourly_value = category.basic_salary / self.HOURS_PER_MONTH
                details.append(PayrollDetail(
                    code=event.subtype or "OVERTIME",
                    name="Horas extra",
                    type="REMUNERATIVE",
                    amount=round(hourly_value * multiplier * event.hours, 2),
                ))
            if event.type == "BONUS" and event.amount:
                details.append(PayrollDetail(
                    code=event.subtype or "BONUS",
                    name=event.description or "Adicional",
                    type="REMUNERATIVE",
                    amount=round(event.amount, 2),
                ))

        remunerative_total = round(sum(d.amount for d in details if d.type == "REMUNERATIVE"), 2)
        context["REMUNERATIVE_TOTAL"] = remunerative_total
        context["TOTAL_REMUNERATIVO"] = remunerative_total

        for item in agreement.salary_model.non_remunerative_items:
            amount = self._calculate_item(item, context)
            amount = apply_fiscal_shields(agreement, amount, item.code)
            details.append(PayrollDetail(code=item.code, name=item.name, type="NON_REMUNERATIVE", amount=amount, taxable=False))
            context[item.code.upper()] = amount

        remunerative_total = round(sum(d.amount for d in details if d.type == "REMUNERATIVE"), 2)
        non_remunerative_total = round(sum(d.amount for d in details if d.type == "NON_REMUNERATIVE"), 2)
        gross_salary = round(remunerative_total + non_remunerative_total, 2)

        deduction_total = 0.0
        for code, name, amount in calculate_deductions(agreement, remunerative_total, non_remunerative_total, gross_salary):
            deduction_total = round(deduction_total + amount, 2)
            details.append(PayrollDetail(code=code, name=name, type="DEDUCTION", amount=-amount, taxable=False))

        net_salary = round(gross_salary - deduction_total, 2)
        return Payroll(
            employee_id=employee.employee_id,
            period=monthly_event.period,
            gross_salary=gross_salary,
            deductions=deduction_total,
            net_salary=net_salary,
            details=details,
        )

    def _calculate_item(self, item: SalaryItem, context: dict[str, float]) -> float:
        if item.calculation_type == "FORMULA" and item.formula:
            return round(self._evaluate_formula(item.formula, context), 2)
        if item.amount is not None:
            amount = item.amount
            if item.calculation_type == "FIXED":
                return round(amount, 2)
        if item.rate is not None:
            base = self._resolve_base(item.base_reference, context)
            if item.code.upper() in {"SENIORITY", "ANTIGUEDAD"}:
                return round(base * item.rate * context.get("SENIORITY_YEARS", 0) / 100, 2)
            return round(base * item.rate / 100, 2)
        if item.amount is not None:
            amount = item.amount
            return round(amount, 2)
        return 0.0

    def _event_adjustments(self, agreement: Agreement, basic: float, events: list[Event]) -> list[PayrollDetail]:
        details = []
        for event in events:
            for rule in agreement.event_rules:
                same_type = rule.event_type == event.type
                same_subtype = rule.subtype is None or rule.subtype == event.subtype
                if not same_type or not same_subtype:
                    continue
                if "DISCOUNT_DAY" in rule.effects and event.days:
                    amount = round((basic / self.DAYS_PER_MONTH) * event.days, 2)
                    details.append(PayrollDetail(
                        code=f"{event.type}_{event.subtype or 'DISCOUNT'}",
                        name=event.description or "Descuento por novedad",
                        type="REMUNERATIVE",
                        amount=-amount,
                    ))
        return details

    def _resolve_base(self, base_reference: str, context: dict[str, float]) -> float:
        key = self._normalize_token(base_reference)
        aliases = {
            "": "BASIC",
            "NO_INDICADO": "BASIC",
            "BASIC": "BASIC",
            "BASICO": "BASIC",
            "SUELDO_BASICO": "BASIC",
            "SALARIO_BASICO": "BASIC",
            "REMUNERATIVE_TOTAL": "REMUNERATIVE_TOTAL",
            "TOTAL_REMUNERATIVO": "REMUNERATIVE_TOTAL",
            "TOTAL_REMUNERATIVO": "REMUNERATIVE_TOTAL",
        }
        return context.get(aliases.get(key, key), context["BASIC"])

    def _is_attendance_item(self, item: SalaryItem) -> bool:
        value = f"{item.code} {item.name}".upper()
        return "PRESENTISMO" in value or "ATTENDANCE" in value or "ASISTENCIA" in value

    def _normalize_token(self, value: str) -> str:
        normalized = str(value or "").upper()
        replacements = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U", "Ñ": "N"}
        for source, target in replacements.items():
            normalized = normalized.replace(source, target)
        return re.sub(r"[^A-Z0-9]+", "_", normalized).strip("_")

    def _evaluate_formula(self, formula: str, context: dict[str, float]) -> float:
        expression = self._normalize_formula(formula, context)
        return float(self._eval_ast(ast.parse(expression, mode="eval").body))

    def _normalize_formula(self, formula: str, context: dict[str, float]) -> str:
        expression = str(formula)
        expression = re.sub(r"(\d+(?:[,.]\d+)?)\s*%", lambda match: f"({match.group(1).replace(',', '.')} / 100)", expression)
        replacements = {
            "Salario Básico": "BASIC",
            "Salario Basico": "BASIC",
            "Sueldo Básico": "BASIC",
            "Sueldo Basico": "BASIC",
            "Básico": "BASIC",
            "Basico": "BASIC",
            "Total Remunerativo": "REMUNERATIVE_TOTAL",
        }
        for label, token in replacements.items():
            expression = re.sub(re.escape(label), token, expression, flags=re.IGNORECASE)
        for token, value in sorted(context.items(), key=lambda item: len(item[0]), reverse=True):
            expression = re.sub(rf"\b{re.escape(token)}\b", str(value), expression)
        if re.search(r"[^0-9+\-*/().\s]", expression):
            return 0
        return expression

    def _eval_ast(self, node: ast.AST) -> float:
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            return operators[type(node.op)](self._eval_ast(node.left), self._eval_ast(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in operators:
            return operators[type(node.op)](self._eval_ast(node.operand))
        raise ValueError("Unsupported formula")
