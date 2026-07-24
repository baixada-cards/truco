#!/usr/bin/env python3
"""Assemble one deployable release from exact, independent component checkouts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
FORBIDDEN_PARTS = {
    ".git",
    ".next",
    "node_modules",
    "playwright-report",
    "screenshots",
    "target",
    "test-results",
}
FORBIDDEN_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.production.local",
}
PRIVATE_AUDIO_RELATIVE = PurePosixPath("public/audio/farol")


def run_text(*arguments: str, cwd: Path) -> str:
    return subprocess.check_output(arguments, cwd=cwd, text=True).strip()


def tracked_files(checkout: Path) -> list[PurePosixPath]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=checkout)
    return [PurePosixPath(item.decode()) for item in raw.split(b"\0") if item]


def validate_relative(path: PurePosixPath) -> None:
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe tracked path: {path}")
    if any(part in FORBIDDEN_PARTS for part in path.parts):
        raise ValueError(f"forbidden tracked path: {path}")
    if path.name in FORBIDDEN_NAMES or path.name.startswith("gha-creds-"):
        raise ValueError(f"forbidden tracked credential/environment path: {path}")


def include_tracked(path: PurePosixPath) -> bool:
    """Keep documented examples, but never package environment-specific files."""
    return not (path.name.startswith(".env") and path.name != ".env.example")


def validate_checkout(checkout: Path, expected_revision: str) -> None:
    if not FULL_SHA.fullmatch(expected_revision):
        raise ValueError(f"invalid expected revision: {expected_revision}")
    if run_text("git", "rev-parse", "HEAD", cwd=checkout) != expected_revision:
        raise ValueError(f"{checkout} is not at expected revision {expected_revision}")
    if run_text("git", "status", "--porcelain", "--untracked-files=no", cwd=checkout):
        raise ValueError(f"{checkout} has tracked working-tree changes")


def copy_tracked(checkout: Path, destination: Path) -> None:
    for relative in tracked_files(checkout):
        validate_relative(relative)
        if not include_tracked(relative):
            continue
        source = checkout.joinpath(*relative.parts)
        if source.is_symlink():
            raise ValueError(f"symlinks are not allowed in releases: {relative}")
        if not source.is_file():
            raise ValueError(f"tracked release entry is not a file: {relative}")
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def load_audio_lock(web_checkout: Path) -> list[dict[str, object]]:
    lock = json.loads(
        (web_checkout / "private-audio.lock.json").read_text(encoding="utf-8")
    )
    files = lock.get("files")
    if lock.get("schema_version") != 1 or not isinstance(files, list) or not files:
        raise ValueError("unsupported or empty private-audio lock")
    return files


def copy_private_audio(web_checkout: Path, web_destination: Path) -> list[dict]:
    copied: list[dict] = []
    for item in load_audio_lock(web_checkout):
        name = item.get("name")
        size = item.get("bytes")
        digest = item.get("sha256")
        if (
            not isinstance(name, str)
            or "/" in name
            or not name.endswith(".m4a")
            or not isinstance(size, int)
            or size <= 0
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise ValueError(f"invalid private-audio lock entry: {item!r}")
        source = web_checkout.joinpath(*PRIVATE_AUDIO_RELATIVE.parts, name)
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"missing or unsafe licensed audio: {name}")
        data = source.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if len(data) != size or actual != digest:
            raise ValueError(f"licensed audio does not match lock: {name}")
        target = web_destination.joinpath(*PRIVATE_AUDIO_RELATIVE.parts, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        copied.append({"name": name, "bytes": size, "sha256": digest})
    return copied


def assemble(
    server_checkout: Path,
    web_checkout: Path,
    destination: Path,
    stack_path: Path = ROOT / "stack.lock.json",
) -> Path:
    stack = json.loads(stack_path.read_text(encoding="utf-8"))
    components = stack["components"]
    server_revision = components["server"]["revision"]
    web_revision = components["web"]["revision"]
    validate_checkout(server_checkout, server_revision)
    validate_checkout(web_checkout, web_revision)

    if destination.exists():
        raise ValueError(f"destination must be absent: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.assembling-",
            dir=destination.parent,
        )
    )
    try:
        copy_tracked(server_checkout, staging)
        web_destination = staging / "truco-frontend"
        copy_tracked(web_checkout, web_destination)
        audio = copy_private_audio(web_checkout, web_destination)

        remote_script = ROOT / "deploy" / "remote_deploy.sh"
        target_script = staging / "deploy" / "remote_deploy.sh"
        target_script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(remote_script, target_script)
        target_script.chmod(
            target_script.stat().st_mode
            | stat.S_IXUSR
            | stat.S_IXGRP
            | stat.S_IXOTH
        )

        manifest = {
            "format": "baixada-truco-release/v1",
            "stack_revision": run_text("git", "rev-parse", "HEAD", cwd=ROOT),
            "components": {
                "server": server_revision,
                "web": web_revision,
            },
            "private_audio": audio,
        }
        (staging / "RELEASE.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--web", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    result = assemble(
        args.server.resolve(),
        args.web.resolve(),
        args.destination.resolve(),
    )
    print(f"assembled release at {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
