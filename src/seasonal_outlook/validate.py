from __future__ import annotations

from pathlib import Path

from .models import ForecastRun


def validate_forecast(run: ForecastRun) -> list[str]:
    errors = []
    required = {
        run.output_dir / "briefing.md",
        run.output_dir / "tercile_probabilities.json",
        run.output_dir / "tercile_probabilities.csv",
        run.output_dir / "tercile_overview.png",
        run.output_dir / "model_agreement.png",
    }
    for path in required:
        if not path.exists():
            errors.append(f"missing output: {path}")

    seen = set()
    for cell in run.cells:
        key = (cell.region, cell.variable, cell.lead)
        seen.add(key)
        total = cell.posterior.lower + cell.posterior.normal + cell.posterior.upper
        if abs(total - 1.0) > 0.001:
            errors.append(f"probabilities do not sum to 1 for {key}")
        for value in (cell.posterior.lower, cell.posterior.normal, cell.posterior.upper):
            if value < -0.0001 or value > 1.0001:
                errors.append(f"probability out of bounds for {key}")

    for region in ("korea", "east_asia"):
        for variable in ("temperature", "precipitation"):
            for lead in (1, 2, 3):
                if (region, variable, lead) not in seen:
                    errors.append(f"missing forecast cell for {(region, variable, lead)}")
    return errors


def validate_latest_report(report_dir: Path) -> list[str]:
    required = [
        report_dir / "briefing.md",
        report_dir / "tercile_probabilities.json",
        report_dir / "tercile_probabilities.csv",
        report_dir / "tercile_overview.png",
        report_dir / "model_agreement.png",
    ]
    return [f"missing output: {path}" for path in required if not path.exists()]

