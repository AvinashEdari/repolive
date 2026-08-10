import re
from urllib.parse import urlsplit

from app.providers.base import InvalidRepositoryUrl, RepositoryProvider
from app.schemas.repository import RepositoryReference

_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")


class GitHubRepositoryProvider(RepositoryProvider):
    def parse_url(self, url: str) -> RepositoryReference:
        candidate = url.strip()
        try:
            parsed = urlsplit(candidate)
        except ValueError as exc:
            raise InvalidRepositoryUrl("Invalid repository URL.") from exc

        if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
            raise InvalidRepositoryUrl("Use an HTTPS github.com repository URL.")
        if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
            raise InvalidRepositoryUrl(
                "Repository URL must not include credentials, ports, or extras."
            )

        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 2:
            raise InvalidRepositoryUrl("URL must identify one GitHub owner and repository.")
        owner, name = parts
        if name.endswith(".git"):
            name = name[:-4]
        if not owner or not name or not _SEGMENT.fullmatch(owner) or not _SEGMENT.fullmatch(name):
            raise InvalidRepositoryUrl("GitHub owner or repository name is invalid.")

        return RepositoryReference(
            owner=owner,
            name=name,
            canonical_url=f"https://github.com/{owner}/{name}",
        )
