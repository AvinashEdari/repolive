from abc import ABC, abstractmethod

from app.schemas.repository import RepositoryReference


class InvalidRepositoryUrl(ValueError):
    """Raised when a repository URL is unsupported or malformed."""


class RepositoryProvider(ABC):
    @abstractmethod
    def parse_url(self, url: str) -> RepositoryReference:
        """Validate a URL and return a provider-neutral repository reference."""

