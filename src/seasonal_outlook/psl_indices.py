from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html import unescape
from pathlib import Path
import csv
import json
import re
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from .config import SystemConfig


PSL_ROOT_URL = "https://psl.noaa.gov"
PSL_CLIMATEINDICES_URL = "https://psl.noaa.gov/data/climateindices/"
PSL_LIST_URL = "https://psl.noaa.gov/data/climateindices/list/"
PSL_CAVEATS_URL = "https://psl.noaa.gov/data/climateindices/caveats.html"
PSL_TIMESERIES_MONTH_URL = "https://psl.noaa.gov/data/timeseries/month/"
TELE_INDEX_URL = "https://ftp.cpc.ncep.noaa.gov/wd52dg/data/indices/tele_index.nh"
_USER_AGENT = "seasonal-outlook/0.1 (+https://github.com/openai/codex)"
_MONTHLY_MISSING_THRESHOLD = -90.0

_TIMESERIES1_OPTION_INDEX_IDS = {
    "1": "soi",
    "2": "pna",
    "3": "nao",
    "4": "nino_3",
    "5": "nino_1_2",
    "6": "wp",
    "7": "qbo",
    "8": "nino_3_4",
    "9": "nino_4",
    "10": "hurricane_activity",
    "11": "best_longer_version",
    "12": "pdo",
    "13": "np",
    "14": "ao",
    "16": "tni_trans_nino_index",
    "17": "pacific_warmpool_region",
    "18": "tropical_pacific_sst_eof",
    "19": "atlantic_tripole_sst_eof",
    "20": "globally_integrated_angular_momentum",
    "21": "solar_flux_10_7cm",
    "23": "central_indian_precipitation_core_monsoon_region",
    "24": "sahel_rainfall",
    "25": "northeast_brazil_rainfall_anomaly",
    "26": "nao_jones",
    "27": "mei_v2",
    "28": "sw_monsoon_region_rainfall",
    "29": "global_mean_land_ocean_temperature_index",
    "30": "ep_np",
    "31": "tnh",
    "32": "atlantic_multidecadal_oscillation_long_version",
    "34": "noi",
    "35": "enso_precipitation_index",
    "36": "aao",
    "37": "tna",
    "38": "tsa",
    "39": "whwp",
    "41": "oni",
    "42": "north_tropical_atlantic_index_nta",
    "43": "caribbean_index_car",
    "44": "atlantic_meridional_mode",
    "45": "pmm",
    "46": "ace_atlantic",
    "47": "mdr_hurricanes_sst_anomaly",
    "48": "mdr_tropics_sst_anomaly",
    "49": "ao_20cr",
    "50": "aao_20cr",
    "51": "gbi",
    "52": "ace_eastern_pacific",
    "53": "nh_sea_ice_extent",
    "54": "sh_sea_ice_extent",
}

