"""Exercise actual remote queue, exact CLI binding and cancel without a paid turn."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pathlib
import sqlite3
import tempfile
import types
import unittest
from unittest import mock

from tools.codex_assets import feishu_codex_bot as bot_module
from tools.codex_assets.feishu_engineering_agent.executor import EngineeringExecutor
from tools.codex_assets.feishu_engineering_agent.models import InboundEvent
from tools.codex_assets.feishu_engineering_agent.service import LinkContextService, topic_key
from tools.codex_assets.feishu_task_spool import TaskSpool, SpoolError

THREAD = "01979c6c-0354-7000-8000-000000000001"
ISSUE = "https://project.feishu.cn/example-space/issue/detail/1000000001"
WIKI = "https://example-tenant.feishu.cn/wiki/ExampleWikiToken123"


class RemoteEngineeringTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="engineering-remote-")
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        self.repo = self.root/"repo"
        self.repo.mkdir()
        (self.repo/".git").mkdir()
        self.agent_home = self.root/"agent-home"
        self.agent_home.mkdir(mode=0o700)
        self.private = self.root/"private"
        self.private.mkdir(mode=0o700)
        policy = bot_module.RepositoryPolicy(
            alias="robot-app",path=self.repo,allowed_open_ids=frozenset(),
            allowed_modes=frozenset(("explain","review","edit")),
            agent_allowed_modes=frozenset(("explain","review","edit")),
            edit_strategy="worktree",base_ref="HEAD",
            worktree_root=self.root/"worktrees",branch_prefix="agent",
            commit_enabled=True,
            verification_commands=(),document_read_urls=frozenset((WIKI,)),
        )
        # Synthetic noncredential fixture, never sourced from a real account.
        synthetic_identity = "fixture-" + "not-a-credential"
        self.config = bot_module.BotConfig(
            app_id="cli_test",app_secret="fixture-secret",target_chat_id="oc_test",
            bot_name="研发助手",repositories={"robot-app":policy},
            default_repo="robot-app",allowed_open_ids=frozenset(("ou_owner","ou_other")),
            state_db=self.private/"bot.sqlite3",lock_file=self.private/"bot.lock",
            engineering_enabled=True,agent_intake_enabled=True,
            link_repositories={"feishu_project:example-space":("robot-app",)},
            agent_billing_source="external_gateway",agent_codex_home=self.agent_home,
            agent_openai_api_key=synthetic_identity,
            agent_openai_base_url="https://gateway.example/v1",
            agent_budget_backend="litellm", agent_budget_max_usd="10",
            agent_budget_key_alias="fixture-agent", agent_model="fixture-model",
            deny_read_paths=(self.private,),isolation_write_paths=(self.agent_home,),
        )
        self.store=bot_module.StateStore(self.config.state_db)
        self.service=LinkContextService(self.store)
        self.spool=TaskSpool(self.private/"feishu-pending-jobs")
        self.transport=mock.Mock()
        self.runner=mock.Mock()
        self.executor=EngineeringExecutor(self.config,self.store,self.spool,self.transport,self.runner)

    def intake(self,mid,text,topic="root:om_root",actor="ou_owner"):
        event=InboundEvent("feishu_message","tenantA","oc_test",actor,mid,text)
        result=self.service.handle(event,topic,set(self.config.repositories),self.config.link_repositories)
        return event,result

    def submit(self,mid,text,topic="root:om_root",executor=None):
        event=InboundEvent("feishu_message","tenantA","oc_test","ou_owner",mid,text)
        result=self.service.handle(event,topic,set(self.config.repositories),
            self.config.link_repositories,admit=(executor or self.executor).submit)
        return result.reply

    def latest(self):
        return self.store.pending()[-1]

    def decode(self,row):
        bot=bot_module.FeishuCodexBot(self.config,self.transport,self.runner,self.store)
        return bot,bot._decode_job(self.spool.get(row["id"]),row)

    def complete(self,row,thread=THREAD):
        bot,job=self.decode(row)
        self.assertTrue(self.store.claim_queued(job.task_id))
        result=bot_module.ExecutionResult("fixture",thread_id=thread,thread_cwd=self.config.repository(job.repository).path)
        self.executor.finish(job,result,None)
        self.store.complete_with_output(job.task_id, result.text)
        return job

    def test_link_only_then_explicit_read_directly_queues_existing_worker(self):
        event,result=self.intake("om_root",ISSUE)
        self.assertEqual("",result.intent)
        self.assertEqual([],self.store.pending())
        reply=self.submit("om_read","分析 复现：传感器初始化失败，检查错误处理")
        self.assertIn("queued",reply)
        row=self.latest()
        self.assertEqual("om_read",row["message_id"])
        self.assertEqual(f"agent:{os.getuid()}",row["sender_open_id"])
        bot,job=self.decode(row)
        self.assertIn("传感器初始化失败",job.task)
        self.assertIn(ISSUE,job.task)
        self.assertEqual("explain",job.mode)
        # Exact duplicate did not create another task.
        event,replay=self.intake("om_read","分析 复现：传感器初始化失败，检查错误处理")
        self.assertIsNone(replay.reply)
        self.assertEqual("",replay.intent)
        self.assertEqual(1,len(self.store.pending()))
        self.runner.run.assert_not_called()

    def test_native_session_exact_resume_and_unknown_block(self):
        self.intake("om_root",ISSUE)
        self.submit("om_read","分析 传感器复位逻辑")
        first=self.complete(self.latest())
        self.submit("om_continue","继续推进，直到全部完成")
        row=self.latest()
        bot,job=self.decode(row)
        target=self.executor.resume_target(job)
        self.assertEqual(THREAD,target.thread_id)
        self.assertEqual(first.task_id,target.root_task_id)
        self.assertEqual(self.repo,target.working_directory)
        self.assertTrue(self.store.claim_queued(job.task_id))
        self.assertTrue(self.store.finish_unsuccessful(job.task_id, "unknown", "SyntheticUnobservedRun"))
        self.assertIn("未知", self.submit("om_again","继续推进"))
        self.runner.run.assert_not_called()

    def test_no_billing_no_read_and_no_legacy_fallback(self):
        config=dataclasses.replace(self.config,agent_intake_enabled=False)
        ex=EngineeringExecutor(config,self.store,self.spool,self.transport,self.runner)
        self.assertIn("独立模型", self.submit("om_root","分析 "+ISSUE+" 复现：输入异常",executor=ex))
        self.assertEqual([],self.store.pending())
        self.runner.run.assert_not_called()

    def test_delivery_seal_rechecked_in_the_atomic_admission(self):
        self.intake("om_root", ISSUE)
        self.submit("om_edit", "修复 初始化失败并增加回归测试")
        row = self.latest()
        bot, job = self.decode(row)
        self.assertTrue(self.store.claim_queued(job.task_id))
        worktree = self.root / "worktrees" / "task-1"
        worktree.mkdir(parents=True)
        result = bot_module.ExecutionResult("fixture", "agent-1", "a" * 40, worktree, THREAD, worktree)
        self.store.record_result(job.task_id, result.branch_name, result.commit_hash, worktree)
        self.executor.finish(job, result, None)
        self.store.complete_with_output(job.task_id, result.text)
        self.intake("om_note", "补充说明：保留现有错误码")
        # Inject a seal immediately before publication while holding the same
        # writer transaction; a real concurrent writer cannot cross this lock.
        original = self.store.create_agent_task
        def seal_before_publish(*args, **kwargs):
            db = kwargs["connection"]
            db.execute("INSERT INTO engineering_context_delivery VALUES (?,?,?,?,?,?)",
                       (job.task_id, "a" * 40, "example-org/robot", 1, "{}", 1))
            return original(*args, **kwargs)
        with mock.patch.object(self.store,"create_agent_task",side_effect=seal_before_publish):
            self.assertIn("封存",self.submit("om_continue","继续推进"))
        self.assertEqual([], self.store.pending())
        with self.store._connect() as db:
            self.assertEqual(1, db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])
        self.runner.run.assert_not_called()

    def test_document_requires_explicit_audience_and_repository_grant(self):
        self.intake("om_root",ISSUE+" https://example-tenant.feishu.cn/docx/OtherDocument123")
        reply=self.submit("om_read","分析 关联文档")
        self.assertIn("明确授权",reply)
        self.assertEqual([],self.store.pending())
        self.transport.resolve_sources.assert_not_called()

    def test_scope_source_and_policy_tampering_denied(self):
        self.intake("om_root",ISSUE+" "+WIKI)
        self.submit("om_read","分析 初始化异常")
        row=self.latest()
        bot,job=self.decode(row)
        self.assertEqual((bot_module.SourceRef("doc",WIKI),),job.sources)
        payload=self.spool.get(job.task_id)
        payload["sources"]=[]
        with self.assertRaises(SpoolError):
            bot._decode_job(payload,row)
        config=dataclasses.replace(self.config,agent_openai_api_key=self.config.agent_openai_api_key+"-changed")
        changed=bot_module.FeishuCodexBot(config,self.transport,self.runner,self.store)
        with self.assertRaises(SpoolError):
            changed._decode_job(self.spool.get(job.task_id),row)
        self.runner.run.assert_not_called()

    def test_cancel_only_current_context_and_mcp_queue_not_touched(self):
        self.intake("om_root",ISSUE)
        self.submit("om_read","分析 初始化逻辑")
        target=self.latest()["id"]
        self.submit("om_other","分析 独立的第二项任务",topic="root:om_other")
        other=self.latest()["id"]
        event,result=self.intake("om_cancel","/cancel")
        self.assertIn("精确排队任务",self.executor.cancel(event,result))
        self.assertEqual("canceled",self.store.task_status(target))
        self.assertEqual("queued",self.store.task_status(other))
        self.runner.cancel_task.assert_not_called()

    def test_accepted_notes_do_not_require_feishu_history_permission(self):
        self.intake("om_root",ISSUE)
        self.intake("om_note","复现：电源重启后异常")
        self.assertIn("queued",self.submit("om_read","分析一下"))
        bot,job=self.decode(self.latest())
        self.assertIn("电源重启后异常",job.task)
        self.runner.run.assert_not_called()

    def test_expired_or_tampered_private_note_cannot_be_silently_dropped(self):
        self.intake("om_root",ISSUE)
        self.intake("om_note","复现：初始化异常")
        with self.store._connect() as db:
            db.execute("UPDATE engineering_context_note_inputs SET body='changed'")
        self.assertIn("摘要不符",self.submit("om_read","分析一下"))
        self.assertEqual([],self.store.pending())

    def test_ingress_task_and_dedupe_receipt_commit_together(self):
        self.intake("om_root",ISSUE)
        with mock.patch.object(self.store,"create_agent_task",
                               side_effect=sqlite3.OperationalError("fixture transaction interruption")):
            with self.assertRaises(sqlite3.OperationalError):
                self.submit("om_read","分析 初始化异常")
        with self.store._connect() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM engineering_context_events WHERE message_id='om_read'").fetchone())
            self.assertEqual(0,db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])
        self.assertIn("queued",self.submit("om_read","分析 初始化异常"))
        self.assertIsNone(self.submit("om_read","分析 初始化异常"))
        self.assertEqual(1,len(self.store.pending()))
        self.runner.run.assert_not_called()

    def add_second_repo(self):
        second=self.root/"firmware"
        second.mkdir()
        (second/".git").mkdir()
        a=self.config.repository("robot-app")
        self.config=dataclasses.replace(self.config,repositories={
            "robot-app":dataclasses.replace(a,github_repository="example-org/robot",
                                           github_required_workflows=(".github/workflows/verify.yml",)),
            "firmware":dataclasses.replace(a,alias="firmware",path=second,
                                          worktree_root=self.root/"firmware-worktrees",
                                          github_repository="example-org/firmware",
                                          github_required_workflows=(".github/workflows/verify.yml",)),
        })
        self.executor.config=self.config

    def test_running_cancel_is_durable_before_native_process_exists(self):
        self.intake("om_root",ISSUE)
        self.submit("om_read","分析 初始化")
        bot,job=self.decode(self.latest())
        self.assertTrue(self.store.claim_queued(job.task_id))
        event,result=self.intake("om_cancel","/cancel")
        self.assertIn("持久登记",self.executor.cancel(event,result))
        self.assertTrue(self.store.cancel_requested(job.task_id))
        actual=bot_module.CodexRunner(self.config)
        with mock.patch.object(bot_module.subprocess,"Popen") as popen:
            with self.assertRaises(bot_module.TaskCanceled):
                actual.run(job,persistent_session=True)
            popen.assert_not_called()

    def test_private_result_retrieval_and_unknown_reconciliation(self):
        self.intake("om_root",ISSUE)
        self.submit("om_read","分析 初始化")
        bot,job=self.decode(self.latest())
        self.assertTrue(self.store.claim_queued(job.task_id))
        outcome=bot_module.ExecutionResult("synthetic result",thread_id=THREAD,thread_cwd=self.repo)
        self.executor.finish(job,outcome,None)
        self.store.complete_with_output(job.task_id,outcome.text)
        event,result=self.intake("om_result","/result")
        self.assertEqual("synthetic result",self.executor.result(event,result))
        self.submit("om_again","继续推进")
        next_id=self.latest()["id"]
        self.assertTrue(self.store.claim_queued(next_id))
        self.assertTrue(self.store.finish_unsuccessful(next_id, "unknown", "SyntheticUnobservedRun"))
        receipt=self.store.reconcile_unknown(next_id,"a"*64)
        self.assertEqual("abandoned",receipt["status"])
        self.assertFalse(receipt["completion_claimed"])
        self.assertIn("queued",self.submit("om_new","分析 新的明确任务"))
        self.runner.run.assert_not_called()

    def test_explicit_shared_context_across_authorized_repositories(self):
        self.add_second_repo()
        self.intake("om_root",ISSUE)
        self.intake("om_shared","共享上下文：合成接口约定和联合验收范围")
        self.submit("om_a","分析 应用侧复位")
        self.intake("om_select_b","/repo firmware")
        self.submit("om_b","分析 控制侧复位")
        for row in self.store.pending():
            self.assertIn("合成接口约定和联合验收范围",self.decode(row)[1].task)
        self.runner.run.assert_not_called()

    def test_same_topic_separate_repo_receipts_resume_and_cancel(self):
        self.add_second_repo()
        self.intake("om_root",ISSUE)
        self.submit("om_a","分析 应用侧复位")
        first=self.latest()
        self.intake("om_select_b","/repo firmware")
        self.submit("om_b","分析 控制侧复位")
        second=self.latest()
        self.assertEqual(["robot-app","firmware"],[r["repository"] for r in self.store.pending()])
        bot,job=self.decode(first)
        self.assertEqual("robot-app",job.repository)
        bot,job=self.decode(second)
        self.assertNotIn("应用侧复位",job.task)
        self.complete(first,THREAD)
        thread_b="01979c6c-0354-7000-8000-000000000002"
        self.complete(second,thread_b)
        self.intake("om_select_a","/repo robot-app")
        self.submit("om_resume_a","继续推进")
        a=self.latest()
        self.intake("om_select_b2","/repo firmware")
        self.submit("om_resume_b","继续推进")
        b=self.latest()
        self.assertEqual(THREAD,self.executor.resume_target(self.decode(a)[1]).thread_id)
        self.assertEqual(thread_b,self.executor.resume_target(self.decode(b)[1]).thread_id)
        event,result=self.intake("om_cancel","/cancel")
        self.executor.cancel(event,result)
        self.assertEqual("queued",self.store.task_status(a["id"]))
        self.assertEqual("canceled",self.store.task_status(b["id"]))
        self.runner.run.assert_not_called()

    def test_joint_delivery_pins_both_task_receipts_and_rechecks(self):
        from tools.codex_assets.feishu_engineering_agent.delivery import ContextDelivery
        from tools.codex_assets.feishu_engineering_agent.models import IntakeRejected
        self.add_second_repo()
        self.intake("om_root",ISSUE)
        self.submit("om_edit_a","修复 应用初始化")
        self.intake("om_select_b","/repo firmware")
        self.submit("om_edit_b","修复 控制器初始化")
        for i,row in enumerate(self.store.pending()):
            bot,job=self.decode(row)
            self.assertTrue(self.store.claim_queued(job.task_id))
            repo=self.config.repository(job.repository)
            cwd=repo.worktree_root/f"task-{job.task_id}"
            branch=f"{repo.branch_prefix}-{job.task_id}"
            sha=("a" if i==0 else "b")*40
            thread=THREAD if i==0 else "01979c6c-0354-7000-8000-000000000002"
            outcome=bot_module.ExecutionResult("fixture",thread_id=thread,thread_cwd=cwd,
                worktree_path=cwd,branch_name=branch,commit_hash=sha)
            self.executor.finish(job,outcome,None)
            self.store.record_result(job.task_id,branch,sha,cwd)
            self.store.complete_with_output(job.task_id, outcome.text)

        def forge(repo):
            observer=mock.Mock()
            observer.discover_delivery.side_effect=lambda branch,sha,workflows: {
                "repo_alias":repo.alias,"repo_full_name":repo.github_repository,
                "head_sha":sha,"branch":branch,"base_branch":repo.github_base_branch,
                "workflows":{w:11 for w in workflows},"pr_number":7,
            }
            return observer

        event,result=self.intake("om_joint","检查联合交付")
        self.assertEqual("joint_delivery",result.intent)
        delivery=ContextDelivery(self.config,self.executor,forge)
        reply=delivery.verify_joint(event,result)
        self.assertIn("不是跨仓集成测试或产品验收",reply)
        self.assertIn("a"*40,reply)
        self.assertIn("b"*40,reply)
        with self.store._connect() as db:
            row=db.execute("SELECT * FROM engineering_context_joint_delivery").fetchone()
            self.assertEqual(2,len(json.loads(row["proof_json"])))
            db.execute("UPDATE tasks SET status='unknown' WHERE repository='firmware'")
        event,result=self.intake("om_joint_again","检查联合交付")
        with self.assertRaises(IntakeRejected):
            delivery.verify_joint(event,result)
        self.runner.run.assert_not_called()

    def test_dedicated_outer_mounts_no_personal_home_or_read_repo_write(self):
        personal=self.root/"personal"
        personal.mkdir()
        (personal/".codex").mkdir()
        (personal/".ssh").mkdir()
        config=dataclasses.replace(self.config,isolation_write_paths=(personal/".codex",self.agent_home))
        runner=bot_module.CodexRunner(config)
        with mock.patch.object(pathlib.Path,"home",return_value=personal),mock.patch.dict(
                os.environ,{"CODEX_HOME":str(personal/".codex")}):
            cmd=runner._isolated_command(self.repo,["exec"],dedicated=True,writable_workdir=False)
        self.assertIn("--unshare-pid",cmd)
        binds=[tuple(cmd[i+1:i+3]) for i,x in enumerate(cmd) if x=="--bind"]
        self.assertEqual([(str(self.agent_home),str(self.agent_home))],binds)
        masks=[cmd[i+1] for i,x in enumerate(cmd) if x=="--tmpfs"]
        self.assertIn(str(personal/".codex"),masks)
        self.assertIn(str(personal/".ssh"),masks)
        self.assertIn(str(self.private),masks)


if __name__=="__main__":
    unittest.main()
