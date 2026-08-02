from __future__ import annotations

import pathlib
import shutil
import sqlite3
import tempfile
import unittest

from tools.codex_assets.usage_dashboard import fixed_context_projection, load_goals


class UsageDashboardTest(unittest.TestCase):
    def make_db(self) -> pathlib.Path:
        handle = tempfile.NamedTemporaryFile(prefix="codex-usage-", suffix=".sqlite", delete=False)
        handle.close()
        path = pathlib.Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def test_missing_thread_goals_is_reported_as_unavailable(self) -> None:
        path = self.make_db()
        with sqlite3.connect(path) as db:
            db.execute("create table threads (id text primary key)")
        goals, available = load_goals(path)
        self.assertEqual({}, goals)
        self.assertFalse(available)

    def test_thread_goals_are_loaded_when_table_exists(self) -> None:
        path = self.make_db()
        with sqlite3.connect(path) as db:
            db.execute(
                """
                create table thread_goals (
                    thread_id text,
                    status text,
                    token_budget integer,
                    tokens_used integer,
                    time_used_seconds integer,
                    updated_at_ms integer
                )
                """
            )
            db.execute(
                "insert into thread_goals values (?, ?, ?, ?, ?, ?)",
                ("thread-1", "active", 1000, 120, 5, 1),
            )
        goals, available = load_goals(path)
        self.assertTrue(available)
        self.assertEqual(120, goals["thread-1"].tokens_used)

    def test_fixed_context_projection_attributes_instruction_layers(self) -> None:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-context-cost-"))
        self.addCleanup(shutil.rmtree, root)
        codex_home = root / "codex-home"
        cwd = root / "workspace/subdir"
        codex_home.mkdir(parents=True)
        cwd.mkdir(parents=True)
        (codex_home / "AGENTS.md").write_text("g" * 8)
        (root / "workspace/AGENTS.md").write_text("w" * 5)

        payload = fixed_context_projection(codex_home, cwd)
        self.assertEqual("estimate", payload["status"])
        self.assertEqual(13, payload["total_bytes"])
        self.assertEqual(4, payload["estimated_tokens"])
        self.assertEqual(2, len(payload["components"]))
        self.assertIn("tool-results", payload["excluded_variable_costs"])


if __name__ == "__main__":
    unittest.main()
