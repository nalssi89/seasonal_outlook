from __future__ import annotations

from datetime import date
from pathlib import Path
import json

from .observed_symbols import _is_year_row, _read_rows


def _latest_populated_month(row: list[str]) -> int | None:
    return max((month for month, value in enumerate(row[2:14], start=1) if value.strip()), default=None)


def _observed_summary(path: Path, dataset_name: str, value_type: str, threshold_rule: str, station_note: str) -> dict[str, str | int]:
    rows = _read_rows(path)
    year_rows = [row for row in rows[3:] if row and _is_year_row(row[0].strip())]
    years = [int(row[0]) for row in year_rows]
    latest_row = max(year_rows, key=lambda row: int(row[0]))
    latest_month = _latest_populated_month(latest_row)
    return {
        "dataset_name": dataset_name,
        "value_type": value_type,
        "threshold_rule": threshold_rule,
        "station_note": station_note,
        "path": str(path),
        "start_year": min(years),
        "end_year": max(years),
        "latest_month": f"{int(latest_row[0])}-{latest_month:02d}" if latest_month else f"{int(latest_row[0])}",
    }


def _find_latest_context(reports_dir: Path) -> Path | None:
    candidates: list[tuple[date, Path]] = []
    for path in reports_dir.glob("*/climate_factor_context.json"):
        try:
            issue_date = date.fromisoformat(path.parent.name)
        except ValueError:
            continue
        candidates.append((issue_date, path))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _load_operational_factors(reports_dir: Path) -> tuple[Path | None, list[dict]]:
    context_path = _find_latest_context(reports_dir)
    if context_path is None:
        return None, []
    payload = json.loads(context_path.read_text(encoding="utf-8"))
    factors = []
    for factor in payload.get("factors", []):
        factors.append(
            {
                "id": factor["id"],
                "name": factor["name"],
                "importance": factor["importance"],
                "latest_month": factor["latest_month"],
                "freshness": factor["freshness"],
                "units": factor["series_units"],
            }
        )
    return context_path, factors


def _catalog_tables(catalog_path: Path) -> tuple[dict, list[dict], list[dict]]:
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    summary = payload["summary"]
    preferred_rows: list[dict] = []
    issues: list[dict] = []

    for item in payload["indices"]:
        preferred = item.get("preferred")
        preferred_variant_id = item.get("preferred_variant_id")
        preferred_variant = None
        for variant in item.get("variants", []):
            if variant.get("variant_id") == preferred_variant_id:
                preferred_variant = variant
            if variant.get("parse_status") != "ok":
                issues.append(
                    {
                        "index_id": item["index_id"],
                        "display_name": item["display_name"],
                        "variant_label": variant["label"],
                        "url": variant["url"],
                        "fetch_status": variant["fetch_status"],
                        "parse_status": variant["parse_status"],
                        "error": variant["error"] or "",
                    }
                )
        if preferred and preferred_variant:
            preferred_rows.append(
                {
                    "index_id": item["index_id"],
                    "display_name": item["display_name"],
                    "preferred_label": preferred["preferred_label"],
                    "range": f"{preferred_variant['start_month']} ~ {preferred['latest_month']}",
                    "latest_month": preferred["latest_month"],
                    "freshness": preferred["freshness"],
                    "outlook_role": preferred["outlook_role"],
                    "regularly_updated": "yes" if item["regularly_updated"] else "no",
                    "preferred_url": preferred["preferred_url"],
                }
            )

    preferred_rows.sort(key=lambda item: item["index_id"])
    return summary, preferred_rows, issues


