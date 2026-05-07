from pydantic import BaseModel


class AgreementUploadResponse(BaseModel):
    agreement: dict
    warnings: list[str]


class ActivateAgreementRequest(BaseModel):
    version: str
