from __future__ import annotations

from datetime import date
from pathlib import Path
import unittest

from seasonal_outlook.config import load_config
from seasonal_outlook.engine import evaluate_candidate, generate_forecast
from seasonal_outlook.models import CandidateScorecard


ROOT = Path(__file__).resolve().parents[1]


class ForecastPipelineTests(unittest.TestCase):
    def test_generate_forecast_has_expected_cells(self) -> None:
        config = load_config(ROOT)
        run = generate_forecast(config, date(2026, 4, 15))
        self.assertEqual(len(run.cells), 12)
        cell = [
            item
            for item in run.cells
            if item.region == "korea" and item.variable == "temperature" and item.lead == 1
        ][0]
        self.assertAlmostEqual(
            cell.posterior.lower + cell.posterior.normal + cell.posterior.upper,
            1.0,
            places=4,
        )
        self.assertEqual(cell.dominant_category, "upper")

    def test_candidate_promotion_rule(self) -> None:
        current = CandidateScorecard(0.45, 0.18, 0.13, 0.72)
        candidate = CandidateScorecard(0.462, 0.15, 0.12, 0.74)
        result = evaluate_candidate(current, candidate)
        self.assertTrue(result["accepted"])

    def test_candidate_rejection_on_precip_drop(self) -> None:
        current = CandidateScorecard(0.45, 0.18, 0.13, 0.72)
        candidate = CandidateScorecard(0.50, 0.20, 0.06, 0.74)
        result = evaluate_candidate(current, candidate)
        self.assertFalse(result["accepted"])

    def test_missing_issue_date_falls_back_to_latest_snapshot(self) -> None:
        config = load_config(ROOT)
        run = generate_forecast(config, date(2026, 4, 16))
        self.assertEqual(run.source_status, "delayed")
        self.assertEqual(len(run.cells), 12)


if __name__ == "__main__":
    unittest.main()
