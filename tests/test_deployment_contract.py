from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeploymentContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = (ROOT / ".github/workflows/production.yml").read_text()

    def test_workflow_is_manual_and_dry_by_default(self) -> None:
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("\n  push:", self.workflow)
        self.assertIn("default: false", self.workflow)
        self.assertIn("environment:\n      name: production", self.workflow)

    def test_workflow_uses_ephemeral_cloud_identity_and_private_audio(self) -> None:
        self.assertIn("id-token: write", self.workflow)
        self.assertIn("google-github-actions/auth@", self.workflow)
        self.assertIn("audio:sync-private", self.workflow)
        self.assertIn("audio:verify-private", self.workflow)
        self.assertNotIn("upload-artifact", self.workflow)
        self.assertNotIn("service-account-key", self.workflow)

    def test_workflow_deploys_bounded_private_server_and_public_web(self) -> None:
        self.assertEqual(self.workflow.count("--max-instances 1"), 2)
        self.assertEqual(self.workflow.count("--min-instances 0"), 2)
        self.assertEqual(self.workflow.count("--max 1"), 2)
        self.assertEqual(self.workflow.count("--min 0"), 2)
        self.assertIn("--no-allow-unauthenticated", self.workflow)
        self.assertIn("--allow-unauthenticated", self.workflow)
        self.assertIn("roles/run.invoker", self.workflow)
        self.assertIn("TRUCO_ENGINE_SERVICE_AUDIENCE", self.workflow)

    def test_workflow_smokes_real_session_and_rolls_back_traffic(self) -> None:
        self.assertIn("/api/game/session", self.workflow)
        self.assertIn("botKind", self.workflow)
        self.assertIn('smoke-match.json', self.workflow)
        self.assertGreaterEqual(self.workflow.count("for attempt in $(seq 1 30)"), 2)
        self.assertIn("update-traffic", self.workflow)
        self.assertIn("trap rollback ERR", self.workflow)

    def test_droplet_mechanics_are_not_part_of_the_public_deploy(self) -> None:
        self.assertNotIn("DROPLET_", self.workflow)
        self.assertNotIn("ssh", self.workflow.lower())
        self.assertNotIn("rsync", self.workflow)


if __name__ == "__main__":
    unittest.main()
