from __future__ import annotations

import json
import pathlib
import shutil
import tempfile
import unittest

from tools.codex_assets.routing_precedence import check


def write_json(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


class RoutingPrecedenceTest(unittest.TestCase):
    def make_repo(self, superpowers_profile: str = "superpowers-compat") -> pathlib.Path:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-routing-test-"))
        self.addCleanup(shutil.rmtree, root)
        write_json(root / "manifests/assets.json", {"schema_version": 2, "default_profile": "team-collab"})
        write_json(
            root / "manifests/profiles.json",
            {
                "schema_version": 2,
                "profiles": [{"name": "team-collab"}, {"name": "superpowers-compat"}],
            },
        )
        skills = [
            "adk-requirements-triage",
            "adk-task-breakdown",
            "adk-systematic-debugging",
            "adk-test-strategy",
            "adk-code-review-loop",
            "adk-commit-pr-quality-gate",
            "adk-verification-before-completion",
            "adk-parallel-agent-governance",
            "adk-worktree-governance",
            "adk-branch-closeout",
            "codex-parallel-collab",
            "worktree-closeout",
        ]
        skill_items = [
            {"name": name, "enabled": True, "profiles": ["team-collab"], "tags": ["adk" if name.startswith("adk-") else "parallel"]}
            for name in skills
        ]
        skill_items.append(
            {
                "name": "writing-plans",
                "enabled": True,
                "profiles": [superpowers_profile],
                "tags": ["superpowers"],
            }
        )
        write_json(root / "manifests/skills.json", {"schema_version": 2, "skills": skill_items})
        write_json(
            root / "manifests/workflows.json",
            {
                "schema_version": 1,
                "workflows": [
                    {
                        "name": "adk-delivery-gate",
                        "enabled": True,
                        "profiles": ["team-collab"],
                        "skills": [
                            "adk-requirements-triage",
                            "adk-task-breakdown",
                            "adk-verification-before-completion",
                            "adk-commit-pr-quality-gate",
                        ],
                    },
                    {
                        "name": "implementation-quality",
                        "enabled": True,
                        "profiles": ["team-collab"],
                        "skills": [
                            "adk-requirements-triage",
                            "adk-task-breakdown",
                            "adk-systematic-debugging",
                            "adk-test-strategy",
                            "adk-code-review-loop",
                            "adk-commit-pr-quality-gate",
                            "adk-verification-before-completion",
                        ],
                    },
                    {
                        "name": "parallel-collab",
                        "enabled": True,
                        "profiles": ["team-collab"],
                        "skills": [
                            "codex-parallel-collab",
                            "adk-parallel-agent-governance",
                            "adk-worktree-governance",
                            "adk-branch-closeout",
                            "worktree-closeout",
                        ],
                    },
                    {
                        "name": "superpowers-compat-fallback",
                        "enabled": True,
                        "profiles": ["superpowers-compat"],
                        "skills": ["writing-plans"],
                    },
                ],
            },
        )
        return root

    def test_passes_when_superpowers_is_compat_only(self) -> None:
        errors, summary = check(self.make_repo())
        self.assertEqual([], errors)
        self.assertEqual([], summary["active_superpowers_in_default"])

    def test_fails_when_superpowers_is_active_in_default_profile(self) -> None:
        errors, _ = check(self.make_repo("team-collab"))
        self.assertTrue(any("仍激活 Superpowers skill" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
