from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .models import ForecastRun, REGION_ORDER, VARIABLE_ORDER
from .png import write_png


COLOR_SCALE = {
    "lower": (53, 104, 160),
    "normal": (190, 190, 190),
    "upper": (180, 76, 58),
}
VARIABLE_LABELS = {"temperature": "기온", "precipitation": "강수"}
REGION_LABELS = {"korea": "한반도", "east_asia": "동아시아"}
CATEGORY_LABELS = {"lower": "낮음", "normal": "비슷", "upper": "높음"}


def _group_cells(run: ForecastRun) -> dict[tuple[str, str], list]:
    grouped = defaultdict(list)
    for cell in run.cells:
        grouped[(cell.region, cell.variable)].append(cell)
    for value in grouped.values():
        value.sort(key=lambda item: item.lead)
    return grouped


def _percent(value: float) -> str:
    return f"{value * 100:.0f}%"


def _korea_cells(grouped: dict[tuple[str, str], list], variable: str) -> list:
    return grouped[("korea", variable)]


def _category_name_ko(category: str) -> str:
    return {"lower": "하위", "normal": "평년", "upper": "상위"}[category]


def _temperature_summary_ko(cells: list) -> str:
    dominant = all(cell.dominant_category == "upper" for cell in cells)
    if dominant:
        return "기온은 M+1~M+3 모두 상위 3분위 우세가 유지됩니다."
    return "기온은 전반적으로 평년 이상 쪽으로 기울지만, 리드별 강도 차이는 남아 있습니다."


def _precipitation_summary_ko(cells: list) -> str:
    first = cells[0]
    first_gap = first.posterior.upper - first.posterior.normal
    later_strong = sum(cell.posterior.upper > cell.posterior.normal for cell in cells[1:])
    if first_gap < 0.03:
        return "강수는 M+1에서 평년과 상위 범주의 차이가 크지 않아, 평년과 비슷하거나 다소 많을 가능성으로 보는 편이 가장 보수적입니다."
    if later_strong >= 2:
        return "강수는 세 달 모두 상위 범주가 가장 높지만, 기온보다 신호가 약해 강한 다우 전망보다는 평년~다소 많음으로 해석하는 편이 안전합니다."
    return "강수는 상위 범주 쪽 기울기가 있으나, 평년 범주와의 차이가 크지 않아 사건성 변동에 더 민감합니다."


def _factor_sentence_ko(factor) -> str:
    if factor.factor_id == "enso":
        return "ENSO는 중립이지만 여름철 warm transition 가능성이 남아 있어 기온 상향의 핵심 배경입니다."
    if factor.factor_id == "pdo":
        return "PDO 음의 위상은 북태평양 쪽 온난 증폭을 일부 완화하지만, 현재 신호를 뒤집는 수준은 아닙니다."
    if factor.factor_id == "iod_iob":
        return "인도양은 대체로 중립에 가깝지만, M+2~M+3 강수에 약한 상향 배경으로 작용합니다."
    if factor.factor_id == "ao_nao":
        return "AO/NAO는 봄철 전이 구간의 보조 인자로만 반영했고 여름철 직접 신호로 과대해석하지 않았습니다."
    if factor.factor_id == "pj":
        return "PJ 패턴은 M+1 강수와 기온의 빠른 조정 인자로만 낮은 가중치로 반영했습니다."
    if factor.factor_id == "bsiso":
        return "BSISO는 계절내 시간척도 인자로서 M+1 강수 신호를 약하게 지지합니다."
    if factor.factor_id == "monsoon":
        return "아시아 몬순 전이 신호는 초여름 강수대 형성 가능성을 보조적으로 지지합니다."
    if factor.factor_id in {"sea_ice", "snow_cover", "soil_moisture"}:
        return f"{factor.name}은(는) 독립 판단 근거가 아니라 배경장 보정용 보조 인자로만 사용했습니다."
    return f"{factor.name}은(는) `{factor.state}` 상태로 반영했습니다."


