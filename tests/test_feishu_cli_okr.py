from __future__ import annotations

import contextlib
import copy
import io
import json
import pathlib
import tempfile
import types
import unittest
from unittest import mock

from tools.codex_assets import feishu_cli_read as cli, feishu_cli_okr as okr
from tools.codex_assets.feishu_documents import parse_document_url
from tools.codex_assets.feishu_read_evidence import enrich
from tests.test_feishu_cli_read import args, backend

URL = "https://example.feishu.cn/okr/user/111/?okrId=222&periodId=333"
BODY = {"blocks": [{"block_element_type": "paragraph", "paragraph": {"elements": [
    {"paragraph_element_type": "textRun", "text_run": {"text": "提升可靠性"}}]}}]}
CYCLE = {"id": "222", "tenant_cycle_id": "333", "owner": {"owner_type": "user", "user_id": "111"}}
OBJECTIVE = {"id": "444", "cycle_id": "222", "content": BODY, "score": 0.5}
KR = {"id": "555", "objective_id": "444", "content": BODY, "score": 0.7}


def page(items, more=False, token=""):
    return {"items": items, "has_more": more, "page_token": token}


def fake(*pages):
    value = mock.Mock()
    value.read.side_effect = copy.deepcopy(pages)
    return value


class OkrURLTest(unittest.TestCase):
    def test_link_canonicalization_and_legacy_reader_boundary(self):
        ref = parse_document_url(URL + "&from=test#section", allow_okr=True)
        self.assertEqual(("okr", "222", "111", "333"), (ref.kind, ref.token, ref.owner_id, ref.period_id))
        self.assertEqual(URL.replace("/111/", "/111"), ref.url)
        with self.assertRaises(ValueError):
            parse_document_url(URL)
        with self.assertRaises(ValueError):
            parse_document_url(URL, allow_files=True)

    def test_invalid_links_are_rejected_before_credentials(self):
        invalid = [URL.replace("https://", "http://"), URL.replace("example.feishu.cn", "evil.example"),
                   URL.replace("example.feishu.cn", "example.feishu.cn@evil.example"),
                   URL.replace("/111/", "/0/"), URL.replace("/111/", "/-1/"),
                   URL.replace("/111/", "/9223372036854775808/"),
                   URL.replace("okrId=222", "okrId="), URL.replace("okrId=222", "okrId=01"),
                   URL + "&okrId=223", URL + "&periodId=334", URL.replace("periodId=333", "periodId=x"),
                   URL.replace("okrId=222&", ""), URL.replace("periodId=333", "periodId=9223372036854775808"),
                   URL.replace("/111/", "/111/extra/"), URL.replace("example.feishu.cn", "example.feishu.cn:443")]
        for url in invalid:
            with self.subTest(url=url), mock.patch.object(cli, "Backend") as constructor, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(2, cli.run(args(url=url, dry_run=True)))
                constructor.assert_not_called()

    def test_mixed_flags_and_sessions_fail_without_creating_state(self):
        for changes in ({"session": "job"}, {"resume": True}, {"scope": "full"}, {"range": "A1:B2"},
                        {"file_mode": "download"}, {"expected_revision": "3"}, {"format": "cells"},
                        {"action": "status"}, {"okr_page_size": 0}, {"okr_page_size": 101},
                        {"okr_user_id_type": "open_id"}, {"okr_user_id": "unsafe value"},
                        {"okr_objective_id": "-1"}, {"action": "inspect", "okr_objective_id": "444"}):
            with self.subTest(changes=changes), mock.patch.object(cli, "Backend") as constructor, \
                    mock.patch.object(cli, "SessionStore") as store, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(2, cli.run(args(url=URL, dry_run=True, **changes)))
                constructor.assert_not_called()
                store.assert_not_called()
        with self.assertRaises(ValueError):
            cli.validate_input(args(url="https://example.feishu.cn/docx/Doc1", okr_user_id="111"))

    def test_dry_run_is_offline_from_non_repo_entry_contract(self):
        with mock.patch.object(cli, "Backend") as constructor, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(0, cli.run(args(url=URL, dry_run=True)))
        constructor.assert_not_called()
        self.assertFalse(json.loads(out.getvalue())["network_requested"])


