from __future__ import annotations

import argparse
import json
import pathlib
import tempfile
import unittest
from unittest import mock

from tools.codex_assets import wechat_archive


class WechatArchiveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="wechat-archive-test-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp))

    def args(self, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "action": "plan",
            "account": ["腾讯技术工程", "阿里云开发者|阿里开发者"],
            "topic": [],
            "seed_url": [],
            "date_from": "2026-01-16",
            "date_to": "2026-07-16",
            "output_dir": self.tmp.as_posix(),
            "plan_file": "",
            "evidence_file": "",
            "discovery_index": "",
            "agent_browser_bin": "",
            "max_queries": 50,
            "max_results_per_query": 10,
            "max_candidates": 50,
            "min_title_similarity": 0.72,
            "delay": 1.0,
            "resume": False,
            "dry_run": False,
            "json": True,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_default_plan_is_bounded_and_preserves_aliases(self) -> None:
        plan = wechat_archive.make_plan(self.args())

        self.assertEqual(42, len(plan["queries"]))
        self.assertEqual(
            ["阿里云开发者", "阿里开发者"], plan["accounts"][1]["aliases"]
        )
        self.assertEqual("persist-never", plan["body_policy"])
        self.assertEqual(0, plan["limits"]["retry_budget_after_access_gate"])

    def test_plan_rejects_unbounded_query_matrix(self) -> None:
        with self.assertRaisesRegex(wechat_archive.WechatArchiveError, "above"):
            wechat_archive.make_plan(
                self.args(account=["账号一", "账号二", "账号三"])
            )

    def test_hermes_index_is_filtered_and_title_deduplicated(self) -> None:
        plan = wechat_archive.make_plan(self.args(topic=["Agent", "MCP"]))
        index = self.tmp / "articles.json"
        index.write_text(
            json.dumps(
                {
                    "one": {
                        "source": "阿里开发者",
                        "title": "Agent Skills 工程实践",
                        "summary": "短摘要",
                        "keyword": "Agent",
                        "url": "https://weixin.sogou.com/link?one",
                    },
                    "two": {
                        "source": "阿里开发者",
                        "title": "Agent-Skills：工程实践",
                        "summary": "包含 MCP 和 Workflow 的更长摘要",
                        "keyword": "MCP",
                        "url": "https://weixin.sogou.com/link?two",
                    },
                    "wrong-account": {
                        "source": "其他账号",
                        "title": "Agent Skills 工程实践",
                        "summary": "不应进入",
                        "url": "https://weixin.sogou.com/link?wrong",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        candidates, raw_count = wechat_archive.load_index_candidates(plan, index)

        self.assertEqual(3, raw_count)
        self.assertEqual(1, len(candidates))
        self.assertEqual("https://weixin.sogou.com/link?two", candidates[0]["_redirect_url"])
        self.assertNotIn("summary", candidates[0])

    def test_verified_record_keeps_hash_but_discards_body_and_signed_url(self) -> None:
        plan = wechat_archive.make_plan(self.args(topic=["Agent", "Hook"]))
        candidate = {
            "candidate_key": "candidate",
            "requested_account": "腾讯技术工程",
            "candidate_title": "Agent Hook 治理",
            "discovery_source": "腾讯技术工程",
            "discovery_query": "腾讯技术工程 Hook",
            "discovery_topic_hits": ["agent", "hook"],
            "_redirect_url": "https://weixin.sogou.com/link?temporary",
            "_fresh": True,
        }
        body = "Agent Hook 权限治理和记忆校验。" * 20
        with mock.patch.object(
            wechat_archive,
            "resolve_redirect",
            return_value="https://mp.weixin.qq.com/s?timestamp=1&signature=secret",
        ), mock.patch.object(
            wechat_archive,
            "fetch_article",
            return_value={
                "title": "Agent Hook 治理",
                "account": "腾讯技术工程",
                "pub_date": "2026-07-16",
                "content": body,
            },
        ):
            record = wechat_archive.verify_candidate(
                plan, mock.Mock(), candidate, min_similarity=0.72
            )

        self.assertEqual("direct-read", record["status"])
        self.assertEqual(64, len(record["content_sha256"]))
        self.assertFalse(record["body_persisted"])
        self.assertFalse(record["temporary_url_persisted"])
        self.assertNotIn("content", record)
        self.assertNotIn("signature=", json.dumps(record, ensure_ascii=False))

    def test_report_and_check_preserve_negative_evidence(self) -> None:
        args = self.args(topic=["Agent"], max_queries=10)
        plan = wechat_archive.make_plan(args)
        wechat_archive.write_json(self.tmp / "plan.json", plan)
        accepted = {
            "schema_version": 1,
            "candidate_key": "accepted",
            "status": "direct-read",
            "canonical_account": "腾讯技术工程",
            "account": "腾讯技术工程",
            "pub_date": "2026-07-16",
            "title": "Agent 工程实践",
            "topic_hits": ["agent"],
            "char_count": 1000,
            "paragraph_count": 10,
            "code_block_count": 0,
            "content_sha256": "a" * 64,
            "source_locator": "https://weixin.sogou.com/weixin?type=2&query=Agent",
            "locator_kind": "sogou-title-query",
            "retrieved_at": "2026-07-16T00:00:00+00:00",
            "body_persisted": False,
            "temporary_url_persisted": False,
        }
        rejected = {
            "schema_version": 1,
            "candidate_key": "rejected",
            "status": "account-mismatch",
            "body_persisted": False,
            "temporary_url_persisted": False,
        }
        wechat_archive.append_jsonl(self.tmp / "evidence.jsonl", accepted)
        wechat_archive.append_jsonl(self.tmp / "evidence.jsonl", rejected)

        self.assertEqual(0, wechat_archive.report(args))
        self.assertEqual(0, wechat_archive.check(args))
        catalog = wechat_archive.load_jsonl(self.tmp / "catalog.jsonl")
        coverage = wechat_archive.load_json(self.tmp / "coverage.json")
        self.assertEqual(1, len(catalog))
        self.assertEqual("review-required", catalog[0]["review_status"])
        self.assertEqual(1, coverage["status_counts"]["account-mismatch"])

    def test_access_gate_detection_is_terminal(self) -> None:
        reason = wechat_archive.access_gate_reason(
            {"href": "https://weixin.sogou.com/antispider/", "text": "请输入验证码"}
        )
        self.assertTrue(reason)

    def test_allow_failure_tolerates_browser_wait_timeout(self) -> None:
        client = object.__new__(wechat_archive.BrowserClient)
        client.binary = "agent-browser"
        with mock.patch.object(
            wechat_archive.subprocess,
            "run",
            side_effect=wechat_archive.subprocess.TimeoutExpired(
                cmd=["agent-browser", "wait"], timeout=20
            ),
        ):
            self.assertEqual(
                "", client.run(["wait", "--load", "networkidle"], allow_failure=True)
            )


if __name__ == "__main__":
    unittest.main()
