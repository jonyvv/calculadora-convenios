from app.infrastructure.ai.gemini_client import GeminiClient


class AuditAgent:
    def __init__(self, client: GeminiClient):
        self.client = client

    def audit(self, context: dict) -> dict:
        prompt = f"""
Sos un Audit Agent de liquidaciones argentinas.
Consumis SOLO JSON estructurado. No recalcules importes, no modifiques datos,
no reinterpretas PDFs. Audita conceptos remunerativos, no remunerativos,
presentismo, antiguedad, horas extra, descuentos y reglas fiscales.
Devolve SOLO JSON: status APPROVED|WARNING|ERROR, issues, recommendations.
Contexto:
{context}
"""
        return self.client.generate_json(prompt)


class MockAuditAgent(AuditAgent):
    def __init__(self):
        pass

    def audit(self, context: dict) -> dict:
        issues = []
        payroll_codes = {detail["code"] for detail in context["payroll"]["details"]}
        if "BASIC" not in payroll_codes:
            issues.append({"severity": "ERROR", "message": "Falta sueldo basico", "code": "MISSING_BASIC"})
        return {
            "status": "ERROR" if issues else "APPROVED",
            "issues": issues,
            "recommendations": [] if not issues else ["Revisar metamodelo de conceptos obligatorios"],
        }
