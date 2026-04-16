from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import json
import sys

from .config import load_config
from .climate_factor_report import build_climate_factor_report
from .c3s_pdf import build_c3s_pdf
from .data_inventory import render_data_inventory_markdown
from .observed_symbols import render_observed_symbol_markdown
from .psl_indices import refresh_psl_indices
from .engine import (
    append_results_ledger,
    evaluate_candidate,
    generate_forecast,
    load_scorecard,
    write_probability_exports,
)
from .render import render_markdown, render_model_agreement, render_tercile_overview
from .validate import validate_forecast, validate_latest_report


def _parse_date(value: str | None) -> date:
    if value is None:
        return date.today()
    return date.fromisoformat(value)


def _parse_year_month(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    year_text, month_text = value.split("-", 1)
    return int(year_text), int(month_text)


def _load_objective_forecast():
    from . import objective_forecast

    return objective_forecast


def _print_command_result(result: object) -> None:
    if result is None:
        return
    if isinstance(result, dict):
        print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))
        return
    print(str(result))


def cmd_generate(args: argparse.Namespace) -> int:
    config = load_config()
    run = generate_forecast(config, _parse_date(args.issue_date))
    write_probability_exports(run)
    render_tercile_overview(run)
    render_model_agreement(run)
    render_markdown(run)
    errors = validate_forecast(run)
    append_results_ledger(
        config,
        {
            "kind": "briefing_run",
            "issue_date": run.issue_date.isoformat(),
            "output_dir": str(run.output_dir),
            "source_status": run.source_status,
            "warning_count": len(run.warnings),
            "validation_status": "ok" if not errors else "failed",
        },
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(run.output_dir)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    config = load_config()
    report_dir = config.reports_dir() / _parse_date(args.issue_date).isoformat()
    errors = validate_latest_report(report_dir)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "report_dir": str(report_dir)}, ensure_ascii=True))
    return 0


def cmd_score_candidate(args: argparse.Namespace) -> int:
    config = load_config()
    current = load_scorecard(Path(args.current))
    candidate = load_scorecard(Path(args.candidate))
    result = evaluate_candidate(current, candidate)
    append_results_ledger(
        config,
        {
            "kind": "candidate_score",
            "current_path": args.current,
            "candidate_path": args.candidate,
            **result,
        },
    )
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result["accepted"] else 1


def cmd_render_c3s_pdf(args: argparse.Namespace) -> int:
    config = load_config()
    issue_dir = config.reports_dir() / _parse_date(args.issue_date).isoformat()
    output = build_c3s_pdf(issue_dir)
    print(output)
    return 0


def cmd_render_climate_factor_report(args: argparse.Namespace) -> int:
    config = load_config()
    issue_date = _parse_date(args.issue_date)
    outputs = build_climate_factor_report(config, issue_date)
    print(json.dumps({key: str(value) for key, value in outputs.items()}, ensure_ascii=False, indent=2))
    return 0


def cmd_refresh_psl_indices(args: argparse.Namespace) -> int:
    config = load_config()
    issue_date = _parse_date(args.issue_date)
    outputs = refresh_psl_indices(config, issue_date)
    append_results_ledger(
        config,
        {
            "kind": "psl_indices_refresh",
            "issue_date": issue_date.isoformat(),
            "catalog_json": str(outputs["catalog_json"]),
            "latest_snapshot": str(outputs["latest_snapshot"]),
        },
    )
    print(json.dumps({key: str(value) for key, value in outputs.items()}, ensure_ascii=False, indent=2))
    return 0


def cmd_render_observed_symbol_md(args: argparse.Namespace) -> int:
    temperature_csv = Path(args.temperature_csv)
    precipitation_csv = Path(args.precipitation_csv)
    output_path = Path(args.output)
    result = render_observed_symbol_markdown(temperature_csv, precipitation_csv, output_path)
    print(result)
    return 0


def cmd_build_objective_dataset(args: argparse.Namespace) -> int:
    config = load_config()
    result = _load_objective_forecast().build_objective_dataset(
        config,
        history_end=_parse_year_month(getattr(args, "history_end", None)),
    )
    _print_command_result(result)
    return 0


def cmd_backtest_objective_forecast(args: argparse.Namespace) -> int:
    config = load_config()
    max_origins = getattr(args, "max_origins", None)
    history_end = _parse_year_month(getattr(args, "history_end", None))
    if max_origins is None:
        result = _load_objective_forecast().backtest_objective_forecast(config, history_end=history_end)
    else:
        result = _load_objective_forecast().backtest_objective_forecast(
            config,
            max_origins=max_origins,
            history_end=history_end,
        )
    _print_command_result(result)
    return 0


def cmd_run_objective_forecast(args: argparse.Namespace) -> int:
    config = load_config()
    issue_date = _parse_date(args.issue_date)
    result = _load_objective_forecast().run_objective_forecast(
        config,
        issue_date,
        history_end=_parse_year_month(getattr(args, "history_end", None)),
    )
    _print_command_result(result)
    return 0