def _tele_summary(path: Path) -> dict[str, str | int | float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_path = Path(str(payload["raw_path"]))
    start_month = ""
    for line in raw_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 4 and parts[1].isdigit():
            start_month = f"{int(parts[0])}-{int(parts[1]):02d}"
            break
    latest = payload.get("latest") or {}
    return {
        "range": f"{start_month} ~ {latest.get('month', '')}".strip(),
        "row_count": payload["row_count"],
        "latest_month": latest.get("month", ""),
        "latest_values": latest.get("values", {}),
        "source_url": payload["source_url"],
    }


def render_data_inventory_markdown(
    temperature_csv: Path,
    precipitation_csv: Path,
    observed_symbol_md: Path,
    catalog_json: Path,
    tele_json: Path,
    reports_dir: Path,
    output_path: Path,
) -> Path:
    station_note = "사용자 제공 메타데이터 기준 1973~1989년 56개 지점, 1990년 이후 62개 지점"
    observed_rows = [
        _observed_summary(
            temperature_csv,
            dataset_name="남한 월별 평균기온 편차",
            value_type="월별 평균기온 평년편차",
            threshold_rule="각 월의 비슷범위 ±값 기준으로 -, 0, + 판정",
            station_note=station_note,
        ),
        _observed_summary(
            precipitation_csv,
            dataset_name="남한 월별 강수량",
            value_type="월별 강수량 총량",
            threshold_rule="각 월의 비슷범위 하한~상한 기준으로 -, 0, + 판정",
            station_note=station_note,
        ),
    ]

    operational_context_path, operational_factors = _load_operational_factors(reports_dir)
    catalog_summary, preferred_rows, issues = _catalog_tables(catalog_json)
    tele = _tele_summary(tele_json)

    lines = [
        "# 수집자료 가용범위 요약",
        "",
        "## 1. 관측 참값 자료",
        "",
        "| 자료 | 내용 | 가용 범위 | 최근 가용 월 | 판정 기준 | 비고 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for row in observed_rows:
        lines.append(
            f"| {row['dataset_name']} | {row['value_type']} | {row['start_year']} ~ {row['end_year']} | {row['latest_month']} | {row['threshold_rule']} | {row['station_note']} |"
        )

    lines.extend(
        [
            "",
            f"- 기호화 정리 파일: `{observed_symbol_md}`",
            f"- 원본 파일: `{temperature_csv}`, `{precipitation_csv}`",
            "",
            "## 2. 현재 운영 보고서에서 읽는 핵심 기후인자",
            "",
        ]
    )

    if operational_factors:
        lines.extend(
            [
                f"- 기준 context: `{operational_context_path}`",
                "",
                "| ID | 인자 | 중요도 | 최근 월 | freshness | 단위 |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for factor in operational_factors:
            lines.append(
                f"| {factor['id']} | {factor['name']} | {factor['importance']} | {factor['latest_month']} | {factor['freshness']} | {factor['units']} |"
            )
    else:
        lines.append("- 생성된 `climate_factor_context.json`이 없어 운영 인자 표는 생략했습니다.")

    lines.extend(
        [
            "",
            "## 3. NOAA PSL 전체 기후지수 수집 현황",
            "",
            f"- catalog 기준일: `{catalog_summary['issue_date']}`",
            f"- 수집 인덱스 수: `{catalog_summary['index_count']}`",
            f"- 발견된 variant 수: `{catalog_summary['variant_count']}`",
            f"- 정규화 가능한 대표 시계열 수: `{catalog_summary['preferred_count']}`",
            f"- freshness 분포: `fresh {catalog_summary['fresh']}`, `usable_with_lag {catalog_summary['usable_with_lag']}`, `stale {catalog_summary['stale']}`, `historical_only {catalog_summary['historical_only']}`",
            "",
            "| ID | 표시명 | 대표 시계열 | 가용 범위 | 최근 월 | freshness | outlook role | updated* |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for row in preferred_rows:
        lines.append(
            f"| {row['index_id']} | {row['display_name']} | [{row['preferred_label']}]({row['preferred_url']}) | {row['range']} | {row['latest_month']} | {row['freshness']} | {row['outlook_role']} | {row['regularly_updated']} |"
        )

    lines.extend(
        [
            "",
            "## 4. 보완 수집: CPC tele_index.nh",
            "",
            f"- 가용 범위: `{tele['range']}`",
            f"- row 수: `{tele['row_count']}`",
            f"- 최근 월: `{tele['latest_month']}`",
            f"- 최신값: `NAO {tele['latest_values'].get('NAO')}`, `WP {tele['latest_values'].get('WP')}`, `PNA {tele['latest_values'].get('PNA')}`, `EP/NP {tele['latest_values'].get('EP/NP')}`, `EA/WR {tele['latest_values'].get('EA/WR')}`",
            f"- 원시 자료: [{tele['source_url']}]({tele['source_url']})",
            "",
            "## 5. 정규화 실패 또는 raw-only 항목",
            "",
            "| ID | 표시명 | variant | fetch | parse | 비고 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )

    if issues:
        for item in issues:
            lines.append(
                f"| {item['index_id']} | {item['display_name']} | [{item['variant_label']}]({item['url']}) | {item['fetch_status']} | {item['parse_status']} | {item['error']} |"
            )
    else:
        lines.append("| - | - | - | - | - | 없음 |")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
