from app.domain.entities.audit_report import AuditReport
from app.infrastructure.ai.audit_agent import AuditAgent


class AuditService:
    def __init__(self, audit_agent: AuditAgent):
        self.audit_agent = audit_agent

    def audit(self, context: dict) -> AuditReport:
        return AuditReport.model_validate(self.audit_agent.audit(context))