def cmd_render_data_inventory_md(args: argparse.Namespace) -> int:
    config = load_config()
    result = render_data_inventory_markdown(
        temperature_csv=Path(args.temperature_csv),
        precipitation_csv=Path(args.precipitation_csv),
        observed_symbol_md=Path(args.observed_symbol_md),
        catalog_json=Path(args.catalog_json),
        tele_json=Path(args.tele_json),
        reports_dir=config.reports_dir(),
        output_path=Path(args.output),
    )
    print(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seasonal outlook pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate a dynamic-model-only briefing")
    generate.add_argument("--issue-date", help="Issue date in YYYY-MM-DD")
    generate.set_defaults(func=cmd_generate)

    check = subparsers.add_parser("check", help="Validate a generated briefing")
    check.add_argument("--issue-date", help="Issue date in YYYY-MM-DD")
    check.set_defaults(func=cmd_check)

    score = subparsers.add_parser("score-candidate", help="Evaluate promotion rules")
    score.add_argument("--current", required=True, help="Current scorecard TOML")
    score.add_argument("--candidate", required=True, help="Candidate scorecard TOML")
    score.set_defaults(func=cmd_score_candidate)

    render_pdf = subparsers.add_parser("render-c3s-pdf", help="Render the C3S slide deck PDF")
    render_pdf.add_argument("--issue-date", required=True, help="Issue date in YYYY-MM-DD")
    render_pdf.set_defaults(func=cmd_render_c3s_pdf)

    render_factor_report = subparsers.add_parser(
        "render-climate-factor-report",
        help="Render a separate climate-factor slide report",
    )
    render_factor_report.add_argument("--issue-date", required=True, help="Issue date in YYYY-MM-DD")
    render_factor_report.set_defaults(func=cmd_render_climate_factor_report)

    refresh_psl = subparsers.add_parser(
        "refresh-psl-indices",
        help="Scrape NOAA PSL climate indices, download raw files, and normalize full-period series",
    )
    refresh_psl.add_argument("--issue-date", help="Issue date in YYYY-MM-DD")
    refresh_psl.set_defaults(func=cmd_refresh_psl_indices)

    render_observed = subparsers.add_parser(
        "render-observed-symbol-md",
        help="Render observed South Korea monthly temperature and precipitation values with -, 0, + symbols",
    )
    render_observed.add_argument(
        "--temperature-csv",
        default="남한_평균기온_월별.csv",
        help="Monthly temperature anomaly CSV",
    )
    render_observed.add_argument(
        "--precipitation-csv",
        default="남한_강수량_월별.csv",
        help="Monthly precipitation CSV",
    )
    render_observed.add_argument(
        "--output",
        default="inputs/observed_symbols/남한_월별_실황_기호화.md",
        help="Output markdown path",
    )
    render_observed.set_defaults(func=cmd_render_observed_symbol_md)

    render_inventory = subparsers.add_parser(
        "render-data-inventory-md",
        help="Render a markdown inventory of observed truth datasets and collected climate indices",
    )
    render_inventory.add_argument(
        "--temperature-csv",
        default="남한_평균기온_월별.csv",
        help="Monthly temperature anomaly CSV",
    )
    render_inventory.add_argument(
        "--precipitation-csv",
        default="남한_강수량_월별.csv",
        help="Monthly precipitation CSV",
    )
    render_inventory.add_argument(
        "--observed-symbol-md",
        default="inputs/observed_symbols/남한_월별_실황_기호화.md",
        help="Observed symbol markdown path",
    )
    render_inventory.add_argument(
        "--catalog-json",
        default="state/psl_indices/catalog.json",
        help="PSL catalog json path",
    )
    render_inventory.add_argument(
        "--tele-json",
        default="state/psl_indices/supplemental/cpc_tele_index_nh_latest.json",
        help="Supplemental tele_index summary json path",
    )
    render_inventory.add_argument(
        "--output",
        default="inputs/data_inventory/수집자료_가용범위_요약.md",
        help="Output markdown path",
    )
    render_inventory.set_defaults(func=cmd_render_data_inventory_md)

    build_objective = subparsers.add_parser(
        "build-objective-dataset",
        help="Build objective forecast training artifacts",
    )
    build_objective.add_argument("--history-end", help="Last target month to include in training/validation, in YYYY-MM")
    build_objective.set_defaults(func=cmd_build_objective_dataset)

    backtest_objective = subparsers.add_parser(
        "backtest-objective-forecast",
        help="Backtest the objective forecast core",
    )
    backtest_objective.add_argument(
        "--max-origins",
        type=int,
        help="Optional cap on expanding-window origins per variable/lead group for faster smoke runs",
    )
    backtest_objective.add_argument("--history-end", help="Last target month to include in training/validation, in YYYY-MM")
    backtest_objective.set_defaults(func=cmd_backtest_objective_forecast)

    run_objective = subparsers.add_parser(
        "run-objective-forecast",
        help="Run the climate-index-only objective forecast core",
    )
    run_objective.add_argument("--issue-date", help="Issue date in YYYY-MM-DD")
    run_objective.add_argument("--history-end", help="Last target month to include in training/validation, in YYYY-MM")
    run_objective.set_defaults(func=cmd_run_objective_forecast)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
