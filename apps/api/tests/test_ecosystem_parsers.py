import pytest

from app.analysis.dependencies import DependencyAnalyzer, RuntimeAnalyzer
from app.schemas.repository import (
    RepositoryFile,
    RepositoryMetadata,
    RepositoryReference,
    RepositorySnapshot,
)


def snapshot(path: str, content: str) -> RepositorySnapshot:
    return RepositorySnapshot(
        repository=RepositoryReference(
            owner="a", name="b", canonical_url="https://github.com/a/b"
        ),
        metadata=RepositoryMetadata(
            description=None,
            default_branch="main",
            stars=0,
            forks=0,
            open_issues=0,
            size_kib=1,
            archived=False,
            license_spdx=None,
            primary_language=None,
            last_pushed_at=None,
        ),
        files=[RepositoryFile(path=path, text_content=content)],
    )


@pytest.mark.parametrize(
    ("path", "content", "expected_name", "ecosystem"),
    [
        ("Cargo.toml", '[dependencies]\nserde = "1"', "serde", "Cargo"),
        ("go.mod", "module x\nrequire github.com/a/b v1.2.3", "github.com/a/b", "Go"),
        (
            "pom.xml",
            "<project><dependencies><dependency><groupId>org.example</groupId>"
            "<artifactId>core</artifactId><version>1</version></dependency></dependencies></project>",
            "org.example:core",
            "Maven",
        ),
        (
            "build.gradle",
            "dependencies {\n implementation 'org.example:core:2.0'\n}",
            "org.example:core",
            "Gradle",
        ),
        ("Gemfile", "gem 'rails', '~> 8.0'", "rails", "RubyGems"),
        (
            "composer.json",
            '{"require":{"laravel/framework":"^12"}}',
            "laravel/framework",
            "Composer",
        ),
        (
            "App.csproj",
            '<Project><ItemGroup><PackageReference Include="Serilog" Version="4.0" />'
            "</ItemGroup></Project>",
            "Serilog",
            "NuGet",
        ),
    ],
)
def test_supported_manifest_parsers(
    path: str, content: str, expected_name: str, ecosystem: str
) -> None:
    findings = DependencyAnalyzer().analyze(snapshot(path, content))
    assert [(item.name, item.ecosystem) for item in findings] == [(expected_name, ecosystem)]


@pytest.mark.parametrize(
    ("path", "content", "runtime", "constraint"),
    [
        ("Cargo.toml", '[package]\nrust-version = "1.85"', "Rust", "1.85"),
        ("Gemfile", "ruby '3.4'", "Ruby", "3.4"),
        ("composer.json", '{"require":{"php":"^8.4"}}', "PHP", "^8.4"),
        (
            "App.csproj",
            "<Project><PropertyGroup><TargetFramework>net9.0</TargetFramework>"
            "</PropertyGroup></Project>",
            ".NET",
            "net9.0",
        ),
    ],
)
def test_supported_runtime_parsers(
    path: str, content: str, runtime: str, constraint: str
) -> None:
    findings = RuntimeAnalyzer().analyze(snapshot(path, content))
    assert [(item.runtime, item.version_constraint) for item in findings] == [
        (runtime, constraint)
    ]


@pytest.mark.parametrize(
    ("path", "content"),
    [
        ("Cargo.toml", "not = [valid"),
        ("composer.json", "{"),
        ("pom.xml", "<project>"),
        ("App.csproj", "<Project>"),
    ],
)
def test_malformed_manifests_do_not_create_findings(path: str, content: str) -> None:
    assert DependencyAnalyzer().analyze(snapshot(path, content)) == []
