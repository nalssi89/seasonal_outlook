from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.pdfgen import canvas

from .c3s_pdf import (
    MARGIN_X,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    _draw_chip,
    _draw_image,
    _draw_panel,
    _draw_paragraph,
    _draw_slide_shell,
    _register_fonts,
    _styles,
)
from .pdf_publish import publish_pdf_copy

if TYPE_CHECKING:
    from .climate_factor_report import FactorRuntime, ReportSpec
    from .models import ForecastRun


ACCENT = "#7f3f22"


def _pick_output_path(issue_dir: Path) -> Path:
    return issue_dir / "climate_factor_outlook_slides_ko.pdf"


def _draw_cover_slide(c: canvas.Canvas, report_spec: "ReportSpec", run: "ForecastRun", total_slides: int, styles: dict) -> None:
    _draw_slide_shell(c, ACCENT, f"01 / {total_slides:02d}")
    top = PAGE_HEIGHT - 68
    top = _draw_paragraph(c, "Climate-factor watch", styles["eyebrow"], MARGIN_X, top, 420)
    top = _draw_paragraph(c, report_spec.title, styles["title"], MARGIN_X, top - 2, 760)
    _draw_chip(c, 1010, 674, 300, 26, f"Issue date | {run.issue_date.isoformat()}", styles, "#efe4d2")
    _draw_paragraph(c, report_spec.overview, styles["subtitle"], MARGIN_X, top - 10, PAGE_WIDTH - (2 * MARGIN_X))

    _draw_panel(
        c,
        MARGIN_X,
        356,
        620,
        210,
        "이번 보고서의 목적",
        "<b>1.</b> 기존 briefing과 분리된 기후인자 전용 산출물입니다.<br/><br/>"
        "<b>2.</b> 최근성(freshness)을 따져 핵심 인자와 배경 인자를 나눴습니다.<br/><br/>"
        "<b>3.</b> 한반도 기온·강수는 3분위 확률로만 제시하고, 단정형 문장을 피했습니다.",
        styles,
        ACCENT,
    )
    _draw_panel(
        c,
        680,
        356,
        650,
        210,
        "전망 창",
        f"<b>대상월</b><br/>{run.targets[0].year}-{run.targets[0].month:02d}, {run.targets[1].year}-{run.targets[1].month:02d}, {run.targets[2].year}-{run.targets[2].month:02d}<br/><br/>"
        "<b>확률 앵커</b><br/>calibrated multi-model prior<br/><br/>"
        "<b>기후인자 결합</b><br/>ENSO, 인도양, AO, QBO, PDO의 capped posterior adjustment",
        styles,
        ACCENT,
    )
    _draw_panel(
        c,
        MARGIN_X,
        132,
        1294,
        176,
        "운영 규칙",
        "<b>fresh</b> 인자는 현재 진단의 핵심, <b>usable_with_lag</b>는 보조, <b>stale</b>는 배경장 설명에만 사용했습니다.<br/><br/>"
        "강수는 기온보다 근거 수준을 낮게 두었고, 상위 확률이 가장 높아도 <b>평년과 비슷하거나 다소 많음</b> 수준으로만 표현했습니다.<br/><br/>"
        "PJ·BSISO·아시아 몬순 전이 등 빠른 인자는 M+1 보조 설명으로만 유지했습니다.",
        styles,
        ACCENT,
    )


def _draw_probability_slide(c: canvas.Canvas, report_spec: "ReportSpec", probability_path: Path, total_slides: int, styles: dict) -> None:
    _draw_slide_shell(c, "#9d3322", f"02 / {total_slides:02d}")
    top = PAGE_HEIGHT - 62
    top = _draw_paragraph(c, "Korea tercile outlook", styles["eyebrow"], MARGIN_X, top, 420)
    top = _draw_paragraph(c, "한반도 기온·강수 3분위 확률", styles["title"], MARGIN_X, top - 4, 680)
    _draw_paragraph(c, "기온은 상위 3분위 우세가 일관적이고, 강수는 상위 3분위가 가장 높지만 기온보다 훨씬 보수적으로 읽어야 합니다.", styles["subtitle"], MARGIN_X, top - 10, 1160)
    _draw_image(c, probability_path, MARGIN_X, 252, 760, 320)
    _draw_panel(c, 830, 388, 500, 184, "기온 해석", report_spec.temperature_summary, styles, "#9d3322")
    _draw_panel(c, 830, 172, 500, 184, "강수 해석", report_spec.precipitation_summary, styles, "#9d3322")


def _factor_card_body(factor: "FactorRuntime") -> str:
    return (
        f"<b>상태</b><br/>{factor.spec.status_line}<br/><br/>"
        f"<b>M+1~M+3 기온</b><br/>{', '.join(factor.spec.korea_temp_effects)}<br/><br/>"
        f"<b>M+1~M+3 강수</b><br/>{', '.join(factor.spec.korea_precip_effects)}<br/><br/>"
        f"<b>해석</b><br/>{factor.spec.mechanism}"
    )


