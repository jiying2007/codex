from __future__ import annotations

import contextlib
import io
import json
import pathlib
import tempfile
import unittest
from unittest import mock

from tools.codex_assets import check_skills


class CheckSkillsTest(unittest.TestCase):
    def make_repo(
        self,
        body: str,
        manifest_item: dict | None,
        *,
        readme_body: str = "# example-skill",
        openai_body: str = (
            'interface:\n  display_name: "Example"\n  short_description: "Example"\n'
        ),
    ) -> tuple[pathlib.Path, pathlib.Path]:
        temp = tempfile.TemporaryDirectory(prefix="codex-check-skills-")
        self.addCleanup(temp.cleanup)
        root = pathlib.Path(temp.name)
        skill_dir = root / "src/codex-home/vendor/skills/example-skill/1.0.0"
        (skill_dir / "agents").mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: example-skill\n"
            "description: Example skill for validation tests.\n"
            "version: 1.0.0\n"
            "last_updated: 2026-07-15\n"
            "---\n\n"
            f"{body}\n",
            encoding="utf-8",
        )
        (skill_dir / "README.md").write_text(f"{readme_body}\n", encoding="utf-8")
        (skill_dir / "LICENSE").write_text("test\n", encoding="utf-8")
        (skill_dir / "agents/openai.yaml").write_text(openai_body, encoding="utf-8")
        manifest_path = root / "manifests/skills.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(
            json.dumps(
                {"schema_version": 2, "skills": [] if manifest_item is None else [manifest_item]},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return root, manifest_path

    def run_check(self, root: pathlib.Path, manifest_path: pathlib.Path) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(check_skills, "ROOT", root))
            stack.enter_context(
                mock.patch.object(check_skills, "SKILLS_ROOT", root / "src/codex-home/vendor/skills")
            )
            stack.enter_context(mock.patch.object(check_skills, "MANIFEST", manifest_path))
            stack.enter_context(contextlib.redirect_stdout(output))
            result = check_skills.main()
        return result, output.getvalue()

    @staticmethod
    def manifest_item(*, enabled: bool = True, review_status: str = "accepted", tags: list[str] | None = None) -> dict:
        return {
            "name": "example-skill",
            "enabled": enabled,
            "version": "1.0.0",
            "vendor_rel": "vendor/skills/example-skill/1.0.0",
            "target_rel": "skills/example-skill",
            "profiles": [],
            "tags": tags or [],
            "owner": "test-owner",
            "source_repo": "example/repo",
            "source_ref": "1.0.0",
            "source_path": "skills/example-skill/SKILL.md",
            "imported_at": "2026-07-15",
            "review_status": review_status,
        }

    def test_unregistered_source_skill_is_rejected(self) -> None:
        root, manifest_path = self.make_repo("# Example", None)
        result, output = self.run_check(root, manifest_path)
        self.assertEqual(1, result)
        self.assertIn("source skill 未登记到 manifests/skills.json", output)

    def test_disabled_pending_vendor_skill_is_allowed(self) -> None:
        root, manifest_path = self.make_repo(
            "# Example",
            self.manifest_item(enabled=False, review_status="pending"),
        )
        result, output = self.run_check(root, manifest_path)
        self.assertEqual(0, result, output)

    def test_local_skill_rejects_bare_command_in_code_fence(self) -> None:
        root, manifest_path = self.make_repo(
            "```bash\ngit status --short\n```",
            self.manifest_item(tags=["local"]),
        )
        result, output = self.run_check(root, manifest_path)
        self.assertEqual(1, result)
        self.assertIn("local skill 命令必须通过 rtk 执行", output)

    def test_local_skill_rejects_unavailable_script_reference(self) -> None:
        root, manifest_path = self.make_repo(
            "```bash\nrtk bash scripts/missing.sh\n```",
            self.manifest_item(tags=["local"]),
        )
        result, output = self.run_check(root, manifest_path)
        self.assertEqual(1, result)
        self.assertIn("local skill 引用不可用脚本 scripts/missing.sh", output)

    def test_local_skill_readme_rejects_bare_command(self) -> None:
        root, manifest_path = self.make_repo(
            "# Example",
            self.manifest_item(tags=["local"]),
            readme_body="```bash\ncodex exec --full-auto\n```",
        )
        result, output = self.run_check(root, manifest_path)
        self.assertEqual(1, result)
        self.assertIn("README.md", output)
        self.assertIn("local skill 命令必须通过 rtk 执行", output)

    def test_openai_metadata_rejects_legacy_top_level(self) -> None:
        root, manifest_path = self.make_repo(
            "# Example",
            self.manifest_item(),
            openai_body='display_name: "Example"\nshort_description: "Example"\n',
        )
        result, output = self.run_check(root, manifest_path)
        self.assertEqual(1, result)
        self.assertIn("legacy 顶层 interface 字段已退役", output)

    def test_openai_metadata_rejects_redundant_implicit_true(self) -> None:
        root, manifest_path = self.make_repo(
            "# Example",
            self.manifest_item(),
            openai_body=(
                'interface:\n  display_name: "Example"\n  short_description: "Example"\n'
                "policy:\n  allow_implicit_invocation: true\n"
            ),
        )
        result, output = self.run_check(root, manifest_path)
        self.assertEqual(1, result)
        self.assertIn("implicit invocation 必须省略 policy", output)

    def test_openai_metadata_accepts_explicit_only_false(self) -> None:
        root, manifest_path = self.make_repo(
            "# Example",
            self.manifest_item(),
            openai_body=(
                'interface:\n  display_name: "Example"\n  short_description: "Example"\n'
                "policy:\n  allow_implicit_invocation: false\n"
            ),
        )
        result, output = self.run_check(root, manifest_path)
        self.assertEqual(0, result, output)

    def test_openai_metadata_accepts_official_optional_interface_fields(self) -> None:
        root, manifest_path = self.make_repo(
            "# Example",
            self.manifest_item(),
            openai_body=(
                'interface:\n  display_name: "Example"\n  short_description: "Example"\n'
                '  default_prompt: "Use Example."\n'
                '  icon_small: "./assets/example-small.svg"\n'
                '  icon_large: "./assets/example.png"\n'
                '  brand_color: "#101010"\n'
            ),
        )
        result, output = self.run_check(root, manifest_path)
        self.assertEqual(0, result, output)

    def test_openai_metadata_rejects_empty_optional_interface_field(self) -> None:
        root, manifest_path = self.make_repo(
            "# Example",
            self.manifest_item(),
            openai_body=(
                'interface:\n  display_name: "Example"\n  short_description: "Example"\n'
                '  icon_small: ""\n'
            ),
        )
        result, output = self.run_check(root, manifest_path)
        self.assertEqual(1, result)
        self.assertIn("interface.icon_small 必须是非空字符串", output)

    def test_openai_metadata_rejects_unknown_policy_field(self) -> None:
        root, manifest_path = self.make_repo(
            "# Example",
            self.manifest_item(),
            openai_body=(
                'interface:\n  display_name: "Example"\n  short_description: "Example"\n'
                "policy:\n  allow_implicit_invocation: false\n  unexpected: true\n"
            ),
        )
        result, output = self.run_check(root, manifest_path)
        self.assertEqual(1, result)
        self.assertIn("policy 未知字段", output)


if __name__ == "__main__":
    unittest.main()
