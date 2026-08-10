from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.schemas.repository import RepositorySnapshot

ResultT = TypeVar("ResultT")


class Analyzer(ABC, Generic[ResultT]):
    @abstractmethod
    def analyze(self, snapshot: RepositorySnapshot) -> ResultT:
        """Return evidence-based findings from an immutable repository snapshot."""
