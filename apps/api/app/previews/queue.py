from abc import ABC, abstractmethod
from typing import Protocol


class ClaimStore(Protocol):
    def claim(self, worker_id: str) -> dict[str, object] | None: ...


class PreviewQueue(ABC):
    @abstractmethod
    def claim(self, worker_id: str) -> dict[str, object] | None: ...


class DatabasePreviewQueue(PreviewQueue):
    def __init__(self, store: ClaimStore) -> None:
        self.store = store

    def claim(self, worker_id: str) -> dict[str, object] | None:
        return self.store.claim(worker_id)
