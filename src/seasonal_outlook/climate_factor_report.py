from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import json
import re
import tomllib

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
from matplotlib import font_manager
import matplotlib.pyplot as plt

from .config import SystemConfig
from .engine import generate_forecast, target_months
from .models import ForecastRun
from .climate_factor_pdf import build_climate_factor_pdf
from .psl_indices import _fetch_text as _download_text

_SOURCE_HEADERS = {
    "User-Agent": "seasonal-outlook/0.1 (+https://github.com/openai/codex)",
    "Accept": "text/plain, text/html;q=0.9, */*;q=0.8",
}

_CATEGORY_COLORS = {
    "lower": "#3568a0",
    "normal": "#9b9b9b",
    "upper": "#b44c3a",
}

_FACTOR_COLORS = {
    "enso": "#b44c3a",
    "wp": "#6f4a2e",
    "iobw": "#0b7a75",
    "ao": "#31558f",
    "qbo": "#8b4a1c",
    "pdo": "#516f2f",
}

_FRESHNESS_KO = {
    "fresh": "fresh",
    "usable_with_lag": "usable_with_lag",
    "stale": "stale",
    "historical_only": "historical_only",
}


def _configure_matplotlib_fonts() -> None:
    preferred = ("Malgun Gothic", "AppleGothic", "NanumGothic")
    available = {font.name for font in font_manager.fontManager.ttflist}
    for candidate in preferred:
        if candidate in available:
            plt.rcParams["font.family"] = candidate
            break
    plt.rcParams["axes.unicode_minus"] = False


@dataclass(frozen=True)
class SeriesPoint:
    year: int
    month: int
    value: float

    @property
    def as_date(self) -> date:
        return date(self.year, self.month, 1)


@dataclass(frozen=True)
class FactorSpec:
    factor_id: str
    name: str
    importance: str
    role: str
    status_line: str
    mechanism: str
    korea_temp_effects: tuple[str, str, str]
    korea_precip_effects: tuple[str, str, str]
    confidence: str
    series_name: str
    series_url: str
    series_parser: str
    series_column: str
    series_units: str
    series_window_months: int
    references: tuple[str, ...]


@dataclass(frozen=True)
class ReportSpec:
    issue_date: date
    title: str
    subtitle: str
    overview: str
    psl_scope_note: str
    temperature_summary: str
    precipitation_summary: str
    methodology: tuple[str, ...]
    priority_buckets: tuple[str, ...]
    supporting_fast_factors: tuple[str, ...]
    teleconnection_focus: tuple[str, ...]
    factors: tuple[FactorSpec, ...]


@dataclass(frozen=True)
class FactorRuntime:
    spec: FactorSpec
    points: tuple[SeriesPoint, ...]
    latest_point: SeriesPoint
    freshness: str
    chart_path: Path
    accent: str

    @property
    def latest_label(self) -> str:
        return f"{self.latest_point.year}-{self.latest_point.month:02d}"


@dataclass(frozen=True)
class TeleconnectionRow:
    year: int
    month: int
    values: dict[str, float]

    @property
    def as_date(self) -> date:
        return date(self.year, self.month, 1)


@dataclass(frozen=True)
class TeleconnectionSnapshot:
    latest_row: TeleconnectionRow
    chart_path: Path
    columns: tuple[str, ...]


def _dated_input_path(directory: Path, issue_date: date) -> Path:
    return directory / f"{issue_date.isoformat()}.toml"


