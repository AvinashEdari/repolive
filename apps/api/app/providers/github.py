import base64
import re
import time
from pathlib import PurePosixPath
from urllib.parse import urlsplit

import httpx

from app.core.config import Settings, get_settings
from app.providers.base import (
    InvalidRepositoryUrl,
    RepositoryConnectivityError,
    RepositoryNotFoundError,
    RepositoryProvider,
    RepositoryProviderError,
    RepositoryRateLimitError,
    RepositoryTooLargeError,
)
from app.schemas.product import DiscoveryItem
from app.schemas.repository import (
    RepositoryFile,
    RepositoryMetadata,
    RepositoryReference,
    RepositorySnapshot,
)

_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")
_EVIDENCE_NAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "pipfile",
    "gemfile",
    "composer.json",
    "cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "gradle.properties",
    "global.json",
    ".nvmrc",
    ".node-version",
    ".python-version",
    ".ruby-version",
    ".tool-versions",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    ".env.example",
    "makefile",
}


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
        if (
            owner in {".", ".."}
            or name in {".", ".."}
            or not owner
            or not name
            or not _SEGMENT.fullmatch(owner)
            or not _SEGMENT.fullmatch(name)
        ):
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
            base_url="https://api.github.com",
            headers=headers,
            timeout=self.settings.github_request_timeout_seconds,
        )
        try:
            metadata_response = await client.get(f"/repos/{repository.owner}/{repository.name}")
            self._raise_for_status(metadata_response)
            metadata_payload = metadata_response.json()
            if not isinstance(metadata_payload, dict):
                raise RepositoryProviderError("GitHub returned invalid repository metadata.")
            default_branch = str(metadata_payload["default_branch"])

            commit_response = await client.get(
                f"/repos/{repository.owner}/{repository.name}/commits/{default_branch}"
            )
            self._raise_for_status(commit_response)
            commit_payload = commit_response.json()
            if not isinstance(commit_payload, dict) or not isinstance(
                commit_payload.get("sha"), str
            ):
                raise RepositoryProviderError("GitHub returned invalid commit metadata.")
            commit_sha = commit_payload["sha"]

            tree_response = await client.get(
                f"/repos/{repository.owner}/{repository.name}/git/trees/{default_branch}",
                params={"recursive": "1"},
            )
            self._raise_for_status(tree_response)
            tree_payload = tree_response.json()
            if not isinstance(tree_payload, dict) or not isinstance(tree_payload.get("tree"), list):
                raise RepositoryProviderError("GitHub returned an invalid repository tree.")
            if tree_payload.get("truncated"):
                raise RepositoryTooLargeError(
                    "Repository tree exceeds GitHub's safe recursive response limit."
                )

            files = []
            for item in tree_payload["tree"]:
                if (
                    not isinstance(item, dict)
                    or item.get("type") != "blob"
                    or item.get("mode") == "120000"
                    or not isinstance(item.get("path"), str)
                ):
                    continue
                path = item["path"]
                if (
                    len(path.encode("utf-8")) > self.settings.max_repository_path_bytes
                    or any(ord(character) < 32 or ord(character) == 127 for character in path)
                    or PurePosixPath(path).is_absolute()
                    or ".." in PurePosixPath(path).parts
                ):
                    raise RepositoryProviderError("GitHub returned an unsafe repository path.")
                files.append(
                    RepositoryFile(
                        path=path,
                        size_bytes=item.get("size"),
                        content_id=item.get("sha"),
                    )
                )
            if len(files) > self.settings.max_repository_files:
                raise RepositoryTooLargeError("Repository exceeds the configured file limit.")
            known_bytes = sum(item.size_bytes or 0 for item in files)
            if known_bytes > self.settings.max_repository_bytes:
                raise RepositoryTooLargeError("Repository exceeds the configured size limit.")

            ingestion_warnings = await self._hydrate_evidence_files(client, repository, files)

            license_data = metadata_payload.get("license") or {}
            return RepositorySnapshot(
                repository=repository,
                metadata=RepositoryMetadata(
                    commit_sha=commit_sha,
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
                ingestion_warnings=ingestion_warnings,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RepositoryProviderError(
                "GitHub returned an invalid repository response."
            ) from exc
        except httpx.RequestError as exc:
            raise RepositoryConnectivityError("GitHub could not be reached.") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def search_repositories(self, query: str, limit: int) -> list[DiscoveryItem]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "RepoLive/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=headers,
            timeout=self.settings.github_request_timeout_seconds,
        )
        try:
            response = await client.get(
                "/search/repositories",
                params={"q": query, "per_page": limit, "sort": "updated", "order": "desc"},
            )
            self._raise_for_status(response)
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise RepositoryProviderError("GitHub returned an invalid search response.")
            items = []
            for raw in payload["items"][:limit]:
                parsed = self._discovery_item(raw, query)
                if parsed is not None:
                    items.append(parsed)
            return sorted(items, key=lambda item: (-item.score, item.full_name.lower()))
        except (TypeError, ValueError) as exc:
            raise RepositoryProviderError("GitHub returned an invalid search response.") from exc
        except httpx.RequestError as exc:
            raise RepositoryConnectivityError("GitHub could not be reached.") from exc
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    def _discovery_item(raw: object, query: str) -> DiscoveryItem | None:
        if not isinstance(raw, dict) or not isinstance(raw.get("full_name"), str):
            return None
        full_name = raw["full_name"]
        parts = full_name.split("/")
        if len(parts) != 2 or any(not _SEGMENT.fullmatch(part) for part in parts):
            return None
        topics = [item for item in raw.get("topics", []) if isinstance(item, str)][:20]
        stars = raw.get("stargazers_count", 0)
        if not isinstance(stars, int) or stars < 0:
            stars = 0
        license_payload = raw.get("license")
        license_data: dict[str, object] = (
            license_payload if isinstance(license_payload, dict) else {}
        )
        reasons, score = GitHubRepositoryProvider._rank_search_item(raw, query, topics, stars)
        license_spdx = license_data.get("spdx_id")
        return DiscoveryItem(
            full_name=full_name,
            url=f"https://github.com/{full_name}",
            description=raw.get("description") if isinstance(raw.get("description"), str) else None,
            primary_language=raw.get("language") if isinstance(raw.get("language"), str) else None,
            topics=topics,
            stars=stars,
            updated_at=raw.get("updated_at"),
            license_spdx=license_spdx if isinstance(license_spdx, str) else None,
            score=score,
            ranking_reasons=reasons,
        )

    @staticmethod
    def _rank_search_item(
        raw: dict[str, object], query: str, topics: list[str], stars: int
    ) -> tuple[list[str], int]:
        score = 25
        reasons = ["Matched the bounded GitHub search query (+25)."]
        terms = {part.lower() for part in re.findall(r"[A-Za-z0-9_.+-]+", query) if ":" not in part}
        searchable = " ".join(
            value.lower()
            for value in (raw.get("name"), raw.get("description"))
            if isinstance(value, str)
        )
        topic_matches = terms.intersection(item.lower() for item in topics)
        if terms and any(term in searchable for term in terms):
            score += 20
            reasons.append("Name or description matches the requested terms (+20).")
        if topic_matches:
            score += 15
            reasons.append("Repository topics match the request (+15).")
        if raw.get("license"):
            score += 10
            reasons.append("A license is declared (+10).")
        if raw.get("archived") is False:
            score += 10
            reasons.append("Repository is not archived (+10).")
        if stars:
            star_points = min(10, len(str(stars)) * 2)
            score += star_points
            reasons.append(
                f"Community signal contributes a capped +{star_points}; stars do not dominate."
            )
        if raw.get("fork") is True:
            score -= 10
            reasons.append("Fork status reduces the score (-10).")
        return reasons, min(max(score, 0), 100)

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 404:
            raise RepositoryNotFoundError("Repository was not found or is not public.")
        if response.status_code in {403, 429}:
            retry_after = GitHubRepositoryProvider._retry_after(response)
            raise RepositoryRateLimitError(
                "GitHub rate limit or access policy blocked the request.", retry_after
            )
        if response.is_error:
            raise RepositoryProviderError("GitHub returned an unexpected error.")

    async def _hydrate_evidence_files(
        self,
        client: httpx.AsyncClient,
        repository: RepositoryReference,
        files: list[RepositoryFile],
    ) -> list[str]:
        warnings: list[str] = []
        eligible = [file for file in files if self._is_evidence_file(file)]
        if len(eligible) > self.settings.max_evidence_files:
            warnings.append(
                "Some evidence files were skipped because the file-count limit was reached."
            )
            eligible = eligible[: self.settings.max_evidence_files]

        total_bytes = 0
        for file in eligible:
            if not file.content_id:
                continue
            response = await client.get(
                f"/repos/{repository.owner}/{repository.name}/git/blobs/{file.content_id}"
            )
            if response.status_code == 404:
                warnings.append(f"Evidence content was unavailable: {file.path}")
                continue
            self._raise_for_status(response)
            payload = response.json()
            if (
                not isinstance(payload, dict)
                or payload.get("encoding") != "base64"
                or not isinstance(payload.get("content"), str)
            ):
                raise RepositoryProviderError("GitHub returned an invalid evidence file.")
            try:
                encoded = "".join(payload["content"].split())
                if len(encoded) > ((self.settings.max_evidence_file_bytes + 2) // 3) * 4:
                    warnings.append(f"Oversized evidence was skipped: {file.path}")
                    continue
                raw = base64.b64decode(encoded, validate=True)
            except ValueError as exc:
                raise RepositoryProviderError("GitHub returned invalid base64 evidence.") from exc
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                warnings.append(f"Non-UTF-8 evidence was skipped: {file.path}")
                continue
            if len(raw) > self.settings.max_evidence_file_bytes:
                warnings.append(f"Oversized evidence was skipped: {file.path}")
                continue
            total_bytes += len(raw)
            if total_bytes > self.settings.max_evidence_total_bytes:
                warnings.append(
                    "Some evidence files were skipped because the byte limit was reached."
                )
                break
            file.text_content = text
        return warnings

    @staticmethod
    def _retry_after(response: httpx.Response) -> int | None:
        retry_after = response.headers.get("retry-after")
        if retry_after and retry_after.isdigit():
            return min(max(int(retry_after), 1), 3600)
        reset = response.headers.get("x-ratelimit-reset")
        if reset and reset.isdigit():
            return min(max(int(reset) - int(time.time()), 1), 3600)
        return None

    def _is_evidence_file(self, file: RepositoryFile) -> bool:
        if file.size_bytes is not None and file.size_bytes > self.settings.max_evidence_file_bytes:
            return False
        path = PurePosixPath(file.path)
        name = path.name.lower()
        return (
            name in _EVIDENCE_NAMES
            or name.endswith((".csproj", ".fsproj", ".vbproj"))
            or name == "readme"
            or name.startswith("readme.")
            or file.path.lower().startswith(".github/workflows/")
        )
