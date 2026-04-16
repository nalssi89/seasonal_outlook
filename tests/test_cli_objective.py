from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path
import json
import sys
import types
import unittest
from unittest.mock import patch

from seasonal_outlook import cli


class ObjectiveCliTests(unittest.TestCase):
    def test_parser_registers_objective_commands(self) -> None:
        parser = cli.build_parser()

        build_args = parser.parse_args(["build-objective-dataset"])
        self.assertIs(build_args.func, cli.cmd_build_objective_dataset)

        backtest_args = parser.parse_args(["backtest-objective-forecast"])
        self.assertIs(backtest_args.func, cli.cmd_backtest_objective_forecast)

        run_args = parser.parse_args(["run-objective-forecast", "--issue-date", "2026-04-15"])
        self.assertIs(run_args.func, cli.cmd_run_objective_forecast)

    def test_build_and_backtest_commands_use_lazy_module(self) -> None:
        calls: list[tuple[str, object]] = []

        def build_objective_dataset(config: object, history_end: tuple[int, int] | None = None) -> dict[str, Path]:
            calls.append(("build", config))
            return {"dataset_md": Path("inputs/objective/dataset.md")}

        def backtest_objective_forecast(
            config: object,
            max_origins: int | None = None,
            history_end: tuple[int, int] | None = None,
        ) -> dict[str, Path]:
            calls.append(("backtest", config))
            return {"summary_md": Path("inputs/objective/backtest.md")}

        fake_module = types.ModuleType("seasonal_outlook.objective_forecast")
        fake_module.build_objective_dataset = build_objective_dataset
        fake_module.backtest_objective_forecast = backtest_objective_forecast
        fake_config = object()

        with patch.object(cli, "load_config", return_value=fake_config), patch.dict(
            sys.modules,
            {"seasonal_outlook.objective_forecast": fake_module},
            clear=False,
        ):
            build_buffer = StringIO()
            with redirect_stdout(build_buffer):
                build_exit = cli.cmd_build_objective_dataset(argparse.Namespace())
            self.assertEqual(build_exit, 0)
            build_output = json.loads(build_buffer.getvalue())
            self.assertEqual(build_output["dataset_md"], str(Path("inputs/objective/dataset.md")))

            backtest_buffer = StringIO()
            with redirect_stdout(backtest_buffer):
                backtest_exit = cli.cmd_backtest_objective_forecast(argparse.Namespace(max_origins=None, history_end=None))
            self.assertEqual(backtest_exit, 0)
            backtest_output = json.loads(backtest_buffer.getvalue())
            self.assertEqual(backtest_output["summary_md"], str(Path("inputs/objective/backtest.md")))

        self.assertEqual(calls, [("build", fake_config), ("backtest", fake_config)])

    def test_run_objective_command_parses_issue_date(self) -> None:
        calls: list[tuple[object, object]] = []

        def run_objective_forecast(
            config: object,
            issue_date: date,
            history_end: tuple[int, int] | None = None,
        ) -> dict[str, Path]:
            calls.append((config, issue_date))
            return {"forecast_md": Path("inputs/objective/forecast.md")}

        fake_module = types.ModuleType("seasonal_outlook.objective_forecast")
        fake_module.run_objective_forecast = run_objective_forecast
        fake_config = object()

        with patch.object(cli, "load_config", return_value=fake_config), patch.dict(
            sys.modules,
            {"seasonal_outlook.objective_forecast": fake_module},
            clear=False,
        ):
            buffer = StringIO()
            with redirect_stdout(buffer):
                exit_code = cli.cmd_run_objective_forecast(argparse.Namespace(issue_date="2026-04-15", history_end=None))

        self.assertEqual(exit_code, 0)
        self.assertEqual(calls, [(fake_config, date(2026, 4, 15))])
        run_output = json.loads(buffer.getvalue())
        self.assertEqual(run_output["forecast_md"], str(Path("inputs/objective/forecast.md")))


if __name__ == "__main__":
    unittest.main()
