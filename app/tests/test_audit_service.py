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


class FalseSeniorityWarningAgent:
    def audit(self, context: dict) -> dict:
        return {
            "status": "WARNING",
            "issues": [
                {
                    "severity": "WARNING",
                    "code": "ANTIGUEDAD_DIFERENCIA",
                    "message": "El importe de antiguedad liquidado (32718.39) no coincide con el 3% del basico (32718.39) esperado para 3 anios de antiguedad segun la regla del 1% anual.",
                }
            ],
            "recommendations": ["Verificar si el calculo de antiguedad aplicado corresponde."],
        }


def test_audit_service_discards_false_seniority_warning_when_amount_matches():
    context = {
        "agreement": {
            "categories": [{"category_id": "A", "basic_salary": 1090613}],
            "salary_model": {
                "remunerative_items": [
                    {"code": "ANTIGUEDAD", "name": "Antiguedad", "rate": 1},
                ],
                "non_remunerative_items": [],
            },
        },
        "employee": {"category_id": "A", "seniority_years": 3},
        "payroll": {
            "details": [
                {"code": "BASIC", "name": "Basico", "amount": 1090613},
                {"code": "ANTIGUEDAD", "name": "Antiguedad", "amount": 32718.39},
            ],
        },
    }

    report = AuditService(FalseSeniorityWarningAgent()).audit(context)

    assert report.status == "APPROVED"
    assert report.issues == []
    assert report.recommendations == []
