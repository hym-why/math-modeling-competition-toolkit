from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from score_problems import score_rows  # noqa: E402


def row(problem: str, scores: tuple[int, int, int, int, int, int]) -> dict[str, str]:
    keys = (
        "data_score",
        "coding_score",
        "metric_score",
        "writing_score",
        "team_score",
        "innovation_score",
    )
    item = {"problem": problem, "veto": "no"}
    item.update({key: str(value) for key, value in zip(keys, scores)})
    return item


class ProblemScoreTests(unittest.TestCase):
    def test_ranks_highest_non_veto_first(self) -> None:
        ranked = score_rows(
            [
                row("A", (4, 4, 4, 4, 4, 4)),
                row("B", (5, 5, 5, 5, 5, 5)),
                row("C", (4, 5, 5, 5, 5, 5)),
            ]
        )
        self.assertEqual([item["problem"] for item in ranked], ["B", "C", "A"])

    def test_data_or_team_score_one_triggers_veto(self) -> None:
        ranked = score_rows([row("A", (1, 5, 5, 5, 5, 5)), row("B", (5, 3, 3, 3, 3, 3))])
        self.assertEqual(ranked[0]["problem"], "B")
        self.assertEqual(ranked[1]["veto"], "yes")

    def test_invalid_score_fails(self) -> None:
        with self.assertRaises(ValueError):
            score_rows([row("A", (0, 5, 5, 5, 5, 5))])


if __name__ == "__main__":
    unittest.main()
