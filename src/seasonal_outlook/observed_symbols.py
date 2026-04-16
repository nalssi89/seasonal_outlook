from __future__ import annotations

from pathlib import Path
import csv


MONTHS = [f"{month}월" for month in range(1, 13)]


def _read_rows(path: Path) -> list[list[str]]:
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return [row for row in csv.reader(handle)]
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("observed_symbols", b"", 0, 1, f"unsupported encoding for {path}")


def _is_year_row(label: str) -> bool:
    return len(label) == 4 and label.isdigit()


def _parse_temperature_thresholds(row: list[str]) -> dict[str, float]:
    thresholds = {}
    for month, value in zip(MONTHS, row[2:14], strict=True):
        thresholds[month] = float(value.replace("±", "").strip())
    return thresholds


def _parse_precipitation_thresholds(row: list[str]) -> dict[str, tuple[float, float]]:
    thresholds = {}
    for month, value in zip(MONTHS, row[2:14], strict=True):
        lower_raw, upper_raw = value.split("~", 1)
        thresholds[month] = (float(lower_raw), float(upper_raw))
    return thresholds


def _classify_temperature(value: float, threshold: float) -> str:
    if value < -threshold:
        return "-"
    if value > threshold:
        return "+"
    return "0"


def _classify_precipitation(value: float, bounds: tuple[float, float]) -> str:
    lower, upper = bounds
    if value < lower:
        return "-"
    if value > upper:
        return "+"
    return "0"


def _collect_values(
    rows: list[list[str]],
    classifier,
    thresholds: dict,
) -> dict[int, dict[str, tuple[str, str]]]:
    by_year: dict[int, dict[str, tuple[str, str]]] = {}
    for row in rows:
        if not row or not _is_year_row(row[0].strip()):
            continue
        year = int(row[0])
        monthly: dict[str, tuple[str, str]] = {}
        for month, value_text in zip(MONTHS, row[2:14], strict=True):
            value_text = value_text.strip()
            if not value_text:
                monthly[month] = ("", "")
                continue
            symbol = classifier(float(value_text), thresholds[month])
            monthly[month] = (value_text, symbol)
        by_year[year] = monthly
    return by_year


def render_observed_symbol_markdown(
    temperature_csv: Path,
    precipitation_csv: Path,
    output_path: Path,
) -> Path:
    temperature_rows = _read_rows(temperature_csv)
    precipitation_rows = _read_rows(precipitation_csv)

    temperature_thresholds = _parse_temperature_thresholds(temperature_rows[2])
    precipitation_thresholds = _parse_precipitation_thresholds(precipitation_rows[2])
    temperature_by_year = _collect_values(temperature_rows[3:], _classify_temperature, temperature_thresholds)
    precipitation_by_year = _collect_values(precipitation_rows[3:], _classify_precipitation, precipitation_thresholds)

    years = sorted(set(temperature_by_year) | set(precipitation_by_year), reverse=True)
    lines = [
        "# 남한 월별 실황 기호화",
        "",
        "- 기준 자료: `남한_평균기온_월별.csv`, `남한_강수량_월별.csv`",
        "- 판정 기준: 기온은 월별 `비슷범위`의 `±값`, 강수량은 월별 `비슷범위`의 `하한~상한`을 사용",
        "- 기호 의미: `-` 낮음/적음, `0` 비슷, `+` 높음/많음",
        "",
    ]

    for year in years:
        temperature = temperature_by_year.get(year, {})
        precipitation = precipitation_by_year.get(year, {})
        lines.extend(
            [
                f"## {year}",
                "",
                "| 구분 | " + " | ".join(MONTHS) + " |",
                "| --- | " + " | ".join(["---"] * len(MONTHS)) + " |",
                "| 기온 편차 | "
                + " | ".join(
                    f"{value}({symbol})" if value else ""
                    for value, symbol in (temperature.get(month, ("", "")) for month in MONTHS)
                )
                + " |",
                "| 기온 기호 | "
                + " | ".join((temperature.get(month, ("", ""))[1] for month in MONTHS))
                + " |",
                "| 강수량 | "
                + " | ".join(
                    f"{value}({symbol})" if value else ""
                    for value, symbol in (precipitation.get(month, ("", "")) for month in MONTHS)
                )
                + " |",
                "| 강수 기호 | "
                + " | ".join((precipitation.get(month, ("", ""))[1] for month in MONTHS))
                + " |",
                "",
            ]
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
