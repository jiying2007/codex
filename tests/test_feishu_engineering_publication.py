"""Real local Git snapshots and fake HTTP; never publish to a real remote."""
from __future__ import annotations

import dataclasses
import io
import os
import pathlib
import subprocess
import threading
import unittest
from unittest import mock

from tests import test_feishu_engineering_remote as remote_fixture
from tools.codex_assets import feishu_codex_bot as bot_module
from tools.codex_assets.feishu_engineering_agent import publication
from tools.codex_assets.feishu_engineering_agent.models import InboundEvent, IntakeRejected


class FakeGitHub:
    def __init__(self):
        self.head = None
        self.pull = None
        self.reads = 0
        self.creates = 0
        self.lose_create_reply = False

    def branch_head(self, branch):
        self.reads += 1
        return self.head

    def find_pull(self, branch, base, sha):
        self.reads += 1
        return self.pull

    def create_pull(self, branch, base, sha, task_id):
        self.creates += 1
        self.pull = {"number": 7, "draft": True}
        if self.lose_create_reply:
            raise OSError("fixture secret must not escape")
        return self.pull


class PublicationTest(unittest.TestCase):
    def setUp(self):
        self.fixture = remote_fixture.RemoteEngineeringTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        fixture = self.fixture
        (fixture.repo / ".git").rmdir()
        self.git(fixture.repo, "init", "-b", "main")
        (fixture.repo / "source.txt").write_text("base\n")
        self.git(fixture.repo, "add", "source.txt")
        self.git(fixture.repo, "commit", "-m", "fixture base")
        self.base_sha = self.git(fixture.repo, "rev-parse", "HEAD")
        self.git(fixture.repo, "remote", "add", "origin", "https://github.com/example-org/robot.git")
        self.repo = dataclasses.replace(fixture.config.repository("robot-app"),
            github_repository="example-org/robot", github_base_branch="main",
            github_required_workflows=(".github/workflows/verify.yml",))
        # These are explicit synthetic configuration fields, never credentials.
        object.__setattr__(self.repo, "github_publish_enabled", True)
        fixture.config = dataclasses.replace(fixture.config, repositories={"robot-app": self.repo})
        object.__setattr__(fixture.config, "agent_github_write_token", "fixture-write-credential")
        fixture.executor.config = fixture.config
        fixture.intake("om_root", remote_fixture.ISSUE)
        fixture.submit("om_edit", "修复 初始化失败")
        _bot, self.job = fixture.decode(fixture.latest())
        self.assertTrue(fixture.store.claim_queued(self.job.task_id))
        self.cwd, self.branch = bot_module.WorktreeManager(fixture.config).prepare(self.job.task_id, self.repo)
        (self.cwd / "source.txt").write_text("fixed\n")
        self.git(self.cwd, "add", "source.txt")
        self.git(self.cwd, "commit", "-m", "fixture exact edit")
        self.sha = self.git(self.cwd, "rev-parse", "HEAD")
        outcome = bot_module.ExecutionResult("fixture result", self.branch, self.sha, self.cwd,
                                            remote_fixture.THREAD, self.cwd)
        fixture.store.record_result(self.job.task_id, self.branch, self.sha, self.cwd)
        fixture.executor.finish(self.job, outcome, None)
        fixture.store.complete_with_output(self.job.task_id, outcome.text)
        self.remote = FakeGitHub()
        self.native = publication.NativePublicationGit(fixture.config)
        self.pushes = 0
        self.push_effect = None
        self.pusher = mock.Mock(spec=publication.NativePublicationGit)
        self.pusher.verify_local.side_effect = self.native.verify_local
        self.pusher.push_create.side_effect = self.push
        self.controller = publication.ContextPublication(fixture.config, fixture.executor,
            transport_factory=lambda repo, token: self.remote, pusher=self.pusher)

    def git(self, cwd, *args):
        completed = subprocess.run(["git", "-C", str(cwd), *args],
            env=publication.NativePublicationGit.environment(), capture_output=True, text=True, check=True)
        return completed.stdout.strip()

    def push(self, repo, row, token):
        with self.fixture.store._connect() as db:
            receipt = db.execute("SELECT status,head_sha,command_sha256 FROM engineering_context_publications").fetchone()
        self.assertEqual(("intent", self.sha), (receipt["status"], receipt["head_sha"]))
        self.assertEqual(64, len(receipt["command_sha256"]))
        self.pushes += 1
        self.remote.head = self.sha
        if self.push_effect:
            self.push_effect()

    def command(self, message_id="om_publish", sha=None):
        return self.fixture.intake(message_id, "/publish " + (sha or self.sha))

    def state(self):
        with self.fixture.store._connect() as db:
            row = db.execute("SELECT * FROM engineering_context_publications").fetchone()
        return dict(row) if row else None

    def test_exact_publication_persists_intent_first_and_repeat_only_reads(self):
        event, result = self.command()
        self.assertEqual("publish", result.intent)
        self.assertIn("/pull/7", self.controller.publish(event, result))
        self.assertEqual((1, 1), (self.pushes, self.remote.creates))
        self.assertEqual("published", self.state()["status"])
        event, result = self.command("om_reconcile")
        self.assertIn("/pull/7", self.controller.publish(event, result))
        self.assertEqual((1, 1), (self.pushes, self.remote.creates))
        self.assertIn("封存", self.fixture.submit("om_continue", "继续推进"))
        self.assertEqual([], self.fixture.store.pending())
        self.fixture.runner.run.assert_not_called()

    def test_push_reply_lost_never_repushes_or_creates_pr_on_reconcile(self):
        self.push_effect = lambda: (_ for _ in ()).throw(OSError("fixture private error"))
        text = self.controller.publish(*self.command())
        self.assertNotIn("fixture private error", text)
        self.assertEqual("unknown", self.state()["status"])
        self.controller.publish(*self.command("om_reconcile"))
        self.assertEqual((1, 0), (self.pushes, self.remote.creates))
        self.remote.pull = {"number": 7, "draft": True}
        self.assertIn("/pull/7", self.controller.publish(*self.command("om_observed")))
        self.assertEqual((1, 0), (self.pushes, self.remote.creates))

    def test_pr_reply_lost_is_reconciled_without_second_post(self):
        self.remote.lose_create_reply = True
        self.controller.publish(*self.command())
        self.assertEqual("unknown", self.state()["status"])
        self.assertIn("/pull/7", self.controller.publish(*self.command("om_reconcile")))
        self.assertEqual((1, 1), (self.pushes, self.remote.creates))

    def test_existing_same_head_reuses_branch_and_other_head_is_never_overwritten(self):
        self.remote.head = self.sha
        self.assertIn("/pull/7", self.controller.publish(*self.command()))
        self.assertEqual((0, 1), (self.pushes, self.remote.creates))
        self.remote.head = "a" * 40
        self.assertIn("尚未核实", self.controller.publish(*self.command("om_changed")))
        self.assertEqual((0, 1), (self.pushes, self.remote.creates))

    def test_wrong_sha_owner_and_source_cannot_authorize(self):
        with self.assertRaises(IntakeRejected):
            self.controller.publish(*self.command(sha="a" * 40))
        event, result = self.command("om_valid")
        with self.assertRaises(IntakeRejected):
            self.controller.publish(dataclasses.replace(event, actor="ou_other"), result)
        with self.assertRaises(IntakeRejected):
            self.controller.publish(dataclasses.replace(event, source="offline_fixture"), result)
        self.assertIsNone(self.state())
        self.assertEqual(0, self.remote.reads)

    def test_only_exact_publish_command_is_control_and_not_context_authority(self):
        for index, body in enumerate(("/publish", "/publish " + self.sha + " extra", "/publish " + self.sha.upper(),
                                      "/publish\n" + self.sha, "/publish " + self.sha + "\nhttps://github.com/x/y")):
            with self.subTest(body=body), self.assertRaises(IntakeRejected):
                self.fixture.intake("om_bad_" + str(index), body)
        _event, result = self.fixture.intake("om_note", "文档写着 /publish " + self.sha)
        self.assertNotEqual("publish", result.intent)
        self.assertEqual(0, self.remote.reads)

    def test_disabled_publication_and_missing_write_identity_do_not_create_intent(self):
        event, result = self.command()
        object.__setattr__(self.repo, "github_publish_enabled", False)
        with self.assertRaises(IntakeRejected):
            self.controller.publish(event, result)
        object.__setattr__(self.repo, "github_publish_enabled", True)
        object.__setattr__(self.fixture.config, "agent_github_write_token", "")
        with self.assertRaises(IntakeRejected):
            self.controller.publish(event, result)
        self.assertIsNone(self.state())
        self.assertEqual(0, self.remote.reads)

    def test_dirty_worktree_and_wrong_origin_are_rejected_before_intent(self):
        event, result = self.command()
        (self.cwd / "source.txt").write_text("unaccepted change\n")
        with self.assertRaises((IntakeRejected, bot_module.FeishuCodexError)):
            self.controller.publish(event, result)
        self.git(self.cwd, "checkout", "--", "source.txt")
        self.git(self.fixture.repo, "remote", "set-url", "origin", "https://github.com/other/repo.git")
        with self.assertRaises(IntakeRejected):
            self.controller.publish(event, result)
        self.assertIsNone(self.state())
        self.assertEqual(0, self.remote.reads)

    def test_replacement_refs_and_object_alternates_are_rejected(self):
        event, result = self.command()
        self.git(self.cwd, "replace", self.sha, self.base_sha)
        with self.assertRaises(IntakeRejected):
            self.controller.publish(event, result)
        self.git(self.cwd, "replace", "-d", self.sha)
        alternate = self.fixture.repo / ".git" / "objects" / "info" / "alternates"
        alternate.write_text(str(self.fixture.repo / ".git" / "objects") + "\n")
        with self.assertRaises(IntakeRejected):
            self.controller.publish(event, result)
        self.assertIsNone(self.state())

    def test_newer_edit_prevents_publishing_old_completion(self):
        self.fixture.submit("om_edit_again", "继续推进")
        with self.assertRaises(IntakeRejected):
            self.controller.publish(*self.command())
        self.assertIsNone(self.state())

    def test_concurrent_command_cannot_launch_second_external_attempt(self):
        entered, released = threading.Event(), threading.Event()
        def pause():
            entered.set()
            self.assertTrue(released.wait(5))
        self.push_effect = pause
        replies = []
        args = self.command()
        worker = threading.Thread(target=lambda: replies.append(self.controller.publish(*args)))
        worker.start()
        try:
            self.assertTrue(entered.wait(5))
            self.assertIn("尚未核实", self.controller.publish(*self.command("om_parallel")))
            self.assertEqual(1, self.pushes)
        finally:
            released.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual((1, 1), (self.pushes, self.remote.creates))
        self.assertEqual(1, len(replies))
        self.assertEqual("published", self.state()["status"])

    def bare_remote(self):
        remote = self.fixture.root / "remote.git"
        self.git(self.fixture.root, "init", "--bare", str(remote))
        subprocess.run(["git", "-C", str(self.fixture.repo), "-c", "protocol.file.allow=always",
                        "push", str(remote), self.base_sha + ":refs/heads/main"],
                       env=self.native.environment(), capture_output=True, check=True)
        return remote

    def route_native_push(self, remote, before_push=None):
        actual = subprocess.run
        def route(argv, **kwargs):
            if "push" in argv:
                self.assertIn("--force-with-lease=refs/heads/" + self.branch + ":", argv)
                self.assertNotIn("--force", argv)
                self.assertFalse(any(arg.startswith("+") for arg in argv))
                self.assertNotIn("fixture-write-credential", repr(argv))
                if before_push:
                    before_push(actual)
                argv = list(argv)
                git_index = argv.index("git")
                argv[git_index + 1:git_index + 1] = ["-c", "protocol.file.allow=always"]
                argv[argv.index("https://github.com/example-org/robot.git")] = str(remote)
            return actual(argv, **kwargs)
        return mock.patch.object(publication.subprocess, "run", side_effect=route)

    def test_native_push_creates_exact_ref_from_private_snapshot(self):
        remote = self.bare_remote()
        row = self.fixture.executor.binding(self.job.task_id)
        with self.route_native_push(remote):
            self.native.push_create(self.repo, row, "fixture-write-credential")
        self.assertEqual(self.sha, self.git(remote, "rev-parse", "refs/heads/" + self.branch))
        self.assertEqual(self.base_sha, self.git(remote, "rev-parse", "refs/heads/main"))
        self.assertEqual("", self.git(self.cwd, "status", "--porcelain"))

    def test_empty_lease_refuses_branch_created_after_preflight_even_if_fast_forward(self):
        remote = self.bare_remote()
        row = self.fixture.executor.binding(self.job.task_id)
        def competing_writer(actual):
            actual(["git", "-C", str(remote), "update-ref", "refs/heads/" + self.branch, self.base_sha],
                   env=self.native.environment(), capture_output=True, check=True)
        with self.route_native_push(remote, competing_writer), self.assertRaises(IntakeRejected):
            self.native.push_create(self.repo, row, "fixture-write-credential")
        self.assertEqual(self.base_sha, self.git(remote, "rev-parse", "refs/heads/" + self.branch))


