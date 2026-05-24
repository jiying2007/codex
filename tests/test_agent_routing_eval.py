from __future__ import annotations

import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def read_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def select_recipe(prompt: str, recipes: list[dict]) -> str:
    matches: list[str] = []
    for item in recipes:
        examples = item.get("trigger_examples", [])
        if any(example and example in prompt for example in examples):
            matches.append(item["name"])
    if len(matches) != 1:
        return ""
    return matches[0]


class AgentRoutingEvalTest(unittest.TestCase):
    def test_workflow_recipe_positive_cases_route_to_expected_recipe(self) -> None:
        recipes = read_json(ROOT / "manifests/workflow_recipes.json")["workflow_recipes"]
        cases = read_json(ROOT / "tests/fixtures/routing_eval/workflow_cases.json")["cases"]

        for case in cases:
            with self.subTest(case=case["name"]):
                self.assertEqual(case["expected_recipe"], select_recipe(case["prompt"], recipes))

    def test_workflow_recipe_negative_examples_do_not_route_to_self(self) -> None:
        recipes = read_json(ROOT / "manifests/workflow_recipes.json")["workflow_recipes"]

        for item in recipes:
            for prompt in item.get("negative_examples", []):
                with self.subTest(recipe=item["name"], prompt=prompt):
                    self.assertNotEqual(item["name"], select_recipe(prompt, recipes))


if __name__ == "__main__":
    unittest.main()
