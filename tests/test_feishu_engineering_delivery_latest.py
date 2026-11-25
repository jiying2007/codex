"""Delivery candidates survive later reads without hiding newer failed edits."""
import json
import unittest
from unittest import mock
import uuid

from tests import test_feishu_engineering_remote as remote_fixture
from tools.codex_assets import feishu_codex_bot as bot_module
from tools.codex_assets.feishu_engineering_agent.delivery import ContextDelivery
from tools.codex_assets.feishu_engineering_agent.models import IntakeRejected


class LatestEditDeliveryTests(unittest.TestCase):
    def setUp(self):
        # Reuse only setup/helpers; do not inherit or rediscover its test class.
        self.fixture = remote_fixture.RemoteEngineeringTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.add_second_repo()
        self.observed = []
        self.during_observation = None
        self.delivery = ContextDelivery(self.fixture.config, self.fixture.executor, self.forge)

    def forge(self, repo):
        def discover(branch, sha, workflows):
            self.observed.append((repo.alias, branch, sha))
            if self.during_observation is not None:
                self.during_observation()
            return {
                "repo_alias": repo.alias, "repo_full_name": repo.github_repository,
                "head_sha": sha, "branch": branch, "base_branch": repo.github_base_branch,
                "workflows": {workflow: 11 for workflow in workflows}, "pr_number": 7,
            }
        observer = mock.Mock()
        observer.discover_delivery.side_effect = discover
        return observer

    def completed_edit(self, message_id, sha, topic="root:om_root"):
        fixture = self.fixture
        fixture.submit(message_id, "修复 初始化失败并添加回归", topic)
        row = fixture.latest()
        _bot, job = fixture.decode(row)
        self.assertTrue(fixture.store.claim_queued(job.task_id))
        repo = fixture.config.repository(job.repository)
        cwd = repo.worktree_root / f"task-{job.task_id}"
        result = bot_module.ExecutionResult(
            "fixture", branch_name=f"{repo.branch_prefix}-{job.task_id}", commit_hash=sha,
            worktree_path=cwd, thread_id=str(uuid.UUID(int=job.task_id)), thread_cwd=cwd,
        )
        fixture.executor.finish(job, result, None)
        fixture.store.record_result(job.task_id, result.branch_name, sha, cwd)
        fixture.store.complete_with_output(job.task_id, result.text)
        return job.task_id

    def test_reads_preserve_single_and_joint_exact_edit_proof(self):
        fixture = self.fixture
        fixture.intake("om_root", remote_fixture.ISSUE)
        app_edit = self.completed_edit("om_edit_app", "a" * 40)
        fixture.submit("om_review_app", "审查 初始化修改")
        fixture.complete(fixture.latest())
        event, result = fixture.intake("om_verify_app", "检查交付")
        self.assertIn("a" * 40, self.delivery.verify(event, result))

        fixture.intake("om_select_firmware", "/repo firmware")
        firmware_edit = self.completed_edit("om_edit_firmware", "b" * 40)
        fixture.submit("om_explain_firmware", "分析 说明初始化修改")
        fixture.complete(fixture.latest())
        event, result = fixture.intake("om_verify_joint", "检查联合交付")
        self.assertIn("联合交付 CI 核验通过", self.delivery.verify_joint(event, result))
        with fixture.store._connect() as db:
            proof = json.loads(db.execute(
                "SELECT proof_json FROM engineering_context_joint_delivery"
            ).fetchone()[0])
        self.assertEqual(
            {("robot-app", app_edit, "a" * 40), ("firmware", firmware_edit, "b" * 40)},
            {(item["alias"], item["task_id"], item["head_sha"]) for item in proof},
        )
        fixture.intake("om_select_app", "/repo robot-app")
        fixture.submit("om_failed_edit", "修复 后续边界条件")
        self.assertTrue(fixture.store.finish_unsuccessful(
            fixture.latest()["id"], "failed", "SyntheticPreflightFailure"))
        event, result = fixture.intake("om_verify_joint_again", "检查联合交付")
        with self.assertRaises(IntakeRejected):
            self.delivery.verify_joint(event, result)
        fixture.runner.run.assert_not_called()

    def test_newest_edit_must_complete_before_any_older_edit_can_be_delivered(self):
        fixture = self.fixture
        for status in ("queued", "running", "failed", "unknown"):
            with self.subTest(status=status):
                topic = "root:om_" + status
                fixture.intake("om_root_" + status, remote_fixture.ISSUE, topic)
                self.completed_edit("om_good_" + status, "a" * 40, topic)
                fixture.submit("om_new_" + status, "修复 第二个初始化问题", topic)
                newest = fixture.latest()["id"]
                if status == "running":
                    self.assertTrue(fixture.store.claim_queued(newest))
                elif status in ("failed", "unknown"):
                    self.assertTrue(fixture.store.finish_unsuccessful(newest, status, "SyntheticFailure"))
                event, result = fixture.intake("om_verify_" + status, "检查交付", topic)
                with self.assertRaises(IntakeRejected):
                    self.delivery.verify(event, result)
                with fixture.store._connect() as db:
                    self.assertEqual(newest, self.delivery._joint_snapshot(db, result.context_id)[0]["task_id"])
        self.assertEqual([], self.observed)
        with fixture.store._connect() as db:
            self.assertEqual(0, db.execute("SELECT COUNT(*) FROM engineering_context_delivery").fetchone()[0])

    def test_joint_delivery_keeps_participant_without_an_edit_until_it_delivers(self):
        fixture = self.fixture
        fixture.intake("om_root", remote_fixture.ISSUE)
        app_edit = self.completed_edit("om_edit_app", "a" * 40)
        fixture.intake("om_select_firmware", "/repo firmware")
        fixture.submit("om_review_firmware", "审查 控制器初始化")
        fixture.complete(fixture.latest())
        event, result = fixture.intake("om_verify_incomplete_joint", "检查联合交付")
        with fixture.store._connect() as db:
            snapshot = self.delivery._joint_snapshot(db, result.context_id)
        self.assertEqual({("robot-app", "edit"), ("firmware", "review")},
                         {(row["repository"], row["mode"]) for row in snapshot})
        with self.assertRaises(IntakeRejected):
            self.delivery.verify_joint(event, result)
        self.assertEqual([], self.observed)

        firmware_edit = self.completed_edit("om_edit_firmware", "b" * 40)
        event, result = fixture.intake("om_verify_complete_joint", "检查联合交付")
        self.assertIn("联合交付 CI 核验通过", self.delivery.verify_joint(event, result))
        with fixture.store._connect() as db:
            proof = json.loads(db.execute(
                "SELECT proof_json FROM engineering_context_joint_delivery"
            ).fetchone()[0])
        self.assertEqual({app_edit, firmware_edit}, {row["task_id"] for row in proof})

    def test_new_edit_arriving_during_observation_prevents_old_proof_commit(self):
        fixture = self.fixture
        fixture.intake("om_root", remote_fixture.ISSUE)
        self.completed_edit("om_first", "a" * 40)
        event, result = fixture.intake("om_verify", "检查交付")
        self.during_observation = lambda: fixture.submit("om_new", "修复 新发现的边界条件")
        with self.assertRaisesRegex(IntakeRejected, "核验期间"):
            self.delivery.verify(event, result)
        with fixture.store._connect() as db:
            self.assertEqual(0, db.execute("SELECT COUNT(*) FROM engineering_context_delivery").fetchone()[0])
        self.assertEqual(1, len(self.observed))
        self.assertEqual("queued", fixture.latest()["status"])


if __name__ == "__main__":
    unittest.main()
