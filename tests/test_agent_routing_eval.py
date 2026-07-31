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


def select_skill_route(prompt: str, workflows: list[dict]) -> dict[str, str]:
    candidates: list[tuple[int, str, str, str]] = []
    folded_prompt = prompt.casefold()
    for workflow in workflows:
        for route in workflow.get("routes", []):
            excludes = [str(term).casefold() for term in route.get("exclude_any", [])]
            if any(term and term in folded_prompt for term in excludes):
                continue
            matches = [
                str(term)
                for term in route.get("match_any", [])
                if str(term) and str(term).casefold() in folded_prompt
            ]
            if matches:
                candidates.append(
                    (
                        len(matches),
                        workflow["name"],
                        route["name"],
                        route["primary_skill"],
                    )
                )
    if not candidates:
        return {}
    best_score = max(item[0] for item in candidates)
    best = [item for item in candidates if item[0] == best_score]
    if len(best) != 1:
        return {}
    _, workflow_name, route_name, primary_skill = best[0]
    return {
        "workflow": workflow_name,
        "route": route_name,
        "primary_skill": primary_skill,
    }


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

    def test_skill_route_cases_select_one_primary(self) -> None:
        workflows = read_json(ROOT / "manifests/workflows.json")["workflows"]
        cases = read_json(ROOT / "tests/fixtures/routing_eval/skill_cases.json")["cases"]

        for case in cases:
            with self.subTest(case=case["name"]):
                expected = (
                    {}
                    if not case["expected_workflow"]
                    else {
                        "workflow": case["expected_workflow"],
                        "route": case["expected_route"],
                        "primary_skill": case["expected_primary_skill"],
                    }
                )
                self.assertEqual(
                    expected,
                    select_skill_route(case["prompt"], workflows),
                )


if __name__ == "__main__":
    unittest.main()