def _draw_factor_cards_slide(c: canvas.Canvas, factors: tuple["FactorRuntime", ...], total_slides: int, styles: dict) -> None:
    _draw_slide_shell(c, "#0d5a6b", f"03 / {total_slides:02d}")
    top = PAGE_HEIGHT - 62
    top = _draw_paragraph(c, "Factor dashboard", styles["eyebrow"], MARGIN_X, top, 420)
    _draw_paragraph(c, "핵심 기후인자 현재 상태", styles["title"], MARGIN_X, top - 4, 620)

    positions = [
        (MARGIN_X, 396),
        (676, 396),
        (MARGIN_X, 144),
        (676, 144),
    ]
    for (x, y), factor in zip(positions, factors[:4]):
        _draw_panel(c, x, y, 616, 220, factor.spec.name, _factor_card_body(factor), styles, factor.accent)
        _draw_chip(c, x + 454, y + 184, 72, 24, factor.spec.importance, styles, "#efe4d2", text_color=factor.accent, stroke_color=factor.accent)
        _draw_chip(c, x + 534, y + 184, 64, 24, factor.freshness, styles, "#fffaf2", text_color=factor.accent, stroke_color=factor.accent)

    if len(factors) > 4:
        factor = factors[4]
        _draw_panel(c, 119, 44, 1128, 76, factor.spec.name, _factor_card_body(factor), styles, factor.accent)
        _draw_chip(c, 1080, 88, 72, 24, factor.spec.importance, styles, "#efe4d2", text_color=factor.accent, stroke_color=factor.accent)
        _draw_chip(c, 1160, 88, 64, 24, factor.freshness, styles, "#fffaf2", text_color=factor.accent, stroke_color=factor.accent)


def _draw_timeseries_slide(
    c: canvas.Canvas,
    title: str,
    slide_no: int,
    total_slides: int,
    factors: tuple["FactorRuntime", ...],
    styles: dict,
    accent: str,
    note: str | None = None,
) -> None:
    _draw_slide_shell(c, accent, f"{slide_no:02d} / {total_slides:02d}")
    top = PAGE_HEIGHT - 62
    top = _draw_paragraph(c, "Climate-factor time series", styles["eyebrow"], MARGIN_X, top, 520)
    _draw_paragraph(c, title, styles["title"], MARGIN_X, top - 4, 760)

    if note and len(factors) <= 2:
        width = (PAGE_WIDTH - (2 * MARGIN_X) - 24) / 2
        for index, factor in enumerate(factors):
            x = MARGIN_X + index * (width + 24)
            _draw_image(c, factor.chart_path, x, 348, width, 270)
        _draw_panel(c, MARGIN_X, 76, PAGE_WIDTH - (2 * MARGIN_X), 218, "보류/제한", note, styles, accent)
        return

    width = (PAGE_WIDTH - (2 * MARGIN_X) - 24) / 2
    coords = [
        (MARGIN_X, 380),
        (MARGIN_X + width + 24, 380),
        (MARGIN_X, 80),
        (MARGIN_X + width + 24, 80),
    ]
    for (x, y), factor in zip(coords, factors):
        _draw_image(c, factor.chart_path, x, y, width, 250)


def _draw_sources_slide(c: canvas.Canvas, report_spec: "ReportSpec", factors: tuple["FactorRuntime", ...], total_slides: int, styles: dict) -> None:
    _draw_slide_shell(c, "#5f513c", f"{total_slides:02d} / {total_slides:02d}")
    top = PAGE_HEIGHT - 62
    top = _draw_paragraph(c, "Evidence and caveats", styles["eyebrow"], MARGIN_X, top, 420)
    _draw_paragraph(c, "근거와 유의사항", styles["title"], MARGIN_X, top - 4, 620)

    unique_refs: list[str] = []
    for factor in factors:
        for ref in factor.spec.references:
            if ref not in unique_refs:
                unique_refs.append(ref)

    left_lines = []
    for item in report_spec.methodology:
        left_lines.append(f"• {item}")
    left_lines.append("")
    for item in report_spec.supporting_fast_factors:
        left_lines.append(f"• {item}")
    left_lines.append("• 강수는 계절내 변동성이 커서 사건성 예측으로 해석하면 안 됩니다.")

    right_lines = [f"• {entry.split('|', 1)[0].strip()}" for entry in unique_refs[:12]]

    _draw_panel(c, MARGIN_X, 166, 620, 430, "해석 규칙", "<br/>".join(left_lines), styles, "#5f513c")
    _draw_panel(c, 686, 166, 644, 430, "주요 출처", "<br/>".join(right_lines), styles, "#5f513c")


def build_climate_factor_pdf(
    report_spec: "ReportSpec",
    run: "ForecastRun",
    factors: tuple["FactorRuntime", ...],
    probability_path: Path,
    output_dir: Path,
) -> Path:
    _register_fonts()
    styles = _styles()
    output_path = _pick_output_path(output_dir)
    c = canvas.Canvas(str(output_path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    c.setTitle("Climate Factor Outlook Slides")
    total_slides = 6

    _draw_cover_slide(c, report_spec, run, total_slides, styles)
    c.showPage()
    _draw_probability_slide(c, report_spec, probability_path, total_slides, styles)
    c.showPage()
    _draw_factor_cards_slide(c, factors, total_slides, styles)
    c.showPage()
    _draw_timeseries_slide(c, "핵심 시계열 1: ENSO · 인도양 · AO", 4, total_slides, factors[:3], styles, "#0b7a75")
    c.showPage()
    _draw_timeseries_slide(
        c,
        "핵심 시계열 2: QBO · PDO",
        5,
        total_slides,
        factors[3:5],
        styles,
        "#516f2f",
        note=(
            "PDO는 2025-12까지의 monthly feed만 제공되어 배경장 설명에만 사용했습니다.<br/><br/>"
            "PJ·BSISO·아시아 몬순 전이 신호는 공개 monthly series의 일관성이 낮고 예측 수명이 짧아 별도 차트에서 제외했습니다."
        ),
    )
    c.showPage()
    _draw_sources_slide(c, report_spec, factors, total_slides, styles)
    c.showPage()
    c.save()
    root_dir = output_dir.parent.parent
    return publish_pdf_copy(output_path, run.issue_date, root_dir)