def render_markdown(run: ForecastRun) -> Path:
    run.output_dir.mkdir(parents=True, exist_ok=True)
    path = run.output_dir / "briefing.md"
    grouped = _group_cells(run)
    dynamic_only = not run.factors

    headline_bits = []
    for variable in VARIABLE_ORDER:
        cell = grouped[("korea", variable)][0]
        headline_bits.append(
            f"한반도 M+1 {VARIABLE_LABELS[variable]}: {CATEGORY_LABELS[cell.dominant_category]} ({_percent(max(cell.posterior.as_dict().values()))})"
        )

    lines = [
        f"# 계절전망 브리핑 | {run.issue_date.isoformat()}",
        "",
        f"- 자료 상태: `{run.source_status}`",
        f"- 전망 대상 기간: `{run.targets[0].year}-{run.targets[0].month:02d}` ~ `{run.targets[-1].year}-{run.targets[-1].month:02d}`",
        (
            "- 전망 기준: 역학 다중모델 확률만 독립적으로 사용하며, 기후인자 보정은 적용하지 않음"
            if dynamic_only
            else "- 전망 기준: 보정된 다중모델 prior와 기후인자 posterior 보정을 함께 사용"
        ),
        (
            "- 분리 원칙: 핵심기후인자 결과는 `objective_forecast_ko.md`에서 별도 제공"
            if dynamic_only
            else "- 분리 원칙: 이 문서는 혼합 결과 브리핑임"
        ),
        "",
        "## 1. 오늘의 핵심",
        "",
        "- " + "; ".join(headline_bits),
        "- 표현은 확률적 서술을 유지하며 단정적 표현은 피합니다.",
        "",
        "## 2. 한반도 3분위 표",
        "",
        "| 변수 | 리드 | 목표월 | 낮음 | 비슷 | 높음 | 우세범주 | 일치도 |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | ---: |",
    ]
    for variable in VARIABLE_ORDER:
        for cell in grouped[("korea", variable)]:
            lines.append(
                f"| {VARIABLE_LABELS[variable]} | M+{cell.lead} | {cell.target_month.year}-{cell.target_month.month:02d} | "
                f"{_percent(cell.posterior.lower)} | {_percent(cell.posterior.normal)} | {_percent(cell.posterior.upper)} | "
                f"{CATEGORY_LABELS[cell.dominant_category]} | {_percent(cell.model_agreement)} |"
            )

    lines.extend(
        [
            "",
            "## 3. 동아시아 확률 패널과 모델 일치도",
            "",
            "생성된 그림:",
            "",
            f"![3분위 요약]({(run.output_dir / 'tercile_overview.png').resolve().as_posix()})",
            "",
            f"![모델 일치도]({(run.output_dir / 'model_agreement.png').resolve().as_posix()})",
        ]
    )
    if dynamic_only:
        lines.extend(
            [
                "",
                "## 4. 독립성 원칙",
                "",
                "- 이 브리핑은 역학 다중모델 입력만 사용한 독립 결과입니다.",
                "- ENSO, PDO, AO, MJO 등 핵심기후인자 결과는 이 문서에 혼합하지 않았습니다.",
                "- 핵심기후인자 기반 객관예측은 별도 문서 `objective_forecast_ko.md`에서 확인합니다.",
            ]
        )
    else:
        lines.extend(["", "## 4. 최근 기후인자 진단", ""])
        for factor in run.factors:
            lines.append(
                f"- **{factor.name}** `{factor.state}` 신뢰도={factor.confidence:.2f} 출처=[{factor.source_name}]({factor.source_url})"
            )
            lines.append(f"  요약: {factor.summary}")

        lines.extend(
            [
                "",
                "## 5. 인자 기여도 표",
                "",
                "| 권역 | 변수 | 리드 | posterior 조정량 | 상위 기여 인자 |",
                "| --- | --- | --- | ---: | --- |",
            ]
        )
        for region in REGION_ORDER:
            for variable in VARIABLE_ORDER:
                for cell in grouped[(region, variable)]:
                    sorted_contrib = sorted(cell.factor_contributions, key=lambda item: abs(item[1]), reverse=True)[:4]
                    label = ", ".join(f"{name}:{value:+.3f}" for name, value in sorted_contrib) or "없음"
                    lines.append(
                        f"| {REGION_LABELS[region]} | {VARIABLE_LABELS[variable]} | M+{cell.lead} | {cell.total_adjustment:+.3f} | {label} |"
                    )

    lines.extend(
        [
            "",
            "## 5. 불확실성과 반대 시나리오" if dynamic_only else "## 6. 불확실성과 반대 시나리오",
            "",
        ]
    )
    for variable in VARIABLE_ORDER:
        east_asia_cell = grouped[("east_asia", variable)][0]
        counter = "lower" if east_asia_cell.dominant_category == "upper" else "upper"
        lines.append(
            f"- {VARIABLE_LABELS[variable]}: 동아시아 M+1의 주 신호는 `{CATEGORY_LABELS[east_asia_cell.dominant_category]}`이지만, 빠른 인자가 약화되거나 반전되면 `{CATEGORY_LABELS[counter]}`도 충분히 가능합니다."
        )

    lines.extend(
        [
            "",
            "## 6. 검증과 시스템 변경 이력" if dynamic_only else "## 7. 검증과 시스템 변경 이력",
            "",
            "- 고정 평가 규칙: 한반도 중심 RPSS, BSS, 신뢰도, ACC, 확률 점프 패널티를 사용합니다.",
            "- 승격 규칙: 종합 점수가 2% 이상 개선되고, 한반도 기온·강수 BSS가 각각 5% 이상 악화되면 안 됩니다.",
        ]
    )
    if run.warnings:
        lines.append("- 참고:")
        for warning in run.warnings:
            lines.append(f"  - {warning}")
    else:
        lines.append("- 참고: 없음")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    render_markdown_ko(run)
    return path


