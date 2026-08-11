import json
import re
import tomllib
import xml.etree.ElementTree as ET

from app.schemas.analysis import DependencyFinding, DependencyScope, RuntimeFinding
from app.schemas.repository import RepositoryFile


def parse_cargo(file: RepositoryFile) -> list[DependencyFinding]:
    try:
        payload = tomllib.loads(file.text_content or "")
    except tomllib.TOMLDecodeError:
        return []
    findings = []
    sections: dict[str, DependencyScope] = {
        "dependencies": "runtime",
        "dev-dependencies": "development",
        "build-dependencies": "development",
    }
    for section, scope in sections.items():
        values = payload.get(section, {})
        if not isinstance(values, dict):
            continue
        for name, declaration in values.items():
            constraint = declaration if isinstance(declaration, str) else None
            if isinstance(declaration, dict) and isinstance(declaration.get("version"), str):
                constraint = declaration["version"]
            findings.append(_dependency(name, constraint, scope, "Cargo", file.path))
    return findings


def parse_go_mod(file: RepositoryFile) -> list[DependencyFinding]:
    content = file.text_content or ""
    findings = []
    in_block = False
    for raw_line in content.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if line == "require (":
            in_block = True
            continue
        if in_block and line == ")":
            in_block = False
            continue
        if line.startswith("require "):
            line = line.removeprefix("require ").strip()
        elif not in_block:
            continue
        parts = line.split()
        if len(parts) >= 2:
            findings.append(_dependency(parts[0], parts[1], "runtime", "Go", file.path))
    return findings


def parse_maven(file: RepositoryFile) -> list[DependencyFinding]:
    root = _xml_root(file)
    if root is None:
        return []
    findings = []
    for node in root.findall(".//{*}dependencies/{*}dependency"):
        group = node.findtext("{*}groupId")
        artifact = node.findtext("{*}artifactId")
        if not artifact:
            continue
        scope_text = node.findtext("{*}scope")
        scope: DependencyScope = "development" if scope_text == "test" else "runtime"
        optional = node.findtext("{*}optional") == "true"
        findings.append(
            _dependency(
                f"{group}:{artifact}" if group else artifact,
                node.findtext("{*}version"),
                "optional" if optional else scope,
                "Maven",
                file.path,
            )
        )
    return findings


def parse_gradle(file: RepositoryFile) -> list[DependencyFinding]:
    pattern = re.compile(
        r"(?m)^\s*(implementation|api|compileOnly|runtimeOnly|testImplementation)"
        r"\s*\(?\s*['\"]([^'\"]+)['\"]"
    )
    findings = []
    for configuration, declaration in pattern.findall(file.text_content or ""):
        parts = declaration.split(":")
        if len(parts) < 2:
            continue
        scope: DependencyScope = "development" if configuration.startswith("test") else "runtime"
        findings.append(
            _dependency(
                ":".join(parts[:2]),
                parts[2] if len(parts) > 2 else None,
                scope,
                "Gradle",
                file.path,
            )
        )
    return findings


def parse_gemfile(file: RepositoryFile) -> list[DependencyFinding]:
    pattern = re.compile(r"(?m)^\s*gem\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?")
    return [
        _dependency(name, constraint or None, "runtime", "RubyGems", file.path)
        for name, constraint in pattern.findall(file.text_content or "")
    ]


def parse_composer(file: RepositoryFile) -> list[DependencyFinding]:
    try:
        payload = json.loads(file.text_content or "")
    except json.JSONDecodeError:
        return []
    findings = []
    sections: dict[str, DependencyScope] = {
        "require": "runtime",
        "require-dev": "development",
    }
    for section, scope in sections.items():
        values = payload.get(section, {})
        if not isinstance(values, dict):
            continue
        for name, constraint in values.items():
            if name == "php" or not isinstance(constraint, str):
                continue
            findings.append(_dependency(name, constraint, scope, "Composer", file.path))
    return findings


def parse_dotnet(file: RepositoryFile) -> list[DependencyFinding]:
    root = _xml_root(file)
    if root is None:
        return []
    findings = []
    for node in root.findall(".//PackageReference"):
        name = node.get("Include") or node.get("Update")
        if not name:
            continue
        version = node.get("Version") or node.findtext("Version")
        findings.append(_dependency(name, version, "runtime", "NuGet", file.path))
    return findings


def ecosystem_runtime(file: RepositoryFile) -> RuntimeFinding | None:
    name = file.path.rsplit("/", 1)[-1].lower()
    content = file.text_content or ""
    if name == "cargo.toml":
        try:
            package = tomllib.loads(content).get("package", {})
        except tomllib.TOMLDecodeError:
            package = {}
        constraint = package.get("rust-version") if isinstance(package, dict) else None
        return RuntimeFinding(runtime="Rust", version_constraint=constraint, evidence=[file.path])
    if name == "gemfile":
        match = re.search(r"(?m)^\s*ruby\s+['\"]([^'\"]+)", content)
        return RuntimeFinding(
            runtime="Ruby",
            version_constraint=match.group(1) if match else None,
            evidence=[file.path],
        )
    if name == "composer.json":
        try:
            require = json.loads(content).get("require", {})
        except json.JSONDecodeError:
            require = {}
        constraint = require.get("php") if isinstance(require, dict) else None
        return RuntimeFinding(runtime="PHP", version_constraint=constraint, evidence=[file.path])
    if name.endswith((".csproj", ".fsproj", ".vbproj")):
        root = _xml_root(file)
        constraint = root.findtext(".//TargetFramework") if root is not None else None
        return RuntimeFinding(runtime=".NET", version_constraint=constraint, evidence=[file.path])
    if name == "pom.xml":
        root = _xml_root(file)
        constraint = None
        if root is not None:
            constraint = root.findtext(".//{*}maven.compiler.release") or root.findtext(
                ".//{*}maven.compiler.source"
            )
        return RuntimeFinding(runtime="Java", version_constraint=constraint, evidence=[file.path])
    return None


def _dependency(
    name: str,
    constraint: str | None,
    scope: DependencyScope,
    ecosystem: str,
    source_path: str,
) -> DependencyFinding:
    return DependencyFinding(
        name=name,
        version_constraint=constraint,
        scope=scope,
        ecosystem=ecosystem,
        source_path=source_path,
    )


def _xml_root(file: RepositoryFile) -> ET.Element | None:
    try:
        return ET.fromstring(file.text_content or "")
    except ET.ParseError:
        return None