def _resolve_input_path(directory: Path, issue_date: date) -> Path:
    exact = _dated_input_path(directory, issue_date)
    if exact.exists():
        return exact

    candidates = []
    for path in directory.glob("*.toml"):
        try:
            path_date = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if path_date <= issue_date:
            candidates.append((path_date, path))
    if not candidates:
        raise FileNotFoundError(f"no dated input found in {directory}")
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _parse_spec(path: Path) -> ReportSpec:
    with path.open("rb") as handle:
        payload = tomllib.load(handle)

    factors = []
    for item in payload["factors"]:
        factors.append(
            FactorSpec(
                factor_id=item["id"],
                name=item["name"],
                importance=item["importance"],
                role=item["role"],
                status_line=item["status_line"],
                mechanism=item["mechanism"],
                korea_temp_effects=tuple(item["korea_temp_effects"]),
                korea_precip_effects=tuple(item["korea_precip_effects"]),
                confidence=item["confidence"],
                series_name=item["series_name"],
                series_url=item["series_url"],
                series_parser=item["series_parser"],
                series_column=item.get("series_column", ""),
                series_units=item["series_units"],
                series_window_months=int(item["series_window_months"]),
                references=tuple(item["references"]),
            )
        )

    return ReportSpec(
        issue_date=date.fromisoformat(payload["issue_date"]),
        title=payload["title"],
        subtitle=payload["subtitle"],
        overview=payload["overview"],
        psl_scope_note=payload["psl_scope_note"],
        temperature_summary=payload["temperature_summary"],
        precipitation_summary=payload["precipitation_summary"],
        methodology=tuple(payload["methodology"]),
        priority_buckets=tuple(payload["priority_buckets"]),
        supporting_fast_factors=tuple(payload["supporting_fast_factors"]),
        teleconnection_focus=tuple(payload["teleconnection_focus"]),
        factors=tuple(factors),
    )


def _fetch_text(url: str) -> str:
    return _download_text(url, timeout_seconds=60)


def _parse_psl_grid(text: str) -> tuple[SeriesPoint, ...]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    points = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 13:
            continue
        year = int(parts[0])
        for month, raw in enumerate(parts[1:13], start=1):
            value = float(raw)
            if value <= -99:
                continue
            points.append(SeriesPoint(year=year, month=month, value=value))
    return tuple(points)


def _parse_year_month_value(text: str) -> tuple[SeriesPoint, ...]:
    points = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        points.append(SeriesPoint(year=int(parts[0]), month=int(parts[1]), value=float(parts[2])))
    return tuple(points)


def _parse_jma_table(text: str) -> tuple[SeriesPoint, ...]:
    tokens = text.split()
    if len(tokens) < 13:
        return ()
    index = 12
    points = []
    while index < len(tokens):
        year = int(tokens[index])
        index += 1
        for month in range(1, 13):
            if index >= len(tokens):
                break
            value = float(tokens[index])
            index += 1
            if value >= 99:
                continue
            points.append(SeriesPoint(year=year, month=month, value=value))
    return tuple(points)


def _parse_tele_index_nh_rows(text: str) -> tuple[TeleconnectionRow, ...]:
    rows = []
    for line in text.splitlines():
        parts = re.findall(r"[-+]?\d+(?:\.\d+)?", line)
        if len(parts) < 13 or len(parts[0]) != 4:
            continue
        rows.append(
            TeleconnectionRow(
                year=int(parts[0]),
                month=int(parts[1]),
                values={
                    "NAO": float(parts[2]),
                    "EA": float(parts[3]),
                    "WP": float(parts[4]),
                    "EP/NP": float(parts[5]),
                    "PNA": float(parts[6]),
                    "EA/WR": float(parts[7]),
                    "SCA": float(parts[8]),
                    "TNH": float(parts[9]),
                    "POL": float(parts[10]),
                    "PT": float(parts[11]),
                    "ExplVar": float(parts[12]),
                },
            )
        )
    return tuple(rows)


def _extract_series_from_tele_rows(rows: tuple[TeleconnectionRow, ...], column: str) -> tuple[SeriesPoint, ...]:
    series = []
    for row in rows:
        value = row.values[column]
        if value <= -99:
            continue
        series.append(SeriesPoint(year=row.year, month=row.month, value=value))
    return tuple(series)


_SERIES_PARSERS = {
    "psl_grid": _parse_psl_grid,
    "year_month_value": _parse_year_month_value,
    "jma_table": _parse_jma_table,
}


def _load_series(spec: FactorSpec) -> tuple[SeriesPoint, ...]:
    text = _fetch_text(spec.series_url)
    if spec.series_parser == "tele_index_nh":
        if not spec.series_column:
            raise ValueError(f"series_column is required for {spec.factor_id}")
        rows = _parse_tele_index_nh_rows(text)
        return _extract_series_from_tele_rows(rows, spec.series_column)
    parser = _SERIES_PARSERS[spec.series_parser]
    return parser(text)


