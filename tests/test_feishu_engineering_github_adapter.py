"""Exact read-only GitHub evidence; no HTTP network or publication in tests."""
from __future__ import annotations

import copy
import json
import unittest
from unittest import mock

from tools.codex_assets.feishu_engineering_agent.github_adapter import (
    GitHubApiFailure, GitHubForge, GitHubTransport,
)

SHA = "0123456789abcdef0123456789abcdef01234567"
REPOSITORY = "example-org/robot-app"
BRANCH = "agent-42"
WORKFLOW = ".github/workflows/verify.yml"


class GitHubAdapterContractTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        repo = {"full_name": REPOSITORY}
        self.pr = {
            "number": 73, "state": "open", "merged_at": None,
            "head": {"sha": SHA, "ref": BRANCH, "repo": repo},
            "base": {"ref": "main", "repo": repo},
        }
        self.ci = {
            "id": 12345, "path": WORKFLOW, "status": "completed",
            "conclusion": "success", "head_sha": SHA, "head_branch": BRANCH,
            "repository": repo, "head_repository": repo,
            "event": "pull_request", "pull_requests": [{"number": 73}],
        }
        def request(method, path, payload):
            self.calls.append((method, path, payload))
            self.assertEqual("GET", method)
            self.assertIsNone(payload)
            if path.endswith("/pulls/73"):
                return copy.deepcopy(self.pr)
            if path.endswith("/actions/runs/12345"):
                return copy.deepcopy(self.ci)
            raise AssertionError("unexpected GitHub evidence route")
        self.forge = GitHubForge("robot-app", REPOSITORY, request)

    def observe(self):
        return self.forge.observe_delivery(73, [12345], BRANCH, SHA, [WORKFLOW])

    def test_exact_pr_head_and_every_required_ci_are_observed(self):
        proof = self.observe()
        self.assertEqual(SHA, proof["head_sha"])
        self.assertEqual({WORKFLOW: 12345}, proof["workflows"])
        self.assertEqual("open", proof["pr_state"])
        self.assertEqual([
            ("GET", "/repos/" + REPOSITORY + "/pulls/73", None),
            ("GET", "/repos/" + REPOSITORY + "/actions/runs/12345", None),
            ("GET", "/repos/" + REPOSITORY + "/pulls/73", None),
        ], self.calls)

    def test_wrong_repository_branch_base_or_commit_never_passes(self):
        original = copy.deepcopy(self.pr)
        for section, field, value in (
            ("head", "sha", "b" * 40),
            ("head", "ref", "different-branch"),
            ("head", "repo", {"full_name": "other-org/robot-app"}),
            ("base", "ref", "wrong-base"),
            ("base", "repo", {"full_name": "other-org/robot-app"}),
        ):
            with self.subTest(section=section, field=field):
                self.pr = copy.deepcopy(original)
                self.pr[section][field] = value
                with self.assertRaises(GitHubApiFailure):
                    self.observe()

    def test_ci_failure_wrong_head_wrong_workflow_or_wrong_pr_is_not_proof(self):
        original = copy.deepcopy(self.ci)
        for field, value in (
            ("conclusion", "failure"), ("status", "in_progress"),
            ("head_sha", "b" * 40), ("head_branch", "different-branch"),
            ("path", ".github/workflows/unrelated.yml"), ("id", 999),
            ("repository", {"full_name": "other-org/robot-app"}),
            ("head_repository", {"full_name": "other-org/robot-app"}),
            ("pull_requests", [{"number": 74}]), ("event", "workflow_dispatch"),
        ):
            with self.subTest(field=field):
                self.ci = copy.deepcopy(original)
                self.ci[field] = value
                with self.assertRaises(GitHubApiFailure):
                    self.observe()

    def test_pr_head_is_rechecked_after_ci_reads(self):
        calls = []
        def changing(method, path, payload):
            calls.append(path)
            if path.endswith("/actions/runs/12345"):
                self.pr["head"]["sha"] = "b" * 40
                return copy.deepcopy(self.ci)
            return copy.deepcopy(self.pr)
        self.forge.request = changing
        with self.assertRaises(GitHubApiFailure):
            self.observe()
        self.assertEqual(3, len(calls))

    def test_ambiguous_or_incomplete_identifiers_fail_before_http(self):
        for run_ids in ([], [12345, 12345], [True]):
            with self.subTest(run_ids=run_ids), self.assertRaises(GitHubApiFailure):
                self.forge.observe_delivery(73, run_ids, BRANCH, SHA, [WORKFLOW])
        with self.assertRaises(GitHubApiFailure):
            self.forge.observe_delivery(73, [12345], "../unsafe", SHA, [WORKFLOW])
        self.assertEqual([], self.calls)

    def test_transport_is_get_only_even_with_a_private_token(self):
        transport = GitHubTransport(REPOSITORY, "fixture-read-only-token")
        transport.opener = mock.Mock()
        for method in ("POST", "PATCH", "PUT", "DELETE"):
            with self.subTest(method=method), self.assertRaises(GitHubApiFailure):
                transport(method, "/repos/" + REPOSITORY + "/pulls", {})
        with self.assertRaises(GitHubApiFailure):
            transport("GET", "/repos/" + REPOSITORY + "/pulls/73", {})
        transport.opener.open.assert_not_called()

    def test_transport_rejects_foreign_or_non_evidence_paths(self):
        transport = GitHubTransport(REPOSITORY)
        transport.opener = mock.Mock()
        for path in (
            "/repos/other-org/project/actions/runs/1",
            "/repos/" + REPOSITORY + "/../secrets",
            "/repos/" + REPOSITORY + "/contents/private",
            "/repos/" + REPOSITORY + "/pulls/73?extra=1",
            "https://example.com/pulls/73",
        ):
            with self.subTest(path=path), self.assertRaises(GitHubApiFailure):
                transport("GET", path)
        transport.opener.open.assert_not_called()
        with self.assertRaises(GitHubApiFailure):
            GitHubTransport("https://github.com/bad/path")

    def test_transport_sends_only_exact_get_without_body(self):
        transport = GitHubTransport(REPOSITORY)
        response = mock.Mock()
        response.read.return_value = json.dumps(self.pr).encode("utf-8")
        transport.opener = mock.Mock()
        transport.opener.open.return_value.__enter__ = mock.Mock(return_value=response)
        transport.opener.open.return_value.__exit__ = mock.Mock(return_value=False)
        self.assertEqual(self.pr, transport("GET", "/repos/" + REPOSITORY + "/pulls/73"))
        request = transport.opener.open.call_args.args[0]
        self.assertEqual("GET", request.get_method())
        self.assertIsNone(request.data)
        self.assertEqual("https://api.github.com/repos/" + REPOSITORY + "/pulls/73", request.full_url)


if __name__ == "__main__":
    unittest.main()
