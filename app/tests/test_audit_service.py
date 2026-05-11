from app.application.services.audit_service import AuditService


class StringIssueAuditAgent:
    def audit(self, context: dict) -> dict:
        return {
            "status": "WARNING",
            "issues": [
                "Duplication of concepts: the same additional appears twice.",
                {"message": "Deduction base mismatch"},
            ],
            "recommendations": [{"action": "review agreement"}],
        }


def test_audit_service_normalizes_gemini_string_issues():
    report = AuditService(StringIssueAuditAgent()).audit({})

    assert report.status == "WARNING"
    assert report.issues[0].severity == "WARNING"
    assert report.issues[0].message.startswith("Duplication")
    assert report.issues[0].code == "GEMINI_ISSUE_1"
    assert report.issues[1].message == "Deduction base mismatch"
    assert report.recommendations == ["{'action': 'review agreement'}"]
