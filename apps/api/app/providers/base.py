from abc import ABC, abstractmethod

from app.schemas.repository import RepositoryReference, RepositorySnapshot


class InvalidRepositoryUrl(ValueError):
    """Raised when a repository URL is unsupported or malformed."""


class RepositoryProviderError(RuntimeError):
    """Raised when a provider cannot safely retrieve repository data."""


class RepositoryProvider(ABC):
    @abstractmethod
    def parse_url(self, url: str) -> RepositoryReference:
        """Validate a URL and return a provider-neutral repository reference."""

    @abstractmethod
    async def fetch_snapshot(self, repository: RepositoryReference) -> RepositorySnapshot:
        """Retrieve bounded metadata and file-tree facts without executing repository code."""
