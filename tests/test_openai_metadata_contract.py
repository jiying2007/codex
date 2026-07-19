from __future__ import annotations

import pathlib
import tempfile
import unittest

from tools.codex_assets.check_skills import validate_openai_metadata


class OpenAIMetadataContractTests(unittest.TestCase):
    def validate(self, content: str) -> list[str]:
        with tempfile.TemporaryDirectory(prefix="codex-openai-metadata-") as temp:
            path = pathlib.Path(temp) / "openai.yaml"
            path.write_text(content, encoding="utf-8")
            errors: list[str] = []
            validate_openai_metadata(path, errors)
            return errors

    def test_nested_interface_is_valid(self) -> None:
        errors = self.validate(
            "interface:\n"
            "  display_name: Example\n"
            "  short_description: Example skill\n"
        )
        self.assertEqual(errors, [])

    def test_official_optional_interface_fields_are_valid(self) -> None:
        errors = self.validate(
            "interface:\n"
            "  display_name: Example\n"
            "  short_description: Example skill\n"
            "  default_prompt: Run the example\n"
            "  icon_small: ./assets/icon-small.svg\n"
            "  icon_large: ./assets/icon-large.png\n"
            "  brand_color: '#0A84FF'\n"
        )
        self.assertEqual(errors, [])

    def test_legacy_top_level_interface_fields_fail(self) -> None:
        errors = self.validate(
            "display_name: Example\n"
            "short_description: Example skill\n"
        )
        self.assertTrue(any("legacy 顶层 interface 字段已退役" in item for item in errors))

    def test_redundant_implicit_true_fails(self) -> None:
        errors = self.validate(
            "interface:\n"
            "  display_name: Example\n"
            "  short_description: Example skill\n"
            "policy:\n"
            "  allow_implicit_invocation: true\n"
        )
        self.assertTrue(any("implicit invocation 必须省略 policy" in item for item in errors))

    def test_explicit_only_false_is_valid(self) -> None:
        errors = self.validate(
            "interface:\n"
            "  display_name: Example\n"
            "  short_description: Example skill\n"
            "policy:\n"
            "  allow_implicit_invocation: false\n"
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
