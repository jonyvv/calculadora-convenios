from pydantic import BaseModel, Field


class AuditIssue(BaseModel):
    severity: str
    message: str
    code: str | None = None


class AuditReport(BaseModel):
    status: str
    issues: list[AuditIssue] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