_TIMESERIES1_SUPPLEMENTAL_SPECS = (
    {
        "index_id": "gbi",
        "display_name": "GBI",
        "description": "Greenland Blocking Index (GBI) from PSL monthly time-series metadata.",
        "variants": (
            {"label": "GBI", "keyvalues_dataset_id": "GBI"},
        ),
    },
    {
        "index_id": "tnh",
        "display_name": "TNH",
        "description": "Tropical/Northern Hemisphere pattern index from PSL correlation data.",
        "variants": (
            {"label": "TNH", "url": "https://psl.noaa.gov/data/correlation/tnh.data"},
        ),
    },
    {
        "index_id": "pmm",
        "display_name": "PMM",
        "description": "Pacific Meridional Mode indices from PSL monthly time-series metadata.",
        "variants": (
            {"label": "PMM", "keyvalues_dataset_id": "PMM", "dataprefix_key": "dataprefix", "timeprefix_key": "timeprefix"},
            {"label": "PMM Wind", "keyvalues_dataset_id": "PMM", "dataprefix_key": "dataprefix2", "timeprefix_key": "timeprefix2"},
        ),
    },
    {
        "index_id": "ao_20cr",
        "display_name": "AO 20CR",
        "description": "Arctic Oscillation index from PSL 20CR monthly time-series metadata.",
        "variants": (
            {"label": "AO 20CR", "keyvalues_dataset_id": "AO20CR"},
        ),
    },
    {
        "index_id": "aao_20cr",
        "display_name": "AAO 20CR",
        "description": "Antarctic Oscillation (SAM) 20CR series exposed in PSL monthly time-series content.",
        "variants": (
            {
                "label": "AAO 20CR",
                "url": "https://psl.noaa.gov/data/20thC_Rean/timeseries/monthly/SAM/sam.20crv2c.long.data",
            },
        ),
    },
    {
        "index_id": "nh_sea_ice_extent",
        "display_name": "NH Sea-Ice Extent",
        "description": "Northern Hemisphere sea-ice extent from PSL monthly time-series metadata.",
        "variants": (
            {"label": "NH Sea-Ice Extent", "keyvalues_dataset_id": "NHICE"},
        ),
    },
    {
        "index_id": "sh_sea_ice_extent",
        "display_name": "SH Sea-Ice Extent",
        "description": "Southern Hemisphere sea-ice extent from PSL monthly time-series metadata.",
        "variants": (
            {"label": "SH Sea-Ice Extent", "keyvalues_dataset_id": "SHICE"},
        ),
    },
    {
        "index_id": "ace_atlantic",
        "display_name": "ACE Atlantic",
        "description": "Atlantic accumulated cyclone energy from PSL monthly time-series metadata.",
        "variants": (
            {"label": "ACE Atlantic", "keyvalues_dataset_id": "HURRICANE_ATL_ACE"},
        ),
    },
    {
        "index_id": "ace_eastern_pacific",
        "display_name": "ACE Eastern Pacific",
        "description": "Eastern Pacific accumulated cyclone energy from PSL monthly time-series metadata.",
        "variants": (
            {
                "label": "ACE Eastern Pacific",
                "keyvalues_dataset_id": "HURRICANE_NEPAC_ACE",
                "dataprefix_key": "dataprefix2",
            },
        ),
    },
    {
        "index_id": "mdr_hurricanes_sst_anomaly",
        "display_name": "MDR Hurricanes SST Anomaly",
        "description": "Atlantic main development region SST anomaly from PSL monthly time-series metadata.",
        "variants": (
            {"label": "MDR", "keyvalues_dataset_id": "MDR"},
        ),
    },
    {
        "index_id": "mdr_tropics_sst_anomaly",
        "display_name": "MDR - Tropics SST Anomaly",
        "description": "Listed in PSL TimeSeries1 but no current raw PSL data endpoint was found during refresh.",
        "variants": (),
        "collection_error": "time_series1_option_present_but_no_official_raw_url_found",
    },
)


@dataclass(frozen=True)
class SeriesPoint:
    year: int
    month: int
    value: float

    @property
    def label(self) -> str:
        return f"{self.year}-{self.month:02d}"


def _slugify(value: str) -> str:
    cleaned = unescape(value)
    cleaned = cleaned.replace("ñ", "n").replace("Ñ", "N")
    cleaned = re.sub(r"\*", "", cleaned)
    cleaned = re.sub(r"[^0-9A-Za-z]+", "_", cleaned)
    cleaned = cleaned.strip("_").lower()
    return cleaned or "series"


