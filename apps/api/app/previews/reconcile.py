import argparse
import subprocess


def candidates() -> list[str]:
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "label=repolive.preview=true", "--format", "{{.Names}}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return [name for name in result.stdout.splitlines() if name.startswith("repolive-preview-")]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconcile exact RepoLive-labeled preview resources."
    )
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    names = candidates()
    print({"dry_run": not args.execute, "candidates": names})
    if args.execute:
        for name in names:
            subprocess.run(["docker", "rm", "-f", name], check=False)


if __name__ == "__main__":
    main()