class OkrReadTest(unittest.TestCase):
    def test_verified_hierarchy_has_entity_evidence_and_unread_boundary(self):
        value = fake(page([CYCLE]), page([OBJECTIVE]), page([KR]))
        result = enrich(cli.fetch(value, args(url=URL)))
        self.assertTrue(result["data"]["mapping_verified"])
        self.assertEqual((1, 1), (result["data"]["objective_count"], result["data"]["key_result_count"]))
        self.assertEqual(BODY, result["data"]["objectives"][0]["key_results"][0]["content"])
        self.assertEqual(["555"], result["evidence"]["locator"]["key_result_ids"])
        self.assertTrue(result["coverage"]["scope_complete"])
        self.assertFalse(result["receipt"]["whole_resource_complete"])
        self.assertEqual("not-guaranteed", result["coverage"]["snapshot_consistency"])
        self.assertIn("comments", result["evidence"]["limitations"])
        self.assertTrue(result["capabilities"]["content_returned"])
        self.assertEqual(okr.COMMANDS, tuple(x.args[0] for x in value.read.call_args_list))

    def test_inspect_and_catalog_do_not_read_key_result_content(self):
        for action, pages, calls in (("inspect", [page([CYCLE])], 1),
                                     ("catalog", [page([CYCLE]), page([OBJECTIVE])], 2)):
            value = fake(*pages)
            result = enrich(cli.fetch(value, args(url=URL, action=action)))
            self.assertEqual(calls, value.read.call_count)
            self.assertFalse(result["capabilities"]["content_returned"])
            self.assertFalse(result["coverage"]["scope_complete"])
            self.assertFalse(result["receipt"]["whole_resource_complete"])
            if action == "catalog":
                self.assertNotIn("content", result["data"]["objectives"][0])

    def test_cycle_candidates_require_exact_owner_cycle_and_period_before_body(self):
        for row in (dict(CYCLE, id="223"), dict(CYCLE, tenant_cycle_id="334"),
                    dict(CYCLE, owner={"owner_type": "user", "user_id": "112"}),
                    dict(CYCLE, owner={}), dict(CYCLE, tenant_cycle_id=None)):
            value = fake(page([row]))
            with self.subTest(row=row), self.assertRaises(okr.ReadError):
                cli.fetch(value, args(url=URL))
            self.assertEqual(1, value.read.call_count)

    def test_no_cycle_match_does_not_fall_back_to_current_or_first_cycle(self):
        value = fake(page([dict(CYCLE, id="777")]))
        with self.assertRaises(okr.ReadError) as raised:
            cli.fetch(value, args(url=URL))
        self.assertEqual("okr_mapping_unverified", raised.exception.kind)
        self.assertEqual(1, value.read.call_count)

    def test_explicit_api_identity_is_pinned_and_validated(self):
        cycle = dict(CYCLE, owner={"owner_type": "user", "user_id": "ou_explicit"})
        value = fake(page([cycle]))
        result = cli.fetch(value, args(url=URL, action="inspect", okr_user_id="ou_explicit", okr_user_id_type="open_id"))
        self.assertEqual("explicit-api-user-and-returned-cycle", result["data"]["mapping_method"])
        self.assertIn("ou_explicit", value.read.call_args.args[1])
        self.assertIn("open_id", value.read.call_args.args[1])

    def test_all_collections_paginate_and_dedupe_identical_overlap(self):
        other = dict(CYCLE, id="999")
        value = fake(page([other], True, "cycle-next"), page([CYCLE]),
                     page([OBJECTIVE], True, "objective-next"), page([OBJECTIVE]),
                     page([KR], True, "kr-next"), page([KR]))
        result = cli.fetch(value, args(url=URL))
        self.assertEqual(6, value.read.call_count)
        self.assertEqual(1, result["data"]["key_result_count"])
        for index, token in ((1, "cycle-next"), (3, "objective-next"), (5, "kr-next")):
            self.assertIn(token, value.read.call_args_list[index].args[1])

    def test_changed_duplicate_is_not_merged(self):
        value = fake(page([CYCLE], True, "next"), page([dict(CYCLE, score=0.5)]))
        with self.assertRaises(okr.ReadError) as raised:
            cli.fetch(value, args(url=URL))
        self.assertEqual("snapshot_changed", raised.exception.kind)

    def test_pagination_requires_explicit_completion_and_cursor_progress(self):
        bad = ({"items": []}, {"items": [], "has_more": "false"},
               page([], True, "next"), page([CYCLE], True, ""),
               page([CYCLE], True, "\nunsafe"), {"items": {}, "has_more": False})
        for payload in bad:
            value = fake(payload)
            with self.subTest(payload=payload), self.assertRaises(okr.ReadError):
                cli.fetch(value, args(url=URL))
        value = fake(page([CYCLE], True, "same"), page([CYCLE], True, "same"))
        with self.assertRaises(okr.ReadError):
            cli.fetch(value, args(url=URL))
        self.assertEqual(2, value.read.call_count)

    def test_collection_limit_and_total_request_and_byte_limits(self):
        value = fake(*[page([dict(CYCLE, id=str(100 + i))], True, "next" + str(i)) for i in range(10)])
        with self.assertRaises(okr.ReadError) as raised:
            cli.fetch(value, args(url=URL))
        self.assertEqual("coverage_limit", raised.exception.kind)
        self.assertEqual(10, value.read.call_count)
        reader = okr.Reader(fake(page([])), 100)
        reader.calls = okr.MAX_CALLS
        with self.assertRaises(okr.ReadError):
            reader.pages(okr.COMMANDS[0], [])
        reader = okr.Reader(fake(page([dict(CYCLE, ignored="x" * okr.MAX_BYTES)])), 100)
        with self.assertRaises(okr.ReadError):
            reader.pages(okr.COMMANDS[0], [])

    def test_foreign_objective_and_key_result_are_rejected(self):
        for pages in ((page([CYCLE]), page([dict(OBJECTIVE, cycle_id="999")])),
                      (page([CYCLE]), page([OBJECTIVE]), page([dict(KR, objective_id="999")]))):
            with self.subTest(pages=pages), self.assertRaises(okr.ReadError) as raised:
                cli.fetch(fake(*pages), args(url=URL))
            self.assertEqual("resource_mismatch", raised.exception.kind)

    def test_missing_and_malformed_content_cannot_claim_read_complete(self):
        objective = dict(OBJECTIVE)
        objective.pop("content")
        result = cli.fetch(fake(page([CYCLE]), page([objective]), page([])), args(url=URL))
        self.assertFalse(result["coverage"]["scope_complete"])
        with self.assertRaises(okr.ReadError):
            cli.fetch(fake(page([CYCLE]), page([dict(OBJECTIVE, content="bad")])), args(url=URL))

    def test_same_kr_cannot_belong_to_two_objectives_in_one_read(self):
        value = fake(page([CYCLE]), page([OBJECTIVE, dict(OBJECTIVE, id="445")]),
                     page([KR]), page([dict(KR, objective_id="445")]))
        with self.assertRaises(okr.ReadError) as raised:
            cli.fetch(value, args(url=URL))
        self.assertEqual("snapshot_changed", raised.exception.kind)

    def test_redacted_content_does_not_count_as_complete(self):
        body = {"blocks": [{"text": "REDACTED"}]}
        result = enrich(cli.fetch(fake(page([CYCLE]), page([dict(OBJECTIVE, content=body)]), page([])), args(url=URL)))
        self.assertFalse(result["coverage"]["scope_complete"])
        self.assertTrue(result["evidence"]["content_redacted"])

    def test_output_budget_preserves_no_partial_body_and_provides_ids(self):
        huge = {"blocks": [{"text": "x" * 1100}]}
        with self.assertRaises(okr.ReadError) as raised:
            cli.fetch(fake(page([CYCLE]), page([dict(OBJECTIVE, content=huge)]), page([])),
                      args(url=URL, max_chars=1000))
        self.assertEqual("content_budget_exceeded", raised.exception.kind)
        self.assertEqual(["444"], raised.exception.details["objective_ids"])
        self.assertNotIn("x" * 100, json.dumps(raised.exception.details))

    def test_explicit_objective_is_validated_in_cycle_before_key_results(self):
        value = fake(page([CYCLE]), page([OBJECTIVE, dict(OBJECTIVE, id="445")]), page([KR]))
        result = cli.fetch(value, args(url=URL, okr_objective_id="444"))
        self.assertEqual(1, result["data"]["objective_count"])
        self.assertEqual(3, value.read.call_count)
        with self.assertRaises(okr.ReadError):
            cli.fetch(fake(page([CYCLE]), page([OBJECTIVE])), args(url=URL, okr_objective_id="999"))

    def test_scope_error_from_actual_api_shape_is_actionable_and_nonretryable(self):
        value = backend()
        native = types.SimpleNamespace(returncode=3, stdout="", stderr=json.dumps(
            {"ok": False, "identity": "bot", "error": {"type": "authorization",
             "subtype": "app_scope_not_applied", "code": 99991672, "message": "do-not-echo"}}))
        for argv, scope in ((["okr", "cycles", "list"], "okr:okr.period:readonly"),
                            (["okr", "cycle.objectives", "list"], "okr:okr.content:readonly")):
            with mock.patch.object(cli.subprocess, "run", return_value=native), self.assertRaises(okr.ReadError) as raised:
                value.invoke(argv)
            self.assertEqual("application_scope_missing", raised.exception.kind)
            self.assertEqual([scope], raised.exception.details["required_scopes_any_of"])
            self.assertNotIn("do-not-echo", str(raised.exception))

    def test_manifest_code_and_new_policy_have_identical_exact_read_allowlist(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "manifests/feishu_cli.json").read_text())
        lines = (root / manifest["policy_rel"]).read_text().splitlines()
        allow = tuple(line[4:] for line in lines if line.startswith("  - ") and line != "  - bot")
        self.assertEqual(cli.ALLOWED, tuple(manifest["allowed_commands"]))
        self.assertEqual(cli.ALLOWED, allow)
        self.assertFalse(manifest["writes_allowed"])
        self.assertNotIn("okr/+patch", allow)
        value = backend()
        with mock.patch.object(value, "invoke") as invoke:
            for command in ("okr/objectives/delete", "okr/cycle.objectives/create", "okr/+patch"):
                with self.assertRaises(okr.ReadError):
                    value.read(command, [])
            invoke.assert_not_called()


if __name__ == "__main__":
    unittest.main()
