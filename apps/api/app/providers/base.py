from abc import ABC, abstractmethod

from app.schemas.repository import RepositoryReference, RepositorySnapshot


class InvalidRepositoryUrl(ValueError):
    """Raised when a repository URL is unsupported or malformed."""


class RepositoryProviderError(RuntimeError):
    """Raised when a provider cannot safely retrieve repository data."""


class RepositoryNotFoundError(RepositoryProviderError):
    """Raised when a repository is unavailable to the configured provider."""


class RepositoryRateLimitError(RepositoryProviderError):
    """Raised when provider rate or access policy blocks retrieval."""

    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class RepositoryTooLargeError(RepositoryProviderError):
    """Raised when configured ingestion limits are exceeded."""


class RepositoryConnectivityError(RepositoryProviderError):
    """Raised when the provider cannot be reached within configured timeouts."""


class RepositoryProvider(ABC):
    @abstractmethod
    def parse_url(self, url: str) -> RepositoryReference:
        """Validate a URL and return a provider-neutral repository reference."""

    @abstractmethod
    async def fetch_snapshot(self, repository: RepositoryReference) -> RepositorySnapshot:
        """Retrieve bounded metadata and file-tree facts without executing repository code."""
