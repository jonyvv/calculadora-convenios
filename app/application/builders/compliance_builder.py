from app.domain.entities.agreement import AuditRule


class ComplianceBuilder:
    def build_audit_rules(self, raw: dict) -> list[AuditRule]:
        rules = []
        for rule in raw.get("raw_compliance_rules") or []:
            rules.append(AuditRule(rule=rule.get("rule") or rule.get("description") or str(rule)))
        return rules