class PublicationTransportTest(unittest.TestCase):
    def test_git_environment_drops_credentials_proxy_trace_and_personal_helpers(self):
        private = {"GH_TOKEN": "personal", "HTTP_PROXY": "https://proxy.invalid", "GIT_TRACE_CURL": "1",
                   "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "url.https://other.invalid/.insteadOf",
                   "GIT_CONFIG_VALUE_0": "https://github.com/", "FEISHU_APP_SECRET": "secret"}
        with mock.patch.dict(os.environ, private):
            env = publication.NativePublicationGit.environment("fixture-write-credential", "example-org/robot")
        for key in ("GH_TOKEN", "HTTP_PROXY", "GIT_TRACE_CURL", "FEISHU_APP_SECRET"):
            self.assertNotIn(key, env)
        settings = {env["GIT_CONFIG_KEY_" + str(i)]: env["GIT_CONFIG_VALUE_" + str(i)]
                    for i in range(int(env["GIT_CONFIG_COUNT"]))}
        self.assertEqual("", settings["credential.helper"])
        self.assertEqual("false", settings["http.followRedirects"])
        self.assertEqual("never", settings["protocol.allow"])
        self.assertEqual("always", settings["protocol.https.allow"])
        self.assertFalse(any("insteadof" in key.lower() for key in settings))
        self.assertEqual("1", env["GIT_NO_REPLACE_OBJECTS"])

    def test_http_creates_only_minimal_draft_for_exact_repository_and_head(self):
        transport = publication.GitHubPublicationTransport("example-org/robot", "fixture-write-credential")
        observed = {"number": 7, "draft": True, "state": "open", "merged_at": None,
                    "head": {"ref": "agent-1", "sha": "a" * 40, "repo": {"full_name": "example-org/robot"}},
                    "base": {"ref": "main", "repo": {"full_name": "example-org/robot"}}}
        with mock.patch.object(transport, "_request", return_value=observed) as request:
            self.assertEqual({"number": 7, "draft": True}, transport.create_pull("agent-1", "main", "a" * 40, 1))
            method, path = request.call_args.args
            payload = request.call_args.kwargs["payload"]
        self.assertEqual(("POST", "/pulls"), (method, path))
        self.assertTrue(payload["draft"])
        self.assertFalse(payload["maintainer_can_modify"])
        self.assertEqual({"title", "head", "base", "draft", "maintainer_can_modify", "body"}, set(payload))
        self.assertNotIn("fixture-write-credential", repr(payload))
        self.assertNotIn("feishu.cn", repr(payload))
        observed["head"]["sha"] = "b" * 40
        with mock.patch.object(transport, "_request", return_value=observed), self.assertRaises(IntakeRejected):
            transport.create_pull("agent-1", "main", "a" * 40, 1)

    def test_http_does_not_use_environment_proxy_or_follow_redirects(self):
        transport = publication.GitHubPublicationTransport("example-org/robot", "fixture-write-credential")
        self.assertFalse(any(isinstance(h, publication.urllib.request.ProxyHandler) and h.proxies
                             for h in transport.opener.handlers))
        redirect = next(h for h in transport.opener.handlers if isinstance(h, publication._NoRedirect))
        self.assertIsNone(redirect.redirect_request(None, None, 302, "", {}, "https://other.invalid"))
        with mock.patch.object(transport.opener, "open", side_effect=OSError("fixture-write-credential")):
            with self.assertRaises(IntakeRejected) as caught:
                transport.branch_head("agent-1")
        self.assertNotIn("fixture-write-credential", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
