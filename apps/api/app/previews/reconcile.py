import argparse
import subprocess


def _names(args: list[str], prefix: str) -> list[str]:
    result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=10)
    return sorted(name for name in result.stdout.splitlines() if name.startswith(prefix))


def candidates() -> dict[str, list[str]]:
    label = "label=repolive.preview=true"
    return {
        "containers": _names(
            ["docker", "ps", "-a", "--filter", label, "--format", "{{.Names}}"],
            "repolive-",
        ),
        "volumes": _names(
            ["docker", "volume", "ls", "--filter", label, "--format", "{{.Name}}"],
            "repolive-preview-",
        ),
        "networks": _names(
            ["docker", "network", "ls", "--filter", label, "--format", "{{.Name}}"],
            "repolive-preview-",
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconcile exact RepoLive-labeled preview resources."
    )
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    found = candidates()
    print({"dry_run": not args.execute, "candidates": found})
    if args.execute:
        for name in found["containers"]:
            subprocess.run(["docker", "rm", "-f", name], check=False)
        for name in found["volumes"]:
            subprocess.run(["docker", "volume", "rm", name], check=False)
        for name in found["networks"]:
            subprocess.run(["docker", "network", "rm", name], check=False)


if __name__ == "__main__":
    main()