def render_markdown_ko(run: ForecastRun) -> Path:
    run.output_dir.mkdir(parents=True, exist_ok=True)
    path = run.output_dir / "briefing_ko.md"
    grouped = _group_cells(run)
    dynamic_only = not run.factors
    korea_temp = _korea_cells(grouped, "temperature")
    korea_precip = _korea_cells(grouped, "precipitation")
    east_asia_temp = grouped[("east_asia", "temperature")]
    east_asia_precip = grouped[("east_asia", "precipitation")]

    lines = [
        f"# 동아시아-한반도 3개월 전망 브리핑 | {run.issue_date.isoformat()}",
        "",
        f"- 자료 상태: `{run.source_status}`",
        f"- 전망 대상 기간: `{run.targets[0].year}-{run.targets[0].month:02d}` ~ `{run.targets[-1].year}-{run.targets[-1].month:02d}`",
        (
            "- 전망 방식: 역학 다중모델 확률만 사용한 독립 결과"
            if dynamic_only
            else "- 전망 방식: 보정된 다중모델 확률(prior) + 기후인자 기반 후처리(posterior)"
        ),
        (
            "- 분리 원칙: 핵심기후인자 객관예보는 `objective_forecast_ko.md`에서 별도로 제공"
            if dynamic_only
            else "- 분리 원칙: 이 문서는 혼합 결과 브리핑임"
        ),
    ]
    if run.source_status == "delayed":
        lines.append("- 입력 자료는 최신 가용 dated input을 사용했으며, 직전 갱신본을 기준으로 4월 16일 발행문으로 재작성했습니다.")

    lines.extend(
        [
            "",
            "## 1. 오늘의 핵심 결론",
            "",
            f"- 한반도 `M+1(2026년 5월)` 기온은 `{_category_name_ko(korea_temp[0].dominant_category)}` 범주 우세입니다. 확률은 `하위 {_percent(korea_temp[0].posterior.lower)} / 평년 {_percent(korea_temp[0].posterior.normal)} / 상위 {_percent(korea_temp[0].posterior.upper)}`입니다.",
            f"- 한반도 `M+1(2026년 5월)` 강수는 `평년~상위` 경계에 가까운 약한 다우 경향입니다. 확률은 `하위 {_percent(korea_precip[0].posterior.lower)} / 평년 {_percent(korea_precip[0].posterior.normal)} / 상위 {_percent(korea_precip[0].posterior.upper)}`입니다.",
            f"- {_temperature_summary_ko(korea_temp)}",
            f"- {_precipitation_summary_ko(korea_precip)}",
            "- 본 전망은 계절 평균장에 대한 확률 전망이며, 장마 시작 시기나 개별 호우 발생일을 직접 예고하지는 않습니다.",
            "",
            "## 2. 한반도 3분위 확률표",
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
                f"{_percent(cell.posterior.lower)} | {_percent(cell.posterior.normal)} | {_percent(cell.posterior.upper)} | "
                f"{_category_name_ko(cell.dominant_category)} | {_percent(cell.model_agreement)} |"
            )

    lines.extend(
        [
            "",
            "## 3. 동아시아 전망 요약",
            "",
            f"- 동아시아 기온은 `M+1~M+3` 모두 `{_category_name_ko(east_asia_temp[0].dominant_category)}` 범주 우세가 유지됩니다.",
            f"- 동아시아 강수는 세 달 모두 상위 범주가 가장 높지만, 기온보다 신호가 약하고 공간 변동성이 더 큽니다.",
            "- 시각 자료:",
            "",
            f"![3분위 개요]({(run.output_dir / 'tercile_overview.png').resolve().as_posix()})",
            "",
            f"![모델 합의도]({(run.output_dir / 'model_agreement.png').resolve().as_posix()})",
        ]
    )
    if dynamic_only:
        lines.extend(
            [
                "",
                "## 4. 독립성 원칙",
                "",
                "- 이 브리핑은 역학 다중모델 확률만 사용한 독립 결과입니다.",
                "- ENSO, PDO, AO, MJO 등 핵심기후인자 결과는 이 문서에 혼합하지 않았습니다.",
                "- 핵심기후인자 기반 객관지수예보는 별도 문서 `objective_forecast_ko.md`에서 확인합니다.",
            ]
        )
    else:
        lines.extend(["", "## 4. 최근 기후인자 진단", ""])
        for factor in run.factors:
            lines.append(f"- `{factor.name}`: {_factor_sentence_ko(factor)}")

        lines.extend(
            [
                "",
                "## 5. 인자별 주요 기여",
                "",
                "| 지역 | 변수 | 리드 | 총 보정량 | 주요 기여 인자 |",
                "| --- | --- | --- | ---: | --- |",
            ]
        )
        for region in REGION_ORDER:
            for variable in VARIABLE_ORDER:
                for cell in grouped[(region, variable)]:
                    sorted_contrib = sorted(cell.factor_contributions, key=lambda item: abs(item[1]), reverse=True)[:4]
                    label = ", ".join(name for name, _ in sorted_contrib) or "없음"
                    region_label = REGION_LABELS[region]
                    variable_label = VARIABLE_LABELS[variable]
                    lines.append(
                        f"| {region_label} | {variable_label} | M+{cell.lead} | {cell.total_adjustment:+.3f} | {label} |"
                    )

    lines.extend(
        [
            "",
            "## 5. 불확실성과 반대 시나리오" if dynamic_only else "## 6. 불확실성과 반대 시나리오",
            "",
            "- 기온: 대규모 온난 배경은 비교적 일관되지만, 5월~6월 순환장 전이가 빨라지면 상위 확률은 일부 약화될 수 있습니다.",
            "- 강수: M+1은 평년과 상위 범주의 차이가 작아, 실황에서는 평년 범주로 수렴할 가능성도 충분합니다.",
            "- 따라서 한반도 강수는 `강한 다우 전망`보다는 `평년과 비슷하거나 다소 많을 가능성`으로 읽는 편이 가장 객관적입니다.",
            "",
            "## 6. 종합 판정" if dynamic_only else "## 7. 종합 판정",
            "",
            "- 한반도 `M+1~M+3 기온`: `평년보다 높을 가능성 우세`",
            "- 한반도 `M+1~M+3 강수`: `평년과 비슷하거나 다소 많을 가능성`, 다만 `M+1`은 신호가 가장 약함",
            "- 동아시아 `M+1~M+3 기온`: `평년보다 높을 가능성 우세`",
            "- 동아시아 `M+1~M+3 강수`: `평년~다소 많음 가능성`, 공간 변동성이 큼",
        ]
    )
    if run.factors:
        lines.extend(["", "## 8. 사용한 공개 근거자료", ""])
        seen_sources = set()
        for factor in run.factors:
            source = (factor.source_name, factor.source_url)
            if source in seen_sources:
                continue
            seen_sources.add(source)
            lines.append(f"- {factor.source_name}: {factor.source_url}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _heat_color(cell) -> tuple[int, int, int]:
    dominant = cell.dominant_category
    base = COLOR_SCALE[dominant]
    scale = 0.4 + max(cell.posterior.lower, cell.posterior.normal, cell.posterior.upper) * 0.6
    return tuple(min(255, int(channel * scale)) for channel in base)


def render_tercile_overview(run: ForecastRun) -> Path:
    cell_width = 120
    cell_height = 80
    width = cell_width * 3
    height = cell_height * 4
    pixels = [(245, 245, 245)] * (width * height)

    grouped = _group_cells(run)
    ordered_rows = []
    for region in REGION_ORDER:
        for variable in VARIABLE_ORDER:
            ordered_rows.append(grouped[(region, variable)])

    for row_index, row in enumerate(ordered_rows):
        for col_index, cell in enumerate(row):
            color = _heat_color(cell)
            x0 = col_index * cell_width
            y0 = row_index * cell_height
            for y in range(y0, y0 + cell_height):
                for x in range(x0, x0 + cell_width):
                    border = x in (x0, x0 + cell_width - 1) or y in (y0, y0 + cell_height - 1)
                    pixels[y * width + x] = (60, 60, 60) if border else color

    path = run.output_dir / "tercile_overview.png"
    write_png(path, width, height, pixels)
    return path


def render_model_agreement(run: ForecastRun) -> Path:
    bar_width = 60
    gap = 20
    bars = len(run.cells)
    width = bars * (bar_width + gap) + gap
    height = 220
    pixels = [(255, 255, 255)] * (width * height)
    baseline = 190

    for index, cell in enumerate(run.cells):
        x0 = gap + index * (bar_width + gap)
        x1 = x0 + bar_width
        bar_height = int(cell.model_agreement * 150)
        color = _heat_color(cell)
        for y in range(baseline - bar_height, baseline):
            for x in range(x0, x1):
                pixels[y * width + x] = color
        for x in range(x0, x1):
            pixels[baseline * width + x] = (50, 50, 50)

    path = run.output_dir / "model_agreement.png"
    write_png(path, width, height, pixels)
    return path
