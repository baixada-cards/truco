#!/usr/bin/env python3
"""Verify nested public component locks against the integration stack."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

try:
    from scripts.check_stack import load_stack, validate_stack
except ModuleNotFoundError:  # Direct execution: python scripts/verify_public_stack.py
    from check_stack import load_stack, validate_stack


@dataclass(frozen=True)
class Edge:
    component: str
    path: str
    json_path: tuple[str, ...]
    target: str
    target_revision_field: str = "revision"


EDGES = (
    Edge("engine", "spec.lock.json", ("revision",), "spec"),
    Edge("solver", "engine.lock.json", ("revision",), "engine"),
    Edge("bots", "contracts.lock.json", ("engine", "revision"), "engine"),
    Edge(
        "bots",
        "contracts.lock.json",
        ("policy_format", "revision"),
        "solver",
        "contract_revision",
    ),
    Edge("server", "contracts.lock.json", ("engine", "revision"), "engine"),
    Edge("server", "contracts.lock.json", ("bots", "revision"), "bots"),
    Edge("server", "spec.lock.json", ("revision",), "spec"),
    Edge("web", "dependencies.lock.json", ("truco_server", "revision"), "server"),
    Edge(
        "web",
        "dependencies.lock.json",
        ("design_system", "revision"),
        "design_system",
    ),
)

PROOF_PATHS = {
    "spec": "README.md",
    "engine": "spec.lock.json",
    "solver": "engine.lock.json",
    "bots": "contracts.lock.json",
    "server": "contracts.lock.json",
    "design_system": "package.json",
    "web": "dependencies.lock.json",
}


def repository_slug(repository: str) -> str:
    return repository.removesuffix(".git").removeprefix("https://github.com/")


def raw_url(repository: str, revision: str, path: str) -> str:
    return (
        "https://raw.githubusercontent.com/"
        f"{repository_slug(repository)}/{revision}/{path}"
    )


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "baixada-truco-stack-verifier/1"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch_json(repository: str, revision: str, path: str) -> dict[str, Any]:
    return json.loads(fetch_bytes(raw_url(repository, revision, path)))


def value_at(document: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = document
    for key in path:
        value = value[key]
    return value


def verify(stack: dict, fetch=fetch_bytes) -> list[str]:
    errors = validate_stack(stack)
    if errors:
        return errors

    components = stack["components"]
    documents: dict[tuple[str, str], dict[str, Any]] = {}

    for name, proof_path in PROOF_PATHS.items():
        component = components[name]
        url = raw_url(component["repository"], component["revision"], proof_path)
        try:
            payload = fetch(url)
        except (OSError, urllib.error.URLError) as error:
            errors.append(f"cannot fetch {name} proof at {url}: {error}")
            continue
        if not payload:
            errors.append(f"empty proof for {name} at {url}")
        if proof_path.endswith(".json"):
            try:
                documents[(name, proof_path)] = json.loads(payload)
            except json.JSONDecodeError as error:
                errors.append(f"invalid JSON for {name}/{proof_path}: {error}")

    for edge in EDGES:
        key = (edge.component, edge.path)
        document = documents.get(key)
        if document is None:
            component = components[edge.component]
            try:
                document = json.loads(
                    fetch(
                        raw_url(
                            component["repository"],
                            component["revision"],
                            edge.path,
                        )
                    )
                )
                documents[key] = document
            except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
                errors.append(
                    f"cannot inspect {edge.component}/{edge.path}: {error}"
                )
                continue

        try:
            actual = value_at(document, edge.json_path)
        except (KeyError, TypeError) as error:
            errors.append(
                f"{edge.component}/{edge.path} lacks "
                f"{'.'.join(edge.json_path)}: {error}"
            )
            continue
        expected = components[edge.target][edge.target_revision_field]
        if actual != expected:
            errors.append(
                f"{edge.component}/{edge.path} pins {actual}, "
                f"expected {edge.target} {expected}"
            )

    return errors


def main() -> int:
    errors = verify(load_stack())
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print("verified 9 public dependency edges across 7 immutable components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
