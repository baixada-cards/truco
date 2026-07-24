from __future__ import annotations

import copy
import json
import unittest

from scripts.check_stack import load_stack, validate_stack
from scripts.verify_public_stack import EDGES, raw_url, value_at, verify


class StackValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = load_stack()

    def test_checked_in_stack_is_valid(self) -> None:
        self.assertEqual(validate_stack(self.stack), [])

    def test_moving_revision_is_rejected(self) -> None:
        changed = copy.deepcopy(self.stack)
        changed["components"]["web"]["revision"] = "main"
        self.assertIn(
            "web revision must be a full lowercase Git SHA",
            validate_stack(changed),
        )

    def test_private_or_sibling_repository_is_rejected(self) -> None:
        changed = copy.deepcopy(self.stack)
        changed["components"]["web"]["repository"] = "../truco-web"
        self.assertIn(
            "web must use a public HTTPS Baixada repository",
            validate_stack(changed),
        )

    def test_raw_urls_are_revision_scoped(self) -> None:
        component = self.stack["components"]["web"]
        url = raw_url(
            component["repository"],
            component["revision"],
            "dependencies.lock.json",
        )
        self.assertIn(component["revision"], url)
        self.assertNotIn("/main/", url)

    def test_nested_value_reader(self) -> None:
        self.assertEqual(value_at({"a": {"b": "value"}}, ("a", "b")), "value")

    def test_verifier_detects_nested_lock_drift(self) -> None:
        documents: dict[str, bytes] = {}
        for name, component in self.stack["components"].items():
            proof = {
                "spec": "README.md",
                "engine": "spec.lock.json",
                "solver": "engine.lock.json",
                "bots": "contracts.lock.json",
                "server": "contracts.lock.json",
                "design_system": "package.json",
                "web": "dependencies.lock.json",
            }[name]
            documents[raw_url(component["repository"], component["revision"], proof)] = (
                b"proof" if proof == "README.md" else b"{}"
            )

        for edge in EDGES:
            component = self.stack["components"][edge.component]
            url = raw_url(component["repository"], component["revision"], edge.path)
            document = json.loads(documents.get(url, b"{}"))
            cursor = document
            for key in edge.json_path[:-1]:
                cursor = cursor.setdefault(key, {})
            cursor[edge.json_path[-1]] = self.stack["components"][edge.target][
                edge.target_revision_field
            ]
            documents[url] = json.dumps(document).encode()

        self.assertEqual(verify(self.stack, documents.__getitem__), [])
        web = self.stack["components"]["web"]
        web_url = raw_url(
            web["repository"], web["revision"], "dependencies.lock.json"
        )
        web_lock = json.loads(documents[web_url])
        web_lock["truco_server"]["revision"] = "0" * 40
        documents[web_url] = json.dumps(web_lock).encode()
        errors = verify(self.stack, documents.__getitem__)
        self.assertTrue(
            any("web/dependencies.lock.json pins" in error for error in errors)
        )


if __name__ == "__main__":
    unittest.main()