def _freshness(issue_date: date, latest_point: SeriesPoint) -> str:
    months_diff = (issue_date.year - latest_point.year) * 12 + (issue_date.month - latest_point.month)
    if months_diff <= 1:
        return "fresh"
    if months_diff <= 4:
        return "usable_with_lag"
    if months_diff <= 12:
        return "stale"
    return "historical_only"


def _trim_points(points: tuple[SeriesPoint, ...], months: int) -> tuple[SeriesPoint, ...]:
    if len(points) <= months:
        return points
    return points[-months:]


def _plot_factor_chart(runtime: FactorRuntime, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_path = output_dir / f"{runtime.spec.factor_id}_timeseries.png"
    window = _trim_points(runtime.points, runtime.spec.series_window_months)
    x = [point.as_date for point in window]
    y = [point.value for point in window]

    fig, ax = plt.subplots(figsize=(6.0, 2.6), dpi=180)
    fig.patch.set_facecolor("#fffaf2")
    ax.set_facecolor("#fffdf8")
    ax.axhline(0.0, color="#b9b3a6", linewidth=1.0, linestyle="--")
    ax.plot(x, y, color=runtime.accent, linewidth=2.2)
    ax.fill_between(x, y, 0, color=runtime.accent, alpha=0.10)
    ax.scatter(
        [runtime.latest_point.as_date],
        [runtime.latest_point.value],
        color=runtime.accent,
        edgecolors="white",
        linewidth=1.2,
        s=46,
        zorder=5,
    )
    ax.set_title(
        f"{runtime.spec.name} | latest {runtime.latest_label} = {runtime.latest_point.value:+.2f} {runtime.spec.series_units}",
        fontsize=10.4,
        loc="left",
        color="#172026",
        pad=10,
    )
    ax.text(
        0.99,
        0.92,
        runtime.freshness,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8.5,
        color="#4f5960",
        bbox={"boxstyle": "round,pad=0.28", "fc": "#efe4d2", "ec": "#d8cfbf"},
    )
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(axis="x", labelsize=8, colors="#4f5960")
    ax.tick_params(axis="y", labelsize=8, colors="#4f5960")
    for spine in ax.spines.values():
        spine.set_color("#d8cfbf")
    ax.grid(axis="y", color="#e8e2d6", linewidth=0.7)
    ax.set_ylabel(runtime.spec.series_units, fontsize=8.5, color="#4f5960")
    fig.tight_layout()
    fig.savefig(chart_path, bbox_inches="tight")
    plt.close(fig)
    return chart_path


def _plot_probability_panel(run: ForecastRun, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_path = output_dir / "korea_tercile_probabilities.png"
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6), dpi=180, sharey=True)
    fig.patch.set_facecolor("#fffaf2")

    grouped = {
        variable: sorted(
            [cell for cell in run.cells if cell.region == "korea" and cell.variable == variable],
            key=lambda item: item.lead,
        )
        for variable in ("temperature", "precipitation")
    }

    for axis, variable, title in zip(
        axes,
        ("temperature", "precipitation"),
        ("한반도 기온 3분위 확률", "한반도 강수 3분위 확률"),
    ):
        cells = grouped[variable]
        labels = [f"M+{cell.lead}\n{cell.target_month.year}-{cell.target_month.month:02d}" for cell in cells]
        lower = [cell.posterior.lower * 100 for cell in cells]
        normal = [cell.posterior.normal * 100 for cell in cells]
        upper = [cell.posterior.upper * 100 for cell in cells]
        axis.bar(labels, lower, color=_CATEGORY_COLORS["lower"], label="하위")
        axis.bar(labels, normal, bottom=lower, color=_CATEGORY_COLORS["normal"], label="평년")
        axis.bar(labels, upper, bottom=[l + n for l, n in zip(lower, normal)], color=_CATEGORY_COLORS["upper"], label="상위")
        axis.set_ylim(0, 100)
        axis.set_title(title, fontsize=11.5, color="#172026")
        axis.grid(axis="y", color="#e8e2d6", linewidth=0.7)
        axis.set_facecolor("#fffdf8")
        axis.tick_params(axis="x", labelsize=8.5, colors="#4f5960")
        axis.tick_params(axis="y", labelsize=8.5, colors="#4f5960")
        for spine in axis.spines.values():
            spine.set_color("#d8cfbf")

    axes[0].set_ylabel("확률(%)", fontsize=9, color="#4f5960")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.02), frameon=False, fontsize=8.6)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(chart_path, bbox_inches="tight")
    plt.close(fig)
    return chart_path


