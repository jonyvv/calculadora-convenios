from abc import ABC, abstractmethod


class DocumentParser(ABC):
    @abstractmethod
    def parse(self, content: bytes) -> str:
        raise NotImplementedError
