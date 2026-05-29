from app.domain.entities.audit_report import AuditReport
from app.infrastructure.ai.audit_agent import AuditAgent


class AuditService:
    def __init__(self, audit_agent: AuditAgent):
        self.audit_agent = audit_agent

    def audit(self, context: dict) -> AuditReport:
        normalized = self._normalize(self.audit_agent.audit(context))
        normalized = self._discard_false_seniority_warnings(normalized, context)
        return AuditReport.model_validate(normalized)

    def _normalize(self, raw: dict) -> dict:
        issues = []
        for index, issue in enumerate(raw.get("issues") or [], start=1):
            if isinstance(issue, str):
                issues.append({"severity": raw.get("status") or "WARNING", "message": issue, "code": f"GEMINI_ISSUE_{index}"})
            elif isinstance(issue, dict):
                issues.append({
                    "severity": issue.get("severity") or raw.get("status") or "WARNING",
                    "message": issue.get("message") or issue.get("description") or str(issue),
                    "code": issue.get("code"),
                })
            else:
                issues.append({"severity": raw.get("status") or "WARNING", "message": str(issue), "code": f"GEMINI_ISSUE_{index}"})

        recommendations = [
            item if isinstance(item, str) else str(item)
            for item in (raw.get("recommendations") or [])
        ]

        return {
            "status": raw.get("status") or ("WARNING" if issues else "APPROVED"),
            "issues": issues,
            "recommendations": recommendations,
        }

    def _discard_false_seniority_warnings(self, normalized: dict, context: dict) -> dict:
        issues = [
            issue
            for issue in normalized["issues"]
            if not self._is_false_seniority_warning(issue, context)
        ]
        if len(issues) == len(normalized["issues"]):
            return normalized
        return {
            **normalized,
            "status": "APPROVED" if not issues else normalized["status"],
            "issues": issues,
            "recommendations": normalized["recommendations"] if issues else [],
        }

    def _is_false_seniority_warning(self, issue: dict, context: dict) -> bool:
        message = str(issue.get("message") or "").upper()
        if "ANTIG" not in message or "NO COINCIDE" not in message:
            return False

        actual = self._seniority_detail_amount(context)
        expected = self._expected_seniority_amount(context)
        if actual is None or expected is None:
            return False
        return abs(actual - expected) <= 0.05

    def _seniority_detail_amount(self, context: dict) -> float | None:
        for detail in context.get("payroll", {}).get("details", []):
            value = f"{detail.get('code', '')} {detail.get('name', '')}".upper()
            if "ANTIG" in value or "SENIORITY" in value:
                return float(detail.get("amount") or 0)
        return None

    def _expected_seniority_amount(self, context: dict) -> float | None:
        employee = context.get("employee", {})
        years = float(employee.get("seniority_years") or 0)
        if years <= 0:
            return 0

        basic = self._employee_basic_salary(context)
        rate = self._seniority_rate(context)
        if basic is None or rate is None:
            return None
        return round(basic * rate / 100 * years, 2)

    def _employee_basic_salary(self, context: dict) -> float | None:
        employee = context.get("employee", {})
        category_id = employee.get("category_id")
        for category in context.get("agreement", {}).get("categories", []):
            if category.get("category_id") == category_id:
                return float(category.get("basic_salary") or 0)
        for detail in context.get("payroll", {}).get("details", []):
            if detail.get("code") == "BASIC":
                return float(detail.get("amount") or 0)
        return None

    def _seniority_rate(self, context: dict) -> float | None:
        salary_model = context.get("agreement", {}).get("salary_model", {})
        items = salary_model.get("remunerative_items", []) + salary_model.get("non_remunerative_items", [])
        for item in items:
            value = f"{item.get('code', '')} {item.get('name', '')}".upper()
            if "ANTIG" in value or "SENIORITY" in value:
                rate = item.get("rate")
                return float(rate) if rate is not None else None
        return None
