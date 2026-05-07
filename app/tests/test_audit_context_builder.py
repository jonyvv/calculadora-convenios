from app.application.builders.audit_context_builder import AuditContextBuilder
from app.domain.rules.payroll_engine import PayrollEngine


def test_builds_audit_context_without_source_documents(agreement, employee, monthly_event):
    payroll = PayrollEngine().calculate(agreement, employee, monthly_event)
    context = AuditContextBuilder().build(agreement, employee, monthly_event, payroll)

    assert set(context.keys()) == {"agreement", "employee", "events", "payroll"}
    assert context["employee"]["employee_id"] == "E1"
    assert isinstance(context["events"], list)
