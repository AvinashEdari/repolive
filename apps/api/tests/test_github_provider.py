import pytest

from app.providers.base import InvalidRepositoryUrl
from app.providers.github import GitHubRepositoryProvider

provider = GitHubRepositoryProvider()


@pytest.mark.parametrize(
    ("url", "owner", "name"),
    [
        ("https://github.com/fastapi/fastapi", "fastapi", "fastapi"),
        ("https://www.github.com/openai/openai-python.git", "openai", "openai-python"),
    ],
)
def test_parse_valid_url(url: str, owner: str, name: str) -> None:
    result = provider.parse_url(url)
    assert (result.owner, result.name) == (owner, name)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a/b",
        "https://gitlab.com/a/b",
        "https://github.com/a/b/issues",
        "https://user:secret@github.com/a/b",
        "https://github.com/a/b?tab=readme",
        "https://github.com/a/%2e%2e",
    ],
)
def test_rejects_unsafe_or_unsupported_url(url: str) -> None:
    with pytest.raises(InvalidRepositoryUrl):
        provider.parse_url(url)

