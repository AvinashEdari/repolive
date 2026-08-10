import re
from urllib.parse import urlsplit

import httpx

from app.core.config import Settings, get_settings
from app.providers.base import InvalidRepositoryUrl, RepositoryProvider, RepositoryProviderError
from app.schemas.repository import (
    RepositoryFile,
    RepositoryMetadata,
    RepositoryReference,
    RepositorySnapshot,
)

_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")


class GitHubRepositoryProvider(RepositoryProvider):
    def __init__(
        self, settings: Settings | None = None, client: httpx.AsyncClient | None = None
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client

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

    async def fetch_snapshot(self, repository: RepositoryReference) -> RepositorySnapshot:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "RepoLive/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"

        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(
            base_url="https://api.github.com", headers=headers, timeout=15.0
        )
        try:
            metadata_response = await client.get(f"/repos/{repository.owner}/{repository.name}")
            self._raise_for_status(metadata_response)
            metadata_payload = metadata_response.json()
            default_branch = str(metadata_payload["default_branch"])

            tree_response = await client.get(
                f"/repos/{repository.owner}/{repository.name}/git/trees/{default_branch}",
                params={"recursive": "1"},
            )
            self._raise_for_status(tree_response)
            tree_payload = tree_response.json()
            if tree_payload.get("truncated"):
                raise RepositoryProviderError(
                    "Repository tree exceeds GitHub's safe recursive response limit."
                )

            files = [
                RepositoryFile(path=item["path"], size_bytes=item.get("size"))
                for item in tree_payload.get("tree", [])
                if item.get("type") == "blob" and isinstance(item.get("path"), str)
            ]
            if len(files) > self.settings.max_repository_files:
                raise RepositoryProviderError("Repository exceeds the configured file limit.")
            known_bytes = sum(item.size_bytes or 0 for item in files)
            if known_bytes > self.settings.max_repository_bytes:
                raise RepositoryProviderError("Repository exceeds the configured size limit.")

            license_data = metadata_payload.get("license") or {}
            return RepositorySnapshot(
                repository=repository,
                metadata=RepositoryMetadata(
                    description=metadata_payload.get("description"),
                    default_branch=default_branch,
                    stars=metadata_payload.get("stargazers_count", 0),
                    forks=metadata_payload.get("forks_count", 0),
                    open_issues=metadata_payload.get("open_issues_count", 0),
                    size_kib=metadata_payload.get("size", 0),
                    archived=metadata_payload.get("archived", False),
                    license_spdx=license_data.get("spdx_id"),
                    primary_language=metadata_payload.get("language"),
                    last_pushed_at=metadata_payload.get("pushed_at"),
                ),
                files=files,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RepositoryProviderError(
                "GitHub returned an invalid repository response."
            ) from exc
        except httpx.RequestError as exc:
            raise RepositoryProviderError("GitHub could not be reached.") from exc
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 404:
            raise RepositoryProviderError("Repository was not found or is not public.")
        if response.status_code == 403:
            raise RepositoryProviderError("GitHub rate limit or access policy blocked the request.")
        if response.is_error:
            raise RepositoryProviderError("GitHub returned an unexpected error.")
