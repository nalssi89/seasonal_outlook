# Seasonal Outlook

Objective East Asia and Korean Peninsula seasonal outlook pipeline for monthly `M+1`, `M+2`, and `M+3` temperature and precipitation guidance.

## What is included

- Python package under `src/seasonal_outlook`
- Configuration in `config/`
- Dated input snapshots in `inputs/`
- Tests in `tests/`
- Representative generated reports in `reports/`
- Final dated PDF outputs in `pdf/`

## What is intentionally excluded from version control

- Local cache and build byproducts such as `__pycache__` and `*.egg-info`
- Re-downloadable or re-trainable large state artifacts under `state/psl_indices/` and `state/objective_forecast/`
- Machine-specific absolute paths and local-only scratch files

## Quick start

```powershell
py -m pip install -e .
py -m unittest discover -s tests -v
py -m seasonal_outlook.cli generate --issue-date 2026-04-16
py -m seasonal_outlook.cli render-climate-factor-report --issue-date 2026-04-16
py -m seasonal_outlook.cli render-c3s-pdf --issue-date 2026-04-15
```

## Main outputs

- `reports/YYYY-MM-DD/briefing.md`
- `reports/YYYY-MM-DD/briefing_ko.md`
- `reports/YYYY-MM-DD/tercile_probabilities.json`
- `reports/YYYY-MM-DD/tercile_probabilities.csv`
- `reports/YYYY-MM-DD/model_agreement.png`
- `pdf/*.pdf`

## Notes for a fresh environment

- `generate` works from the tracked dated inputs in `inputs/dynamic_priors/` and `inputs/climate_factors/`.
- `render-climate-factor-report` fetches current public climate-index sources and writes refreshed report assets.
- `state/` is used for regenerated operational artifacts. See `state/README.md` for details.
