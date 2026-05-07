from abc import ABC, abstractmethod

from app.domain.entities.agreement import Agreement


class AgreementRepository(ABC):
    @abstractmethod
    def save_version(self, agreement: Agreement) -> Agreement:
        raise NotImplementedError

    @abstractmethod
    def list(self) -> list[Agreement]:
        raise NotImplementedError

    @abstractmethod
    def get(self, agreement_id: str, version: str | None = None) -> Agreement:
        raise NotImplementedError

    @abstractmethod
    def activate(self, agreement_id: str, version: str) -> Agreement:
        raise NotImplementedError

    @abstractmethod
    def get_active(self, agreement_id: str) -> Agreement:
        raise NotImplementedError

    @abstractmethod
    def delete(self, agreement_id: str, version: str | None = None) -> None:
        raise NotImplementedError
