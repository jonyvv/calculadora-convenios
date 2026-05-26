import ast
import operator
import re
from typing import Any


class FormulaEngine:
    """Evaluates arithmetic formulas declared by an Agreement.

    Supported canonical variables include BASE_SALARY, YEARS, MONTHLY_HOURS and
    MULTIPLIER. The engine also accepts common aliases generated from Spanish
    source text so the payroll engine does not need convention-specific code.
    """

    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    TEXT_ALIASES = {
        "Salario Basico": "BASE_SALARY",
        "Sueldo Basico": "BASE_SALARY",
        "Basico": "BASE_SALARY",
        "Base Salary": "BASE_SALARY",
        "Basic": "BASE_SALARY",
        "Anios": "YEARS",
        "Anos": "YEARS",
        "Antiguedad": "YEARS",
        "Horas Mensuales": "MONTHLY_HOURS",
        "Monthly Hours": "MONTHLY_HOURS",
        "Multiplicador": "MULTIPLIER",
        "Valor Hora": "HOURLY_VALUE",
        "Valor Horario": "HOURLY_VALUE",
        "Valor Dia": "DAILY_VALUE",
        "Valor Diario": "DAILY_VALUE",
        "Total Remunerativo": "REMUNERATIVE_TOTAL",
        "Todos los conceptos remunerativos": "REMUNERATIVE_TOTAL",
        "Conceptos remunerativos": "REMUNERATIVE_TOTAL",
        "Total rubros remunerativos": "REMUNERATIVE_TOTAL",
        "Rubros remunerativos": "REMUNERATIVE_TOTAL",
        "Haberes remunerativos": "REMUNERATIVE_TOTAL",
        "Remunerativo": "REMUNERATIVE_TOTAL",
        "Total No Remunerativo": "NON_REMUNERATIVE_TOTAL",
        "Haberes no remunerativos": "NON_REMUNERATIVE_TOTAL",
        "No remunerativo": "NON_REMUNERATIVE_TOTAL",
        "Total Haberes": "GROSS_SALARY",
        "Cantidad": "QUANTITY",
        "Kilometros": "QUANTITY",
        "Kilometro": "QUANTITY",
        "Km": "QUANTITY",
        "Dias": "DAYS",
        "Horas": "HOURS",
    }

    TOKEN_ALIASES = {
        "BASIC": "BASE_SALARY",
        "BASICO": "BASE_SALARY",
        "SUELDO_BASICO": "BASE_SALARY",
        "SALARIO_BASICO": "BASE_SALARY",
        "SENIORITY_YEARS": "YEARS",
        "ANTIGUEDAD_ANIOS": "YEARS",
        "ANTIGUEDAD_ANOS": "YEARS",
        "HOURS_PER_MONTH": "MONTHLY_HOURS",
        "HORAS_MENSUALES": "MONTHLY_HOURS",
        "VALOR_HORA": "HOURLY_VALUE",
        "VALOR_HORARIO": "HOURLY_VALUE",
        "HORA_NORMAL": "HOURLY_VALUE",
        "VALOR_DIA": "DAILY_VALUE",
        "VALOR_DIARIO": "DAILY_VALUE",
        "JORNAL": "DAILY_VALUE",
        "REMUNERATIVE_TOTAL": "REMUNERATIVE_TOTAL",
        "TOTAL_REMUNERATIVO": "REMUNERATIVE_TOTAL",
        "TODOS_LOS_CONCEPTOS_REMUNERATIVOS": "REMUNERATIVE_TOTAL",
        "CONCEPTOS_REMUNERATIVOS": "REMUNERATIVE_TOTAL",
        "TOTAL_RUBROS_REMUNERATIVOS": "REMUNERATIVE_TOTAL",
        "RUBROS_REMUNERATIVOS": "REMUNERATIVE_TOTAL",
        "HABERES_REMUNERATIVOS": "REMUNERATIVE_TOTAL",
        "REMUNERATIVO": "REMUNERATIVE_TOTAL",
        "NON_REMUNERATIVE_TOTAL": "NON_REMUNERATIVE_TOTAL",
        "TOTAL_NO_REMUNERATIVO": "NON_REMUNERATIVE_TOTAL",
        "HABERES_NO_REMUNERATIVOS": "NON_REMUNERATIVE_TOTAL",
        "NO_REMUNERATIVO": "NON_REMUNERATIVE_TOTAL",
        "GROSS_SALARY": "GROSS_SALARY",
        "TOTAL_HABERES": "GROSS_SALARY",
        "CANTIDAD": "QUANTITY",
        "KILOMETROS": "QUANTITY",
        "KILOMETRO": "QUANTITY",
        "KM": "QUANTITY",
        "DIAS": "DAYS",
        "DAYS": "DAYS",
        "HORAS": "HOURS",
        "HOURS": "HOURS",
    }

    def evaluate(self, formula: str, variables: dict[str, Any]) -> float:
        expression = self.normalize(formula, variables)
        return float(self._eval_ast(ast.parse(expression, mode="eval").body))

    def normalize(self, formula: str, variables: dict[str, Any]) -> str:
        expression = self._ascii(str(formula or "0"))
        expression = re.sub(
            r"(\d+(?:[,.]\d+)?)\s*%",
            lambda match: f"({match.group(1).replace(',', '.')} / 100)",
            expression,
        )

        for label, token in self.TEXT_ALIASES.items():
            expression = re.sub(re.escape(label), token, expression, flags=re.IGNORECASE)

        normalized_variables = self._normalize_variables(variables)
        for token, value in sorted(normalized_variables.items(), key=lambda item: len(item[0]), reverse=True):
            expression = re.sub(rf"\b{re.escape(token)}\b", str(float(value or 0)), expression)

        if re.search(r"[^0-9+\-*/().\s]", expression):
            raise ValueError(f"Unsupported formula token in: {formula}")
        return expression or "0"

    def canonical_token(self, value: str | None) -> str:
        token = re.sub(r"[^A-Z0-9]+", "_", self._ascii(str(value or "")).upper()).strip("_")
        return self.TOKEN_ALIASES.get(token, token)

    def _normalize_variables(self, variables: dict[str, Any]) -> dict[str, float]:
        normalized = {}
        for key, value in variables.items():
            raw_token = re.sub(r"[^A-Z0-9]+", "_", self._ascii(str(key or "")).upper()).strip("_")
            normalized[raw_token] = float(value or 0)
            normalized[self.canonical_token(key)] = float(value or 0)
        return normalized

    def _eval_ast(self, node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in self.OPERATORS:
            return self.OPERATORS[type(node.op)](self._eval_ast(node.left), self._eval_ast(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in self.OPERATORS:
            return self.OPERATORS[type(node.op)](self._eval_ast(node.operand))
        raise ValueError("Unsupported formula")

    def _ascii(self, value: str) -> str:
        replacements = {
            "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n",
            "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U", "Ñ": "N",
            "Ã¡": "a", "Ã©": "e", "Ã­": "i", "Ã³": "o", "Ãº": "u", "Ã¼": "u", "Ã±": "n",
            "Ã": "A", "Ã‰": "E", "Ã": "I", "Ã“": "O", "Ãš": "U", "Ãœ": "U", "Ã‘": "N",
        }
        for source, target in replacements.items():
            value = value.replace(source, target)
        return value