def _dedupe_slug(base: str, seen: set[str]) -> str:
    candidate = base
    index = 2
    while candidate in seen:
        candidate = f"{base}_{index}"
        index += 1
    seen.add(candidate)
    return candidate


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _strip_tags(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", fragment, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return _collapse_whitespace(unescape(text))


def _extract_links(fragment: str) -> list[dict[str, str]]:
    items = []
    pattern = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    seen: set[tuple[str, str]] = set()
    for href, label_html in pattern.findall(fragment):
        pair = (href.strip(), _strip_tags(label_html))
        if pair in seen:
            continue
        seen.add(pair)
        items.append({"href": href.strip(), "label": _strip_tags(label_html)})
    fallback_pattern = re.compile(r'<a\b[^>]*href="([^"]+)"[^>]*>([^<]+)(?=<)', re.IGNORECASE | re.DOTALL)
    for href, label_text in fallback_pattern.findall(fragment):
        pair = (href.strip(), _collapse_whitespace(unescape(label_text)))
        if pair in seen:
            continue
        seen.add(pair)
        items.append({"href": pair[0], "label": pair[1]})
    return items


def _extract_catalog_rows(html: str) -> list[tuple[str, str]]:
    match = re.search(r'<table class="table table-striped">.*?<tbody>(.*?)</tbody>', html, re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("could not locate PSL climate-indices table")

    rows = []
    for row_html in re.findall(r"<tr>(.*?)</tr>", match.group(1), re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, re.IGNORECASE | re.DOTALL)
        if len(cells) >= 2:
            rows.append((cells[0], cells[1]))
    return rows


def _is_psl_raw_data_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc.lower() != "psl.noaa.gov":
        return False
    filename = parsed.path.rsplit("/", 1)[-1].lower()
    if "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[-1]
    return extension not in {"html", "htm", "shtml", "php", "asp", "aspx", "pdf", "png", "jpg", "gif"}


def _variant_role(label: str, display_name: str) -> str:
    lowered = label.lower()
    if "long" in lowered:
        return "long"
    if "mean" in lowered:
        return "mean"
    if label == display_name:
        return "primary"
    return "alternate"


def _fetch_with_powershell(url: str, timeout_seconds: int) -> str:
    script = (
        "$ProgressPreference='SilentlyContinue';"
        f"$resp = Invoke-WebRequest -UseBasicParsing -Uri '{url}';"
        "if ($resp.Content -is [byte[]]) {"
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;"
        "[System.Text.Encoding]::UTF8.GetString($resp.Content)"
        "} else { [string]$resp.Content }"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=True,
    )
    return result.stdout


def _fetch_text(url: str, timeout_seconds: int = 60) -> str:
    request = Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "text/plain, text/html;q=0.9, */*;q=0.8"})
    errors = []
    for _ in range(2):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, "replace")
        except (HTTPError, URLError, TimeoutError, ConnectionError, OSError) as exc:
            errors.append(f"urllib: {exc}")

    try:
        return _fetch_with_powershell(url, timeout_seconds)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        errors.append(f"powershell: {exc}")

    raise RuntimeError("; ".join(errors))


def _parse_yearly_grid(text: str) -> tuple[SeriesPoint, ...]:
    rows = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 13 and parts[0].isdigit() and len(parts[0]) == 4:
            year = int(parts[0])
            for month, token in enumerate(parts[1:13], start=1):
                value = float(token)
                if value <= _MONTHLY_MISSING_THRESHOLD:
                    continue
                rows.append(SeriesPoint(year=year, month=month, value=value))
    return tuple(rows)


def _parse_year_month_value(text: str) -> tuple[SeriesPoint, ...]:
    rows = []
    for raw_line in text.splitlines():
        parts = raw_line.split()
        if len(parts) < 3 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        year = int(parts[0])
        month = int(parts[1])
        if not 1 <= month <= 12:
            continue
        value = float(parts[2])
        if value <= _MONTHLY_MISSING_THRESHOLD:
            continue
        rows.append(SeriesPoint(year=year, month=month, value=value))
    return tuple(rows)


def _parse_series(text: str) -> tuple[str, tuple[SeriesPoint, ...]]:
    for parser_name, parser in (("yearly_grid", _parse_yearly_grid), ("year_month_value", _parse_year_month_value)):
        points = parser(text)
        if points:
            return parser_name, points
    return "unknown", ()


def _fetch_json(url: str, timeout_seconds: int = 60) -> dict[str, object]:
    return json.loads(_fetch_text(url, timeout_seconds=timeout_seconds), strict=False)


def _freshness(issue_date: date, latest_point: SeriesPoint) -> str:
    months_diff = (issue_date.year - latest_point.year) * 12 + (issue_date.month - latest_point.month)
    if months_diff <= 1:
        return "fresh"
    if months_diff <= 4:
        return "usable_with_lag"
    if months_diff <= 12:
        return "stale"
    return "historical_only"


def _outlook_role(regularly_updated: bool, freshness: str) -> str:
    if freshness in {"fresh", "usable_with_lag"}:
        return "current" if regularly_updated else "current_reference"
    if freshness == "stale":
        return "lagged_background"
    return "historical_reference"


def _write_series_csv(path: Path, points: tuple[SeriesPoint, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "year", "month", "value"])
        for point in points:
            writer.writerow([point.label, point.year, point.month, f"{point.value:.6f}"])


def _preferred_variant_index(variants: list[dict]) -> int | None:
    ranked: list[tuple[int, int]] = []
    for idx, variant in enumerate(variants):
        if variant["parse_status"] != "ok":
            continue
        latest = variant.get("latest_month", "0000-00")
        latest_score = int(latest.replace("-", ""))
        role_bonus = {"long": 30, "primary": 20, "alternate": 10, "mean": 0}[variant["variant_role"]]
        ranked.append((latest_score * 10000 + role_bonus * 100 + variant["point_count"], idx))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    return ranked[0][1]


