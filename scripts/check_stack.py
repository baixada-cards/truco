#!/usr/bin/env python3
"""Validate the offline shape and safety invariants of stack.lock.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STACK_PATH = ROOT / "stack.lock.json"
WORKFLOW_ROOT = ROOT / ".github" / "workflows"

EXPECTED_COMPONENTS = {
    "spec",
    "engine",
    "solver",
    "bots",
    "server",
    "design_system",
    "web",
}
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
PUBLIC_REPOSITORY = re.compile(
    r"^https://github\.com/baixada-cards/[a-z0-9-]+\.git$"
)
ACTION_REFERENCE = re.compile(r"^\s*uses:\s*[^@\s]+@([^\s#]+)", re.MULTILINE)


def load_stack(path: Path = STACK_PATH) -> dict:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def validate_stack(stack: dict) -> list[str]:
    errors: list[str] = []
    if stack.get("format") != "baixada-truco-stack/v1":
        errors.append("unexpected stack format")

    components = stack.get("components")
    if not isinstance(components, dict):
        return errors + ["components must be an object"]

    names = set(components)
    if names != EXPECTED_COMPONENTS:
        errors.append(
            f"component set mismatch: expected {sorted(EXPECTED_COMPONENTS)}, "
            f"found {sorted(names)}"
        )

    repositories: set[str] = set()
    for name, component in components.items():
        if not isinstance(component, dict):
            errors.append(f"{name} must be an object")
            continue
        repository = component.get("repository", "")
        revision = component.get("revision", "")
        if not PUBLIC_REPOSITORY.fullmatch(repository):
            errors.append(f"{name} must use a public HTTPS Baixada repository")
        if repository in repositories:
            errors.append(f"repository is duplicated: {repository}")
        repositories.add(repository)
        if not FULL_SHA.fullmatch(revision):
            errors.append(f"{name} revision must be a full lowercase Git SHA")

    solver = components.get("solver", {})
    if not FULL_SHA.fullmatch(solver.get("contract_revision", "")):
        errors.append("solver contract_revision must be a full lowercase Git SHA")

    return errors


def validate_actions(workflow_root: Path = WORKFLOW_ROOT) -> list[str]:
    errors: list[str] = []
    workflow_paths = sorted(
        [
            *workflow_root.glob("*.yml"),
            *workflow_root.glob("*.yaml"),
        ]
    )
    if not workflow_paths:
        return ["at least one workflow is required"]

    for path in workflow_paths:
        text = path.read_text(encoding="utf-8")
        for match in ACTION_REFERENCE.finditer(text):
            if not FULL_SHA.fullmatch(match.group(1)):
                errors.append(
                    f"{path.relative_to(ROOT)} has a non-immutable action reference: "
                    f"{match.group(1)}"
                )
        if "permissions:\n  contents: read" not in text:
            errors.append(f"{path.relative_to(ROOT)} must declare read-only contents")
    return errors


def main() -> int:
    errors = [*validate_stack(load_stack()), *validate_actions()]
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print("validated 7 exact public components and immutable Actions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
