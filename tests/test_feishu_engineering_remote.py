"""Exercise actual remote queue, exact CLI binding and cancel without a paid turn."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pathlib
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
            commit_enabled=True,artifact_upload_enabled=False,
            artifact_roots=(),artifact_extensions=frozenset(),artifact_max_bytes=0,
            verification_commands=(),
        )
        self.config = bot_module.BotConfig(
            app_id="cli_test",app_secret="fixture-secret",target_chat_id="oc_test",
            bot_name="研发助手",repositories={"robot-app":policy},
            default_repo="robot-app",allowed_open_ids=frozenset(("ou_owner","ou_other")),
            state_db=self.private/"bot.sqlite3",lock_file=self.private/"bot.lock",
            manual_workitems_enabled=True,agent_intake_enabled=True,
            link_repositories={"feishu_project:example-space":("robot-app",)},
            agent_billing_source="external_api_key",agent_codex_home=self.agent_home,
            agent_openai_api_key="fixture-api-not-real",
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
        result=self.service.handle(event,topic,{"robot-app"},self.config.link_repositories)
        return event,result

    def submit(self,mid,text,topic="root:om_root"):
        event,result=self.intake(mid,text,topic)
        return self.executor.submit(event,result)

    def latest(self):
        return self.store.pending()[-1]

    def decode(self,row):
        bot=bot_module.FeishuCodexBot(self.config,self.transport,self.runner,self.store)
        return bot,bot._decode_job(self.spool.get(row["id"]),row)

    def complete(self,row,thread=THREAD):
        bot,job=self.decode(row)
        self.assertTrue(self.store.claim_queued(job.task_id))
        result=bot_module.ExecutionResult("fixture",thread_id=thread,thread_cwd=self.repo)
        self.executor.finish(job,result,None)
        self.store.update_task(job.task_id,"completed")
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
        self.submit("om_continue","继续推进")
        row=self.latest()
        bot,job=self.decode(row)
        target=self.executor.resume_target(job)
        self.assertEqual(THREAD,target.thread_id)
        self.assertEqual(first.task_id,target.root_task_id)
        self.assertEqual(self.repo,target.working_directory)
        self.assertTrue(self.store.claim_queued(job.task_id))
        self.store.update_task(job.task_id,"unknown")
        event,result=self.intake("om_again","继续推进")
        with self.assertRaisesRegex(bot_module.FeishuCodexError,"未知"):
            self.executor.submit(event,result)
        self.runner.run.assert_not_called()

    def test_no_billing_no_read_and_no_legacy_fallback(self):
        config=dataclasses.replace(self.config,agent_intake_enabled=False)
        ex=EngineeringExecutor(config,self.store,self.spool,self.transport,self.runner)
        event,result=self.intake("om_root","分析 "+ISSUE+" 复现：输入异常")
        with self.assertRaisesRegex(bot_module.FeishuCodexError,"独立模型"):
            ex.submit(event,result)
        self.assertEqual([],self.store.pending())
        self.transport.read_engineering_note.assert_not_called()
        self.runner.run.assert_not_called()

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
        config=dataclasses.replace(self.config,agent_openai_api_key="changed-fixture-key")
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

    def test_prior_message_read_failure_and_verified_doc_binding(self):
        self.intake("om_root",ISSUE)
        self.intake("om_note","复现：电源重启后异常")
        self.transport.read_engineering_note.side_effect=RuntimeError("no permission")
        event,result=self.intake("om_read","分析一下")
        with self.assertRaisesRegex(bot_module.FeishuCodexError,"无法按原身份"):
            self.executor.submit(event,result)
        self.assertEqual([],self.store.pending())
        self.transport.read_engineering_note.side_effect=None
        self.transport.read_engineering_note.return_value="复现：电源重启后异常"
        event,result=self.intake("om_read2","分析一下")
        self.executor.submit(event,result)
        bot,job=self.decode(self.latest())
        self.assertIn("电源重启后异常",job.task)
        self.assertEqual("om_note",self.transport.read_engineering_note.call_args.args[0])
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
