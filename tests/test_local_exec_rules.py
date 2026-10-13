import hashlib
import json
import pathlib
import tempfile
import unittest

from tools.codex_assets.local_exec_rules import load_rules, verified_inputs


class LocalExecRulesTests(unittest.TestCase):
    def fixture(self, directory, rules=None):
        root = pathlib.Path(directory)
        (root / "rules").mkdir()
        base = b'prefix_rule(pattern=["rtk"], decision="allow")\n'
        (root / "rules/default.rules").write_bytes(base)
        path = root / "local.json"
        path.write_text(json.dumps({"schema_version": 1, "profile": "team-collab", "target": "rules/default.rules",
            "base_sha256": hashlib.sha256(base).hexdigest(), "extra_rules": rules or [
                'prefix_rule(pattern=["sort"], decision="allow")']}))
        return root, path, hashlib.sha256(path.read_bytes()).hexdigest(), base

    def test_exact_local_input_is_built_and_verifiable(self):
        with tempfile.TemporaryDirectory() as directory:
            root, path, sha, base = self.fixture(directory)
            text, identity = load_rules(path, sha, "team-collab", base)
            self.assertEqual(text, base.decode() + 'prefix_rule(pattern=["sort"], decision="allow")\n')
            self.assertEqual(verified_inputs({"exec_rules": identity}, root, "team-collab"), {"exec_rules": identity})

    def test_input_drift_and_profile_or_base_mismatch_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            _, path, sha, base = self.fixture(directory)
            for profile, source, expected in (("default", base, sha), ("team-collab", b"changed", sha),
                                              ("team-collab", base, "0" * 64)):
                with self.subTest(profile=profile), self.assertRaises(ValueError):
                    load_rules(path, expected, profile, source)

    def test_rule_input_cannot_execute_code(self):
        with tempfile.TemporaryDirectory() as directory:
            _, path, sha, base = self.fixture(directory, ['__import__("os").system("arbitrary")'])
            with self.assertRaises(ValueError):
                load_rules(path, sha, "team-collab", base)


if __name__ == "__main__":
    unittest.main()
