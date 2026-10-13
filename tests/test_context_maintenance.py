from __future__ import annotations

import hashlib
import pathlib
import json
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools.codex_assets.context_maintenance import maintenance_diagnostic, merge_context_config, parse_config, reusable_context_input
from tools.codex_assets.core import CodexAssetError, build_repo, plan_apply, render_config, validate_apply_plan
from tools.codex_assets.cli import cmd_apply

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANAGED = 'model_auto_compact_token_limit = 100000\nmodel_auto_compact_token_limit_scope = "total"\n'


class ContextConfigTests(unittest.TestCase):
    def test_reuse_is_explicit_hash_bound_and_never_falls_back_after_input_change(self):
        self.assertEqual(reusable_context_input({}), '')
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'local.toml'
            path.write_text('model = "local"\n')
            receipt = {'context_config_input_path': str(path),
                       'context_config_input_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            self.assertEqual(reusable_context_input(receipt), str(path))
            path.write_text('model = "changed"\n')
            with self.assertRaisesRegex(ValueError, 'changed'):
                reusable_context_input(receipt)
            path.unlink()
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                reusable_context_input(receipt)
            with self.assertRaisesRegex(ValueError, 'explicit input path'):
                reusable_context_input({'context_config_input_sha256': receipt['context_config_input_sha256']})

    def test_overlay_preserves_model_permissions_trust_and_multiline_values(self):
        existing = '''# local settings
model = "local-model"
developer_instructions = """hello
world"""
model_auto_compact_token_limit = 240000 # old
'model_auto_compact_token_limit_scope' = "body_after_prefix"
approval_policy = "on-request"
[sandbox_workspace_write]
network_access = false
writable_roots = ["/private/work"]
[projects."/private/work"]
trust_level = "trusted"
[notice]
hide_model_migration_prompt = true
'''
        before = parse_config(existing)
        after = parse_config(merge_context_config(existing, MANAGED))
        self.assertEqual(after.pop('model_auto_compact_token_limit'), 100000)
        self.assertEqual(after.pop('model_auto_compact_token_limit_scope'), 'total')
        before.pop('model_auto_compact_token_limit')
        before.pop('model_auto_compact_token_limit_scope')
        self.assertEqual(before, after)
        self.assertTrue(merge_context_config(existing, MANAGED).startswith('# local settings'))

    def test_no_final_newline_and_idempotence(self):
        once = merge_context_config('model = "local"', MANAGED)
        self.assertEqual(once, merge_context_config(once, MANAGED))

    def test_invalid_toml_and_non_total_source_fail_closed(self):
        for existing, source in [('model = [', MANAGED), ('', 'model_auto_compact_token_limit = true\n'),
                                 ('', MANAGED.replace('total', 'body_after_prefix'))]:
            with self.subTest(existing=existing, source=source), self.assertRaises(ValueError):
                merge_context_config(existing, source)

    def test_multiline_ambiguous_root_key_is_rejected_without_mutating_input(self):
        existing = 'developer_instructions = """hello\nmodel_auto_compact_token_limit = 7\nworld"""\n'
        with self.assertRaises(ValueError):
            merge_context_config(existing, MANAGED)

    def test_render_overlay_uses_source_context_keys_only(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            source, build, local = base / 'source', base / 'build', base / 'local.toml'
            (source / 'config').mkdir(parents=True)
            (source / 'config/base.toml').write_text('model = "template"\n' + MANAGED)
            local.write_text('model = "local"\n[features]\nmemories = false\n')
            repo = SimpleNamespace(source=source, manifests_dir=base / 'manifests', assets={'config': {'base': 'config/base.toml'}})
            with patch('tools.codex_assets.core.render_mcp_config', return_value='[mcp_servers.new]\nenabled = true\n'):
                render_config(repo, build, 'default', context_config_from=local)
            config = parse_config((build / 'config.toml').read_text())
            self.assertEqual(config['model'], 'local')
            self.assertFalse(config['features']['memories'])
            self.assertNotIn('mcp_servers', config)
            self.assertEqual(config['model_auto_compact_token_limit'], 100000)
            self.assertEqual(local.read_text(), 'model = "local"\n[features]\nmemories = false\n')
            local.write_text('model = [')
            with self.assertRaises(CodexAssetError):
                render_config(repo, build, 'default', context_config_from=local)

    def test_managed_default_precedes_observed_window_guard(self):
        config = parse_config((ROOT / 'src/codex-home/config/base.toml').read_text())
        self.assertLess(config['model_auto_compact_token_limit'], 258400 * .5)
        self.assertEqual(config['model_auto_compact_token_limit_scope'], 'total')
        self.assertNotIn('model_context_window', config)


class ImplicitRebuildTests(unittest.TestCase):
    def test_smoke_restore_preserves_hash_bound_rules_and_refuses_changed_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root, local = self.fixture(directory)
            rules = root / 'local-rules.json'
            base = (root / 'src/codex-home/rules/default.rules').read_bytes()
            rules.write_text(json.dumps({'schema_version': 1, 'profile': 'default',
                'target': 'rules/default.rules', 'base_sha256': hashlib.sha256(base).hexdigest(),
                'extra_rules': ['prefix_rule(pattern=["fixture-command"], decision="prompt")']}))
            build = build_repo(root, 'default', context_config_from=str(local),
                local_rules_arg=str(rules), local_rules_sha256=hashlib.sha256(rules.read_bytes()).hexdigest())
            before = (build / 'rules/default.rules').read_bytes()
            build_repo(root, 'default', reuse_context_input=True, reuse_machine_inputs=True)
            self.assertEqual((build / 'rules/default.rules').read_bytes(), before)
            self.assertEqual(parse_config((build / 'config.toml').read_text())['model'], 'fixture-local-model')
            state = (build / 'control/state/managed-files.json').read_bytes()
            rules.write_text('{}')
            with self.assertRaisesRegex(CodexAssetError, 'hash mismatch'):
                build_repo(root, 'default', reuse_context_input=True, reuse_machine_inputs=True)
            self.assertEqual((build / 'control/state/managed-files.json').read_bytes(), state)

    def fixture(self, directory):
        root = pathlib.Path(directory)
        shutil.copytree(ROOT / 'src', root / 'src', symlinks=True)
        shutil.copytree(ROOT / 'manifests', root / 'manifests')
        local = root / 'local.toml'
        local.write_text('model = "fixture-local-model"\napproval_policy = "never"\n' + MANAGED)
        return root, local

    def args(self, root):
        return SimpleNamespace(root=str(root), plan='', build='', run_build=True,
                               dry_run=False, profile='', target=str(root / 'target'),
                               backup_root='', overwrite=False, prune_stale=False, plan_out='')

    def test_default_apply_rebuild_preserves_config_and_verified_rules_before_target_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root, local = self.fixture(directory)
            rules = root / 'local-rules.json'
            base = (root / 'src/codex-home/rules/default.rules').read_bytes()
            rules.write_text(json.dumps({'schema_version': 1, 'profile': 'default',
                'target': 'rules/default.rules', 'base_sha256': hashlib.sha256(base).hexdigest(),
                'extra_rules': ['prefix_rule(pattern=["fixture-command"], decision="prompt")']}))
            build = build_repo(root, 'default', context_config_from=str(local),
                               local_rules_arg=str(rules), local_rules_sha256=hashlib.sha256(rules.read_bytes()).hexdigest())
            before = (build / 'config.toml').read_bytes()
            with patch('tools.codex_assets.cli.plan_apply', side_effect=RuntimeError('before-target-write')):
                with self.assertRaisesRegex(RuntimeError, 'before-target-write'):
                    cmd_apply(self.args(root))
            self.assertEqual((build / 'config.toml').read_bytes(), before)
            self.assertIn('fixture-command', (build / 'rules/default.rules').read_text())
            receipt = json.loads((build / 'control/state/managed-files.json').read_text())
            self.assertEqual(receipt['context_config_input_path'], str(local))
            self.assertIn('exec_rules', receipt['machine_inputs'])
            self.assertFalse((root / 'target').exists())

    def test_changed_context_refuses_implicit_rebuild_without_replacing_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root, local = self.fixture(directory)
            build = build_repo(root, 'default', context_config_from=str(local))
            before = (build / 'control/state/managed-files.json').read_bytes()
            local.write_text('model = "changed"\n')
            with patch('tools.codex_assets.cli.plan_apply') as plan:
                with self.assertRaisesRegex(ValueError, 'changed'):
                    cmd_apply(self.args(root))
                plan.assert_not_called()
            self.assertEqual((build / 'control/state/managed-files.json').read_bytes(), before)
            self.assertFalse((root / 'target').exists())

    def test_changed_input_invalidates_plan_and_plan_creation_before_target_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root, local = self.fixture(directory)
            build = build_repo(root, 'default', context_config_from=str(local))
            plan = plan_apply(root, build, root / 'target', root / 'backup', False, False)
            local.write_text('model = "changed"\n')
            with self.assertRaisesRegex(CodexAssetError, 'context input invalid'):
                validate_apply_plan(plan)
            with self.assertRaisesRegex(CodexAssetError, 'context input invalid'):
                plan_apply(root, build, root / 'target', root / 'backup', False, False)
            self.assertFalse((root / 'target').exists())


class MaintenanceDiagnosticTests(unittest.TestCase):
    def diagnostic(self, config, decision=None, window=258400):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'config.toml'
            if config is not None:
                path.write_text(config)
            return maintenance_diagnostic({'usage': {'context_window': window}},
                decision or {'recommended_action': 'compact', 'reasons': ['context-pressure']},
                {'context': {'compact_ratio': .5}}, path)

    def test_pressure_requires_maintenance_without_claiming_compaction_or_gate_override(self):
        result = self.diagnostic(MANAGED)
        self.assertTrue(result['required'])
        self.assertEqual(result['threshold_alignment'], 'before-policy-guard')
        self.assertEqual(result['policy_guard_tokens'], 129200)
        for key in ('effective_runtime_config_verified', 'compaction_completion_verified',
                    'repeat_polling_is_progress', 'gate_override'):
            self.assertFalse(result[key])

    def test_stop_stale_and_token_critical_do_not_become_context_maintenance(self):
        for action, reason in [('stop', 'token-budget-exhausted'), ('replan', 'heartbeat-stale'),
                               ('compact', 'token-budget-critical')]:
            with self.subTest(action=action, reason=reason):
                result = self.diagnostic(MANAGED, {'recommended_action': action, 'reasons': [reason]})
                self.assertFalse(result['required'])
                self.assertEqual(result['next_action'], 'follow-policy-decision')

    def test_missing_invalid_unknown_and_smaller_window_are_explicit(self):
        self.assertEqual(self.diagnostic(None)['native_config_status'], 'absent')
        self.assertEqual(self.diagnostic('broken = [')['native_config_status'], 'unreadable-or-invalid')
        self.assertEqual(self.diagnostic(MANAGED, window=0)['threshold_alignment'], 'unknown')
        self.assertEqual(self.diagnostic(MANAGED, window=100000)['threshold_alignment'], 'at-or-after-policy-guard')
        self.assertEqual(self.diagnostic(MANAGED.replace('total', 'body_after_prefix'))['threshold_alignment'], 'unknown')


if __name__ == '__main__':
    unittest.main()