def _reference_title(entry: str) -> str:
    return entry.split("|", 1)[0].strip()


def _reference_url(entry: str) -> str:
    parts = entry.split("|", 1)
    return parts[1].strip() if len(parts) == 2 else ""


def _write_markdown(report: ReportSpec, run: ForecastRun, factors: tuple[FactorRuntime, ...], output_dir: Path) -> Path:
    path = output_dir / "climate_factor_outlook_ko.md"
    korea_temp = sorted([cell for cell in run.cells if cell.region == "korea" and cell.variable == "temperature"], key=lambda item: item.lead)
    korea_precip = sorted([cell for cell in run.cells if cell.region == "korea" and cell.variable == "precipitation"], key=lambda item: item.lead)

    lines = [
        f"# {report.title} | {run.issue_date.isoformat()}",
        "",
        f"- 발행 기준일: `{run.issue_date.isoformat()}`",
        f"- 전망 기간: `{run.targets[0].year}-{run.targets[0].month:02d}` ~ `{run.targets[-1].year}-{run.targets[-1].month:02d}`",
        "- 산출물 성격: 기존 브리핑과 분리한 기후인자 전용 보고서",
        "",
        "## 1. 개요",
        "",
        report.overview,
        "",
        "## 2. 방법",
        "",
    ]
    for item in report.methodology:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## 3. 한반도 3분위 전망",
            "",
            f"- 기온 요약: {report.temperature_summary}",
            f"- 강수 요약: {report.precipitation_summary}",
            "",
            "| 변수 | 리드 | 대상월 | 하위 | 평년 | 상위 | 우세 범주 | 모델 합의도 |",
            "| --- | --- | --- | ---: | ---: | ---: | --- | ---: |",
        ]
    )

    for variable, label, cells in (
        ("temperature", "기온", korea_temp),
        ("precipitation", "강수", korea_precip),
    ):
        for cell in cells:
            lines.append(
                f"| {label} | M+{cell.lead} | {cell.target_month.year}-{cell.target_month.month:02d} | "
                f"{cell.posterior.lower * 100:.1f}% | {cell.posterior.normal * 100:.1f}% | {cell.posterior.upper * 100:.1f}% | "
                f"{cell.dominant_category} | {cell.model_agreement * 100:.0f}% |"
            )

    lines.extend(
        [
            "",
            "## 4. 핵심 기후인자 현황",
            "",
            "| 기후인자 | 등급 | 역할 | 최신값 | 최신월 | 최신성 | M+1 T | M+1 P | M+2 T | M+2 P | M+3 T | M+3 P |",
            "| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for factor in factors:
        lines.append(
            f"| {factor.spec.name} | {factor.spec.importance} | {factor.spec.role} | "
            f"{factor.latest_point.value:+.2f} {factor.spec.series_units} | {factor.latest_label} | {_FRESHNESS_KO[factor.freshness]} | "
            f"{factor.spec.korea_temp_effects[0]} | {factor.spec.korea_precip_effects[0]} | "
            f"{factor.spec.korea_temp_effects[1]} | {factor.spec.korea_precip_effects[1]} | "
            f"{factor.spec.korea_temp_effects[2]} | {factor.spec.korea_precip_effects[2]} |"
        )

    lines.extend(["", "## 5. 인자별 해석", ""])
    for factor in factors:
        lines.append(f"### {factor.spec.name}")
        lines.append("")
        lines.append(f"- 현재 상태: {factor.spec.status_line}")
        lines.append(f"- 동아시아/한반도 해석: {factor.spec.mechanism}")
        lines.append(f"- 신뢰도: {factor.spec.confidence}")
        lines.append(f"- 최신성 판정: `{_FRESHNESS_KO[factor.freshness]}`")
        lines.append("- 참고 문헌/기관 자료:")
        for ref in factor.spec.references:
            lines.append(f"  - [{_reference_title(ref)}]({_reference_url(ref)})")
        lines.append("")

    lines.extend(["## 6. 빠른 인자와 한계", ""])
    for item in report.supporting_fast_factors:
        lines.append(f"- {item}")
    lines.append("- 강수는 기온보다 사건성·계절내 변동성이 커서, 상위 확률이 가장 높더라도 강한 wet call로 단정하지 않았습니다.")
    lines.append("- PDO처럼 지연된 지수는 배경장 설명에만 사용했고, 이번 호 확률의 직접 앵커로 쓰지 않았습니다.")
    lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_context_json(report: ReportSpec, run: ForecastRun, factors: tuple[FactorRuntime, ...], output_dir: Path) -> Path:
    path = output_dir / "climate_factor_context.json"
    payload = {
        "issue_date": run.issue_date.isoformat(),
        "targets": [f"{item.year}-{item.month:02d}" for item in target_months(run.issue_date)],
        "temperature_summary": report.temperature_summary,
        "precipitation_summary": report.precipitation_summary,
        "factors": [
            {
                "id": factor.spec.factor_id,
                "name": factor.spec.name,
                "importance": factor.spec.importance,
                "role": factor.spec.role,
                "latest_value": round(factor.latest_point.value, 4),
                "latest_month": factor.latest_label,
                "freshness": factor.freshness,
                "series_units": factor.spec.series_units,
                "chart_path": str(factor.chart_path),
                "references": [
                    {"title": _reference_title(entry), "url": _reference_url(entry)}
                    for entry in factor.spec.references
                ],
            }
            for factor in factors
        ],
        "korea_probabilities": [
            {
                "variable": cell.variable,
                "lead": cell.lead,
                "target": f"{cell.target_month.year}-{cell.target_month.month:02d}",
                "lower": round(cell.posterior.lower, 4),
                "normal": round(cell.posterior.normal, 4),
                "upper": round(cell.posterior.upper, 4),
                "dominant_category": cell.dominant_category,
                "model_agreement": round(cell.model_agreement, 4),
            }
            for cell in run.cells
            if cell.region == "korea"
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_climate_factor_report(config: SystemConfig, issue_date: date) -> dict[str, Path]:
    _configure_matplotlib_fonts()
    spec_path = _resolve_input_path(config.factor_reports_dir(), issue_date)
    report_spec = _parse_spec(spec_path)
    run = generate_forecast(config, issue_date)
    output_dir = config.reports_dir() / issue_date.isoformat()
    asset_dir = output_dir / "climate_factor_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)

    factor_states = []
    for factor in report_spec.factors:
        series = _load_series(factor)
        if not series:
            raise ValueError(f"no data points parsed for {factor.factor_id}")
        latest = series[-1]
        runtime = FactorRuntime(
            spec=factor,
            points=series,
            latest_point=latest,
            freshness=_freshness(issue_date, latest),
            chart_path=Path(),
            accent=_FACTOR_COLORS.get(factor.factor_id, "#6f4a2e"),
        )
        chart_path = _plot_factor_chart(runtime, asset_dir)
        factor_states.append(
            FactorRuntime(
                spec=runtime.spec,
                points=runtime.points,
                latest_point=runtime.latest_point,
                freshness=runtime.freshness,
                chart_path=chart_path,
                accent=runtime.accent,
            )
        )

    factor_states_tuple = tuple(factor_states)
    probability_path = _plot_probability_panel(run, asset_dir)
    markdown_path = _write_markdown(report_spec, run, factor_states_tuple, output_dir)
    context_path = _write_context_json(report_spec, run, factor_states_tuple, output_dir)
    pdf_path = build_climate_factor_pdf(report_spec, run, factor_states_tuple, probability_path, output_dir)

    return {
        "markdown": markdown_path,
        "pdf": pdf_path,
        "context": context_path,
        "assets_dir": asset_dir,
    }
