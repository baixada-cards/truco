from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

from deploy.assemble_release import assemble


def run(*arguments: str, cwd: Path) -> None:
    subprocess.run(arguments, cwd=cwd, check=True, capture_output=True)


def make_checkout(root: Path, files: dict[str, bytes]) -> Path:
    root.mkdir()
    run("git", "init", "-q", cwd=root)
    run("git", "config", "user.name", "Release Test", cwd=root)
    run("git", "config", "user.email", "release-test@example.invalid", cwd=root)
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    run("git", "add", ".", cwd=root)
    run("git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "fixture", cwd=root)
    return root


class ReleaseAssemblyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

        audio = b"licensed-runtime-audio"
        digest = hashlib.sha256(audio).hexdigest()
        web_files = {
            "package.json": b'{"name":"web"}\n',
            "pnpm-lock.yaml": b"lockfileVersion: '9.0'\n",
            ".env.example": b"SAFE=\n",
            "private-audio.lock.json": json.dumps(
                {
                    "schema_version": 1,
                    "files": [
                        {
                            "name": "locked.m4a",
                            "bytes": len(audio),
                            "sha256": digest,
                        }
                    ],
                }
            ).encode(),
        }
        self.server = make_checkout(
            self.root / "server",
            {
                "Cargo.toml": b"[workspace]\n",
                "Cargo.lock": b"# lock\n",
                "crates/truco-server/Cargo.toml": b"[package]\nname='truco-server'\n",
            },
        )
        self.web = make_checkout(self.root / "web", web_files)
        audio_path = self.web / "public/audio/farol/locked.m4a"
        audio_path.parent.mkdir(parents=True)
        audio_path.write_bytes(audio)

        self.server_revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.server, text=True
        ).strip()
        self.web_revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.web, text=True
        ).strip()
        self.stack = self.root / "stack.lock.json"
        self.stack.write_text(
            json.dumps(
                {
                    "components": {
                        "server": {"revision": self.server_revision},
                        "web": {"revision": self.web_revision},
                    }
                }
            )
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_assembly_contains_only_tracked_source_locked_audio_and_manifest(self) -> None:
        (self.server / "untracked-secret.txt").write_text("do not copy")
        (self.web / "node_modules").mkdir()
        (self.web / "node_modules/dependency.js").write_text("do not copy")
        destination = self.root / "release"

        assemble(self.server, self.web, destination, self.stack)

        self.assertTrue((destination / "Cargo.toml").is_file())
        self.assertTrue((destination / "truco-frontend/package.json").is_file())
        self.assertTrue(
            (destination / "truco-frontend/public/audio/farol/locked.m4a").is_file()
        )
        self.assertFalse((destination / "untracked-secret.txt").exists())
        self.assertFalse((destination / "truco-frontend/node_modules").exists())
        manifest = json.loads((destination / "RELEASE.json").read_text())
        self.assertEqual(manifest["components"]["server"], self.server_revision)
        self.assertEqual(manifest["components"]["web"], self.web_revision)
        mode = (destination / "deploy/remote_deploy.sh").stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)

    def test_modified_tracked_checkout_is_rejected(self) -> None:
        (self.server / "Cargo.toml").write_text("modified")
        with self.assertRaisesRegex(ValueError, "tracked working-tree changes"):
            assemble(self.server, self.web, self.root / "release", self.stack)

    def test_audio_checksum_mismatch_is_rejected(self) -> None:
        (self.web / "public/audio/farol/locked.m4a").write_bytes(b"wrong")
        with self.assertRaisesRegex(ValueError, "does not match lock"):
            assemble(self.server, self.web, self.root / "release", self.stack)

    def test_existing_destination_is_rejected(self) -> None:
        destination = self.root / "release"
        destination.mkdir()
        with self.assertRaisesRegex(ValueError, "must be absent"):
            assemble(self.server, self.web, destination, self.stack)

    def test_failed_assembly_leaves_no_partial_destination(self) -> None:
        destination = self.root / "release"
        (self.web / "public/audio/farol/locked.m4a").unlink()
        with self.assertRaisesRegex(ValueError, "missing or unsafe licensed audio"):
            assemble(self.server, self.web, destination, self.stack)
        self.assertFalse(destination.exists())


class DeploymentContractTests(unittest.TestCase):
    def test_workflow_is_manual_dry_by_default_and_uses_oidc(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/production.yml"
        ).read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertIn("default: false", workflow)
        self.assertIn("environment:\n      name: production", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("google-github-actions/auth@", workflow)
        self.assertNotIn("upload-artifact", workflow)
        self.assertNotIn("ssh-keyscan", workflow)

    def test_remote_script_requires_new_binary_and_rolls_back(self) -> None:
        script = (
            Path(__file__).resolve().parents[1] / "deploy/remote_deploy.sh"
        ).read_text()
        self.assertIn("target/release/truco-server", script)
        self.assertIn("Node.js 24 or newer is required", script)
        self.assertIn("RELEASE.json does not match requested stack revision", script)
        self.assertIn("rollback()", script)
        self.assertNotIn("truco-engine-service", script)


if __name__ == "__main__":
    unittest.main()
