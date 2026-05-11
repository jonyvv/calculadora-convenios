from app.domain.entities.audit_report import AuditReport
from app.infrastructure.ai.audit_agent import AuditAgent


class AuditService:
    def __init__(self, audit_agent: AuditAgent):
        self.audit_agent = audit_agent

    def audit(self, context: dict) -> AuditReport:
        return AuditReport.model_validate(self._normalize(self.audit_agent.audit(context)))

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
