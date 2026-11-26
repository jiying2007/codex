"""No-model, no-database safety tests for the host cutover preflight."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "feishu-cutover-preflight.py"
SPEC = importlib.util.spec_from_file_location("feishu_cutover_preflight", str(SCRIPT))
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


class CutoverPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="feishu-cutover-preflight-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = self.root / "private.env"
        self.policy = self.root / "policy.json"
        self.db = self.root / "state.sqlite3"
        self.lock = self.root / "bot.lock"
        self.write_policy()
        self.write_env()

    def write_policy(self, policy_path=None):
        payload = {
            "schema_version": 1,
            "engineering_enabled": True,
            "agent_intake_enabled": False,
            "repositories": {"app": {"path": str(self.root / "repo")}},
            "state_db": str(self.db),
            "lock_file": str(self.lock),
        }
        path = policy_path or self.policy
        path.write_text(json.dumps(payload), encoding="utf-8")
        path.chmod(0o600)

    def write_env(self, policy_path=None):
        values = {
            "FEISHU_APP_ID": "cli_fixture",
            "FEISHU_APP_SECRET": "secret-must-not-appear",
            "FEISHU_TARGET_CHAT_ID": "oc_fixture",
            "FEISHU_BOT_CONFIG": str(policy_path or self.policy),
            "FEISHU_STATE_DB": str(self.db),
            "FEISHU_LOCK_FILE": str(self.lock),
            "FEISHU_AGENT_OPENAI_API_KEY": "dedicated-key-must-not-appear",
            "FEISHU_AGENT_GITHUB_WRITE_TOKEN": "github-token-must-not-appear",
        }
        self.env.write_text(
            "".join(key + "=" + value + "\n" for key, value in values.items()),
            encoding="utf-8",
        )
        self.env.chmod(0o600)

    def observe(self, expected_sha=None):
        sha = "a" * 40
        service = {"ActiveState": "inactive", "SubState": "dead", "MainPID": "0"}
        with mock.patch.object(PREFLIGHT, "service_observation", side_effect=[service, service]), \
                mock.patch.object(PREFLIGHT, "command", side_effect=[sha, ""]):
            return PREFLIGHT.probe(self.root, self.env, expected_sha=expected_sha)

    def test_probe_is_read_only_redacted_and_compares_exact_sha(self):
        sha = "a" * 40
        result = self.observe(sha)
        encoded = json.dumps(result, sort_keys=True)
        self.assertTrue(result["checkout"]["matches_expected_sha"])
        self.assertFalse(result["checkout"]["dirty"])
        self.assertTrue(result["config"]["env_parsed"])
        self.assertTrue(result["config"]["policy_parsed"])
        self.assertFalse(result["service_changed"])
        self.assertFalse(result["model_called"])
        self.assertFalse(result["database_opened"])
        self.assertFalse(result["cutover_proven"])
        self.assertEqual("not_observed_no_sqlite_access", result["state"]["task_status"])
        self.assertFalse(self.db.exists())
        for secret in (
            "secret-must-not-appear", "dedicated-key-must-not-appear",
            "github-token-must-not-appear",
        ):
            self.assertNotIn(secret, encoded)

    def test_dirty_submodule_is_not_suppressed(self):
        sha = "a" * 40
        service = {"ActiveState": "inactive", "SubState": "dead", "MainPID": "0"}
        with mock.patch.object(PREFLIGHT, "service_observation", side_effect=[service, service]), \
                mock.patch.object(PREFLIGHT, "command", side_effect=[sha, " m submodule"]) as run:
            result = PREFLIGHT.probe(self.root, self.env, expected_sha=sha)
        self.assertTrue(result["checkout"]["dirty"])
        status_args = run.call_args_list[1].args[0]
        self.assertNotIn("--ignore-submodules=all", status_args)
        self.assertIn("--untracked-files=all", status_args)

    def test_expected_sha_mismatch_is_an_explicit_blocker(self):
        result = self.observe("b" * 40)
        self.assertFalse(result["checkout"]["matches_expected_sha"])
        self.assertIn("checkout_does_not_match_expected_sha", result["blockers_observed"])

    def test_invalid_expected_sha_is_rejected_before_observation(self):
        with mock.patch.object(PREFLIGHT, "service_observation") as service:
            with self.assertRaisesRegex(ValueError, "40-character"):
                PREFLIGHT.probe(self.root, self.env, expected_sha="not-a-sha")
        service.assert_not_called()

    def test_symlinked_private_policy_is_not_followed(self):
        target = self.root / "policy-target.json"
        self.write_policy(target)
        link = self.root / "policy-link.json"
        link.symlink_to(target)
        self.write_env(link)
        result = self.observe()
        self.assertEqual("unsafe_symlink_component", result["config"]["policy_file"])
        self.assertFalse(result["config"]["policy_parsed"])
        self.assertIn("explicit_private_policy_unreadable_or_absent", result["blockers_observed"])

    def test_private_reader_rejects_symlinks_and_fifo_without_blocking(self):
        target = self.root / "target.env"
        target.write_text("FEISHU_APP_SECRET=do-not-read\n", encoding="utf-8")
        target.chmod(0o600)
        link = self.root / "link.env"
        link.symlink_to(target)
        self.assertEqual("unsafe_symlink_component", PREFLIGHT.info(link))
        with self.assertRaises(ValueError):
            PREFLIGHT.read_private(link)
        fifo = self.root / "private.fifo"
        os.mkfifo(str(fifo), 0o600)
        self.assertEqual("unsafe_type", PREFLIGHT.info(fifo))
        with self.assertRaises((OSError, ValueError)):
            PREFLIGHT.read_private(fifo)

    def test_private_environment_parser_exposes_only_presence_to_report(self):
        values = PREFLIGHT.read_env(self.env)
        self.assertEqual("secret-must-not-appear", values["FEISHU_APP_SECRET"])
        result = self.observe()
        fields = result["config"]["environment_fields_present"]
        self.assertTrue(fields["FEISHU_APP_SECRET"])
        self.assertTrue(fields["FEISHU_AGENT_OPENAI_API_KEY"])
        self.assertTrue(fields["FEISHU_AGENT_GITHUB_WRITE_TOKEN"])
        self.assertNotIn("secret-must-not-appear", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
