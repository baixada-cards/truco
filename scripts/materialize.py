#!/usr/bin/env python3
"""Materialize exact public component revisions without creating a monorepo."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

try:
    from scripts.check_stack import ROOT, load_stack, validate_stack
except ModuleNotFoundError:  # Direct execution: python scripts/materialize.py
    from check_stack import ROOT, load_stack, validate_stack

COMPONENT_ROOT = ROOT / ".components"


def run(*arguments: str, cwd: Path | None = None) -> None:
    subprocess.run(arguments, cwd=cwd, check=True)


def materialize(name: str, repository: str, revision: str, refresh: bool) -> Path:
    destination = COMPONENT_ROOT / name.replace("_", "-")
    if refresh and destination.exists():
        shutil.rmtree(destination)

    if not destination.exists():
        COMPONENT_ROOT.mkdir(parents=True, exist_ok=True)
        run(
            "git",
            "-c",
            "credential.helper=",
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            repository,
            str(destination),
        )

    origin = subprocess.check_output(
        ["git", "remote", "get-url", "origin"],
        cwd=destination,
        text=True,
    ).strip()
    if origin != repository:
        raise RuntimeError(
            f"{destination} has origin {origin!r}; expected {repository!r}"
        )

    run("git", "fetch", "--depth=1", "origin", revision, cwd=destination)
    run("git", "checkout", "--detach", revision, cwd=destination)
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=destination,
        text=True,
    ).strip()
    if actual != revision:
        raise RuntimeError(f"{name} resolved {actual}, expected {revision}")
    print(f"materialized {name} at {revision[:8]} -> {destination}")
    return destination


def main() -> int:
    stack = load_stack()
    errors = validate_stack(stack)
    if errors:
        raise SystemExit("\n".join(errors))

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--component",
        action="append",
        choices=sorted(stack["components"]),
        help="materialize only this component; repeatable",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="replace selected materialized checkouts",
    )
    arguments = parser.parse_args()
    selected = arguments.component or list(stack["components"])
    for name in selected:
        component = stack["components"][name]
        materialize(
            name,
            component["repository"],
            component["revision"],
            arguments.refresh,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
