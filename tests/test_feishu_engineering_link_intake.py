"""No-model production SQLite and URL contract tests."""
import pathlib
import tempfile
import unittest

from tools.codex_assets.feishu_codex_bot import StateStore
from tools.codex_assets.feishu_engineering_agent.models import EventConflict, InboundEvent, IntakeRejected
from tools.codex_assets.feishu_engineering_agent.service import LinkContextService, topic_key
from tools.codex_assets.feishu_engineering_agent.sources import parse_source, parse_sources

ISSUE = "https://project.feishu.cn/example-space/issue/detail/1000000001"
STORY = "https://project.feishu.cn/example-space/story/detail/1000000002"
WIKI = "https://tenant-example.feishu.cn/wiki/ExampleWikiToken123"


class SourcesTest(unittest.TestCase):
    def test_link_forms_and_canonicalization(self):
        a = parse_source(ISSUE+"?from=copy")
        self.assertEqual(("example-space","issue","defect","1000000001",ISSUE),
                         (a.space,a.url_type,a.kind,a.item_id,a.url))
        self.assertEqual("requirement",parse_source(STORY).kind)
        self.assertEqual(WIKI,parse_source(WIKI+"?from=from_copylink").url)
        self.assertEqual("requirement",parse_source("https://www.tapd.cn/123/prong/stories/view/456").kind)
        self.assertEqual("defect",parse_source("https://tapd.cn/123/bugtrace/bugs/view/789").kind)
        self.assertEqual(2,len(parse_sources(ISSUE+" "+ISSUE+"?from=x "+WIKI)))
    def test_no_lookalikes_or_unsafe_paths(self):
        for url in (ISSUE.replace("https://","http://"),
                    ISSUE.replace("project.feishu.cn","project.feishu.cn.evil.test"),
                    ISSUE.replace("project.feishu.cn","project.feishu.cn@evil.test"),
                    ISSUE.replace("project.feishu.cn","project.feishu.cn:443"),
                    ISSUE.replace("issue","%69ssue"),
                    ISSUE.replace("issue","custom"),
                    ISSUE+"x"):
            with self.subTest(url=url),self.assertRaises(IntakeRejected):
                parse_source(url)
        with self.assertRaises(IntakeRejected):
            parse_sources(ISSUE+" "+STORY)
    def test_topic_identity(self):
        self.assertEqual("root:om_root",topic_key("om_root"))
        self.assertEqual("root:om_root",topic_key("om_reply","om_root","omt_a","om_parent"))
        self.assertEqual("thread:omt_a",topic_key("om_reply",thread_id="omt_a"))
        with self.assertRaises(IntakeRejected):
            topic_key("om_reply",parent_id="om_parent")


class ContextTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=pathlib.Path(tmp.name)/"bot.sqlite3"
        self.service=LinkContextService(StateStore(self.path))
        self.allowed={"robot-app","codex"}
        self.routes={"feishu_project:example-space":["robot-app"]}
    def event(self,mid,text,actor="ou_owner",tenant="tenant1"):
        return InboundEvent("feishu_message",tenant,"oc_chat",actor,mid,text)
    def handle(self,mid,text,topic="root:om_root",actor="ou_owner",tenant="tenant1",allowed=None,routes=None):
        return self.service.handle(self.event(mid,text,actor,tenant),topic,
            self.allowed if allowed is None else allowed,self.routes if routes is None else routes)
    def test_source_note_replay_restart_and_isolation(self):
        original=self.handle("om_root",ISSUE+" "+WIKI)
        self.assertIn("研发仓库：robot-app",original.reply)
        self.assertIsNone(self.handle("om_root",ISSUE+" "+WIKI).reply)
        with self.assertRaises(EventConflict):
            self.handle("om_root",ISSUE+" changed")
        self.handle("om_note","private reproduction detail")
        self.service=LinkContextService(StateStore(self.path))
        result=self.handle("om_status","/status")
        self.assertIn("补充消息引用：1",result.reply)
        self.assertFalse(self.handle("om_other","/status",actor="ou_other").consumed)
        self.assertFalse(self.handle("om_tenant","/status",tenant="tenant2").consumed)
        self.assertFalse(self.handle("om_topic","/status",topic="root:om_other").consumed)
        with self.service.store._connect() as db:
            self.assertEqual(2,db.execute("SELECT COUNT(*) FROM engineering_context_sources").fetchone()[0])
            self.assertEqual(0,db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])
            self.assertNotIn("private reproduction detail"," ".join(db.iterdump()))
    def test_no_implicit_wrong_repo_or_second_workitem(self):
        a=self.handle("om_root",ISSUE,allowed={"codex"},routes={})
        self.assertIn("待定位",a.reply)
        with self.assertRaises(IntakeRejected):
            self.handle("om_second",STORY)
        with self.assertRaises(IntakeRejected):
            self.handle("om_forbidden","/repo secret")
        self.assertIn("研发仓库：codex",self.handle("om_repo","/repo codex").reply)
        with self.assertRaises(IntakeRejected):
            self.handle("om_revoked","/status",allowed={"robot-app"})
        self.assertIn("未取消其他话题",self.handle("om_cancel","/cancel").reply)
    def test_doc_alone_and_multiple_sources(self):
        a=self.handle("om_root",WIKI,allowed={"codex"})
        self.assertIn("文档驱动",a.reply)
        self.assertIn("研发仓库：codex",a.reply)
        self.assertIn("需求 #1000000002",self.handle("om_story",STORY).reply)


if __name__ == "__main__":
    unittest.main()