def _catalog_entry_from_row(name_cell: str, description_cell: str, seen_ids: set[str]) -> dict[str, object]:
    display_name = _strip_tags(name_cell)
    clean_name = display_name.replace("*", "").strip()
    entry_id = _dedupe_slug(_slugify(clean_name), seen_ids)
    description = _strip_tags(description_cell)
    regularly_updated = "*" in display_name

    variant_seen: set[str] = set()
    variants = []
    for item in _extract_links(name_cell) + _extract_links(description_cell):
        absolute_url = urljoin(PSL_LIST_URL, item["href"])
        if not _is_psl_raw_data_url(absolute_url):
            continue
        if any(existing["url"] == absolute_url for existing in variants):
            continue
        label = item["label"] or Path(urlparse(absolute_url).path).name
        variant_id = _dedupe_slug(_slugify(label), variant_seen)
        variants.append(
            {
                "variant_id": variant_id,
                "label": label,
                "url": absolute_url,
                "variant_role": _variant_role(label, display_name),
            }
        )

    return {
        "index_id": entry_id,
        "display_name": display_name,
        "name": clean_name,
        "regularly_updated": regularly_updated,
        "description": description,
        "variants": variants,
    }


def _extract_timeseries1_options(html: str) -> list[dict[str, str]]:
    match = re.search(r'<select[^>]+id="tstype1"[^>]*>(.*?)</select>', html, re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("could not locate PSL TimeSeries1 select")

    options = []
    for value, label_html in re.findall(r'<option[^>]*value="([^"]+)"[^>]*>(.*?)</option>', match.group(1), re.IGNORECASE | re.DOTALL):
        label = _strip_tags(label_html)
        options.append({"value": value.strip(), "label": label})
    return options


def _raw_url_from_keyvalues(payload: dict[str, object], *, dataprefix_key: str = "dataprefix", timeprefix_key: str = "timeprefix") -> str | None:
    dataprefix = str(payload.get(dataprefix_key, "") or "").strip()
    timeprefix = str(payload.get(timeprefix_key, "") or "").strip()
    if not dataprefix or not timeprefix:
        return None
    if not dataprefix.endswith(".data"):
        dataprefix = f"{dataprefix}.data"
    return urljoin(PSL_ROOT_URL, f"{timeprefix}{dataprefix}")


def _catalog_entry_from_supplemental_spec(spec: dict[str, object], seen_ids: set[str]) -> dict[str, object]:
    entry_id = _dedupe_slug(str(spec["index_id"]), seen_ids)
    description = str(spec.get("description", ""))
    collection_error = spec.get("collection_error")
    variants = []
    variant_seen: set[str] = set()
    keyvalues_cache: dict[str, dict[str, object]] = {}

    for variant_spec in spec.get("variants", ()):
        variant_spec = dict(variant_spec)
        url = variant_spec.get("url")
        keyvalues_dataset_id = variant_spec.get("keyvalues_dataset_id")
        if not url and keyvalues_dataset_id:
            dataset_id = str(keyvalues_dataset_id)
            payload = keyvalues_cache.get(dataset_id)
            if payload is None:
                keyvalues_url = urljoin(PSL_TIMESERIES_MONTH_URL, f"{dataset_id}/keyvalues.json")
                payload = _fetch_json(keyvalues_url)
                keyvalues_cache[dataset_id] = payload
            url = _raw_url_from_keyvalues(
                payload,
                dataprefix_key=str(variant_spec.get("dataprefix_key", "dataprefix")),
                timeprefix_key=str(variant_spec.get("timeprefix_key", "timeprefix")),
            )
            if not description:
                description = _strip_tags(str(payload.get("descriptionshort", "") or payload.get("description", "")))
        if not url:
            continue
        label = str(variant_spec.get("label", Path(urlparse(str(url)).path).name))
        variant_id = _dedupe_slug(_slugify(label), variant_seen)
        variants.append(
            {
                "variant_id": variant_id,
                "label": label,
                "url": str(url),
                "variant_role": _variant_role(label, str(spec["display_name"])),
            }
        )

    entry = {
        "index_id": entry_id,
        "display_name": str(spec["display_name"]),
        "name": str(spec["display_name"]),
        "regularly_updated": bool(spec.get("regularly_updated", False)),
        "description": description,
        "variants": variants,
        "catalog_source": "timeseries1_supplemental",
    }
    if collection_error:
        entry["collection_error"] = str(collection_error)
    return entry


def _append_missing_timeseries1_entries(entries: list[dict[str, object]], timeseries1_options: list[dict[str, str]], seen_ids: set[str]) -> list[dict[str, object]]:
    existing_ids = {str(entry["index_id"]) for entry in entries}
    for option in timeseries1_options:
        option_value = option["value"]
        target_index_id = _TIMESERIES1_OPTION_INDEX_IDS.get(option_value)
        if not target_index_id or target_index_id in existing_ids:
            continue
        spec = next((item for item in _TIMESERIES1_SUPPLEMENTAL_SPECS if item["index_id"] == target_index_id), None)
        if spec is None:
            spec = {
                "index_id": target_index_id,
                "display_name": option["label"],
                "description": "Listed in PSL TimeSeries1 but no current collector mapping exists yet.",
                "variants": (),
                "collection_error": "time_series1_option_present_but_not_mapped",
            }
        entry = _catalog_entry_from_supplemental_spec(spec, seen_ids)
        entry["timeseries1_option"] = option
        entries.append(entry)
        existing_ids.add(str(entry["index_id"]))
    return entries


def _repair_known_entry_variants(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    repairs = {
        "tpi_ipo": (
            {
                "label": "TPI(IPO)",
                "url": "https://psl.noaa.gov/data/timeseries/IPOTPI/ipotpi.hadisst2.data",
            },
        ),
    }
    for entry in entries:
        if entry.get("variants"):
            continue
        specs = repairs.get(str(entry.get("index_id")))
        if not specs:
            continue
        variant_seen: set[str] = set()
        variants = []
        for spec in specs:
            label = str(spec["label"])
            url = str(spec["url"])
            variants.append(
                {
                    "variant_id": _dedupe_slug(_slugify(label), variant_seen),
                    "label": label,
                    "url": url,
                    "variant_role": _variant_role(label, str(entry["display_name"])),
                }
            )
        entry["variants"] = variants
        entry["catalog_source"] = "list_manual_repair"
    return entries


def _build_timeseries1_audit(options: list[dict[str, str]], entries: list[dict[str, object]]) -> dict[str, object]:
    entry_by_id = {str(entry["index_id"]): entry for entry in entries}
    items = []
    summary_counts = {"collected": 0, "raw_only": 0, "missing_source": 0, "unparsed": 0, "fetch_error": 0}

    for option in options:
        if option["value"] == "99":
            continue
        target_index_id = _TIMESERIES1_OPTION_INDEX_IDS.get(option["value"])
        entry = entry_by_id.get(target_index_id or "")

        status = "missing_source"
        latest_month = None
        latest_value = None
        matched_display_name = None
        collection_error = None
        if entry is not None:
            matched_display_name = str(entry.get("display_name", ""))
            collection_error = entry.get("collection_error")
            preferred = entry.get("preferred")
            variants = entry.get("variants", [])
            if preferred:
                status = "collected"
                latest_month = preferred.get("latest_month")
                latest_value = preferred.get("latest_value")
            elif not variants:
                status = "missing_source"
            else:
                parse_statuses = {variant.get("parse_status") for variant in variants}
                fetch_statuses = {variant.get("fetch_status") for variant in variants}
                if "ok" in fetch_statuses and parse_statuses <= {"unparsed", "pending"}:
                    status = "unparsed"
                elif "error" in fetch_statuses and "ok" not in fetch_statuses:
                    status = "fetch_error"
                else:
                    status = "raw_only"

        if status in summary_counts:
            summary_counts[status] += 1

        items.append(
            {
                "value": option["value"],
                "label": option["label"],
                "index_id": target_index_id,
                "matched_display_name": matched_display_name,
                "status": status,
                "latest_month": latest_month,
                "latest_value": latest_value,
                "collection_error": collection_error,
            }
        )

    return {
        "source_url": PSL_CLIMATEINDICES_URL,
        "option_count": len(options),
        "non_custom_count": len(items),
        "counts": summary_counts,
        "options": items,
    }


def _parse_tele_index_rows(text: str) -> list[dict[str, object]]:
    rows = []
    for raw_line in text.splitlines():
        parts = re.findall(r"[-+]?\d+(?:\.\d+)?", raw_line)
        if len(parts) < 13 or len(parts[0]) != 4:
            continue
        row = {
            "year": int(parts[0]),
            "month": int(parts[1]),
            "values": {
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
                "ExplainedVariance": float(parts[12]),
            },
        }
        rows.append(row)
    return rows


def load_psl_latest_snapshot(config: SystemConfig) -> dict | None:
    path = config.psl_indices_dir() / "latest_snapshot.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def refresh_psl_indices(config: SystemConfig, issue_date: date) -> dict[str, Path]:
    base_dir = config.psl_indices_dir()
    raw_dir = base_dir / "raw"
    normalized_dir = base_dir / "normalized"
    supplemental_dir = base_dir / "supplemental"
    base_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    supplemental_dir.mkdir(parents=True, exist_ok=True)

    climateindices_html = _fetch_text(PSL_CLIMATEINDICES_URL)
    climateindices_html_path = base_dir / "climateindices_page.html"
    climateindices_html_path.write_text(climateindices_html, encoding="utf-8")

    monthly_html = _fetch_text(PSL_TIMESERIES_MONTH_URL)
    monthly_html_path = base_dir / "timeseries_month.html"
    monthly_html_path.write_text(monthly_html, encoding="utf-8")

    catalog_html = _fetch_text(PSL_LIST_URL)
    catalog_html_path = base_dir / "catalog.html"
    catalog_html_path.write_text(catalog_html, encoding="utf-8")

    seen_ids: set[str] = set()
    entries = [_catalog_entry_from_row(name_cell, description_cell, seen_ids) for name_cell, description_cell in _extract_catalog_rows(catalog_html)]
    timeseries1_options = _extract_timeseries1_options(climateindices_html)
    entries = _append_missing_timeseries1_entries(entries, timeseries1_options, seen_ids)
    entries = _repair_known_entry_variants(entries)

    fetch_failures = 0
    parse_failures = 0
    preferred_variants = []

    for entry in entries:
        index_dir = raw_dir / entry["index_id"]
        csv_dir = normalized_dir / entry["index_id"]
        index_dir.mkdir(parents=True, exist_ok=True)
        csv_dir.mkdir(parents=True, exist_ok=True)

        hydrated_variants = []
        for variant in entry["variants"]:
            filename = Path(urlparse(variant["url"]).path).name
            if "." in filename:
                suffix = "." + filename.split(".", 1)[1]
            else:
                suffix = ".txt"
            raw_path = index_dir / f"{variant['variant_id']}{suffix}"
            csv_path = csv_dir / f"{variant['variant_id']}.csv"

            hydrated = {
                **variant,
                "raw_path": str(raw_path),
                "csv_path": str(csv_path),
                "fetch_status": "pending",
                "parse_status": "pending",
                "parser": "",
                "point_count": 0,
                "start_month": None,
                "latest_month": None,
                "latest_value": None,
                "freshness": None,
                "outlook_role": None,
                "error": None,
            }

            try:
                text = _fetch_text(variant["url"])
                raw_path.write_text(text, encoding="utf-8")
                hydrated["fetch_status"] = "ok"
            except RuntimeError as exc:
                hydrated["fetch_status"] = "error"
                hydrated["parse_status"] = "skipped"
                hydrated["error"] = str(exc)
                fetch_failures += 1
                hydrated_variants.append(hydrated)
                continue

            parser_name, points = _parse_series(text)
            if not points:
                hydrated["parse_status"] = "unparsed"
                hydrated["parser"] = parser_name
                hydrated["error"] = "no monthly series parsed"
                parse_failures += 1
                hydrated_variants.append(hydrated)
                continue

            _write_series_csv(csv_path, points)
            latest = points[-1]
            hydrated["parse_status"] = "ok"
            hydrated["parser"] = parser_name
            hydrated["point_count"] = len(points)
            hydrated["start_month"] = points[0].label
            hydrated["latest_month"] = latest.label
            hydrated["latest_value"] = round(latest.value, 6)
            hydrated["freshness"] = _freshness(issue_date, latest)
            hydrated["outlook_role"] = _outlook_role(bool(entry["regularly_updated"]), hydrated["freshness"])
            hydrated_variants.append(hydrated)

        preferred_index = _preferred_variant_index(hydrated_variants)
        preferred_variant_id = None
        preferred_snapshot = None
        if preferred_index is not None:
            preferred = hydrated_variants[preferred_index]
            preferred_variant_id = preferred["variant_id"]
            preferred_snapshot = {
                "index_id": entry["index_id"],
                "name": entry["name"],
                "display_name": entry["display_name"],
                "regularly_updated": entry["regularly_updated"],
                "preferred_variant_id": preferred["variant_id"],
                "preferred_label": preferred["label"],
                "preferred_url": preferred["url"],
                "latest_month": preferred["latest_month"],
                "latest_value": preferred["latest_value"],
                "freshness": preferred["freshness"],
                "outlook_role": preferred["outlook_role"],
                "point_count": preferred["point_count"],
                "csv_path": preferred["csv_path"],
                "raw_path": preferred["raw_path"],
            }
            preferred_variants.append(preferred_snapshot)

        entry["variant_count"] = len(hydrated_variants)
        entry["preferred_variant_id"] = preferred_variant_id
        entry["variants"] = hydrated_variants
        entry["preferred"] = preferred_snapshot

    tele_text = _fetch_text(TELE_INDEX_URL)
    tele_raw_path = supplemental_dir / "cpc_tele_index_nh.txt"
    tele_raw_path.write_text(tele_text, encoding="utf-8")
    tele_rows = _parse_tele_index_rows(tele_text)
    tele_latest = tele_rows[-1] if tele_rows else None
    tele_json_path = supplemental_dir / "cpc_tele_index_nh_latest.json"
    tele_payload = {
        "source_url": TELE_INDEX_URL,
        "row_count": len(tele_rows),
        "latest": {
            "month": f"{tele_latest['year']}-{tele_latest['month']:02d}",
            "values": tele_latest["values"],
        }
        if tele_latest
        else None,
        "raw_path": str(tele_raw_path),
    }
    tele_json_path.write_text(json.dumps(tele_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    freshness_counts = {"fresh": 0, "usable_with_lag": 0, "stale": 0, "historical_only": 0}
    for item in preferred_variants:
        freshness = item["freshness"]
        if freshness in freshness_counts:
            freshness_counts[freshness] += 1

    timeseries1_audit = _build_timeseries1_audit(timeseries1_options, entries)

    summary = {
        "issue_date": issue_date.isoformat(),
        "source_url": PSL_LIST_URL,
        "climateindices_url": PSL_CLIMATEINDICES_URL,
        "timeseries_month_url": PSL_TIMESERIES_MONTH_URL,
        "caveats_url": PSL_CAVEATS_URL,
        "index_count": len(entries),
        "variant_count": sum(int(entry["variant_count"]) for entry in entries),
        "preferred_count": len(preferred_variants),
        "fetch_failures": fetch_failures,
        "parse_failures": parse_failures,
        "timeseries1_option_count": timeseries1_audit["non_custom_count"],
        "timeseries1_collected_count": timeseries1_audit["counts"]["collected"],
        "timeseries1_unparsed_count": timeseries1_audit["counts"]["unparsed"],
        "timeseries1_missing_source_count": timeseries1_audit["counts"]["missing_source"],
        "timeseries1_fetch_error_count": timeseries1_audit["counts"]["fetch_error"],
        **freshness_counts,
    }

    catalog_payload = {
        "summary": summary,
        "indices": entries,
        "supplemental": {"tele_index_nh": tele_payload, "timeseries1": timeseries1_audit},
    }
    catalog_json_path = base_dir / "catalog.json"
    catalog_json_path.write_text(json.dumps(catalog_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    latest_snapshot = {
        "summary": summary,
        "indices": preferred_variants,
        "supplemental": {"tele_index_nh": tele_payload, "timeseries1": timeseries1_audit},
    }
    latest_snapshot_path = base_dir / "latest_snapshot.json"
    latest_snapshot_path.write_text(json.dumps(latest_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    timeseries1_audit_path = base_dir / "timeseries1_audit.json"
    timeseries1_audit_path.write_text(json.dumps(timeseries1_audit, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "climateindices_html": climateindices_html_path,
        "catalog_html": catalog_html_path,
        "catalog_json": catalog_json_path,
        "latest_snapshot": latest_snapshot_path,
        "raw_dir": raw_dir,
        "normalized_dir": normalized_dir,
        "timeseries_month_html": monthly_html_path,
        "timeseries1_audit": timeseries1_audit_path,
        "tele_index_latest": tele_json_path,
    }
