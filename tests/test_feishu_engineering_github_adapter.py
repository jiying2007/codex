"""Concrete optional GitHub PR/CI REST shapes, no HTTP network in tests."""
from __future__ import annotations

import unittest
from unittest import mock

from tools.codex_assets.feishu_engineering_agent.github_adapter import (
    GitHubApiFailure, GitHubForge, GitHubTransport,
)
from tools.codex_assets.feishu_engineering_agent.delivery import PublicationGrant

SHA = "0123456789abcdef0123456789abcdef01234567"


class GitHubAdapterContractTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        def request(method, path, payload):
            self.calls.append((method, path, payload))
            if "/git/ref/heads/" in path:
                return {"object": {"sha": SHA, "type": "commit"}}
            if method == "POST" and path.endswith("/pulls"):
                return {"number": 73, "head": {"sha": SHA}}
            if "/pulls/" in path:
                return {"number": 73, "state": "open", "merged_at": None,
                        "head": {"sha": SHA}}
            if "/actions/runs/" in path:
                return {"status": "completed", "conclusion": "success",
                        "head_sha": SHA}
            raise AssertionError("unexpected GitHub REST route")
        self.forge = GitHubForge(
            "robot-app", "jiying2007/robot-app", request,
            remote_write_enabled=False,
        )

    def test_default_disabled_does_not_post_or_push(self):
        request = {
            "run_id": "a" * 32, "repo_full_name": "jiying2007/robot-app",
            "head_sha": SHA, "target_ref": "refs/heads/feat/bugfix",
            "approval_ref": "approved",
        }
        with self.assertRaises(GitHubApiFailure):
            self.forge.publish(request)
        self.assertEqual([], self.calls)
        self.forge.remote_write_enabled = True
        published = self.forge.publish(request)
        self.assertEqual("73", published["pr_id"])
        self.assertEqual("GET", self.calls[0][0])
        self.assertEqual("POST", self.calls[1][0])
        self.assertTrue(self.calls[1][2]["draft"])
        self.assertEqual("main", self.calls[1][2]["base"])
        self.assertFalse(any("/git/push" in path for _, path, _ in self.calls))

    def test_observed_pr_and_ci_have_exact_sha(self):
        pr = self.forge.observe_pr("github://pr/73")
        self.assertEqual("open", pr["state"])
        self.assertEqual("robot-app", pr["repo_alias"])
        self.assertEqual(SHA, pr["head_sha"])
        ci = self.forge.observe_ci("github://ci/12345")
        self.assertEqual("success", ci["conclusion"])
        self.assertEqual(SHA, ci["head_sha"])
        self.assertTrue(all(method == "GET" for method, _, _ in self.calls))

    def test_unknown_refs_and_remote_sha_discrepancy_fail_closed(self):
        with self.assertRaises(GitHubApiFailure):
            self.forge.observe_pr("http://example.com/73")
        with self.assertRaises(GitHubApiFailure):
            self.forge.observe_ci("github://pr/73")
        self.forge.remote_write_enabled = True
        with self.assertRaises(GitHubApiFailure):
            self.forge.publish({
                "run_id": "a" * 32, "repo_full_name": "bad-owner/repo",
                "head_sha": SHA, "target_ref": "refs/heads/test",
            })
        with self.assertRaises(GitHubApiFailure):
            self.forge.publish({
                "run_id": "a" * 32, "repo_full_name": "jiying2007/robot-app",
                "head_sha": SHA, "target_ref": "refs/heads/../../unsafe",
            })

    def test_transport_only_accepts_fixed_api_origin_and_write_token(self):
        transport = GitHubTransport("jiying2007/robot-app")
        with self.assertRaises(GitHubApiFailure):
            transport("POST", "/repos/jiying2007/robot-app/pulls", {})
        with self.assertRaises(GitHubApiFailure):
            transport("GET", "/repos/other_owner/project/actions/runs/1", None)
        with self.assertRaises(GitHubApiFailure):
            transport("GET", "/repos/jiying2007/robot-app/../secrets", None)
        with self.assertRaises(GitHubApiFailure):
            GitHubTransport("https://github.com/bad/path")


if __name__ == "__main__":
    unittest.main()
