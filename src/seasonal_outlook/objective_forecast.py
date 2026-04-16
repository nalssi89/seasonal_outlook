from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import json
import math
from pathlib import Path
import re
import time
import tomllib
import warnings

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from lightgbm import LGBMClassifier
except ImportError:  # pragma: no cover
    LGBMClassifier = None

try:
    from xgboost import XGBClassifier
except ImportError:  # pragma: no cover
    XGBClassifier = None

try:
    from catboost import CatBoostClassifier
except ImportError:  # pragma: no cover
    CatBoostClassifier = None

from .config import SystemConfig
from .models import ObjectiveForecastCell, ObjectiveForecastRun, ProbabilityTriple, TargetMonth
from .psl_indices import _parse_series, _parse_tele_index_rows


VARIABLE_LABELS = {"temperature": "기온", "precipitation": "강수"}
MODEL_LABELS = {
    "climatology": "기후평년",
    "analog_knn": "유사사례 kNN",
    "softmax": "소프트맥스 회귀",
    "lightgbm": "LightGBM",
    "xgboost": "XGBoost",
    "catboost": "CatBoost",
}
SOURCE_TYPE_LABELS = {
    "psl_preferred": "PSL 대표 시계열",
    "tele_index": "CPC tele_index",
    "manual_snapshot_only": "스냅샷 해석값",
}
FRESHNESS_LABELS = {
    "fresh": "최신",
    "usable_with_lag": "시차 허용",
    "stale": "지연",
    "snapshot_only": "스냅샷 전용",
}
FEATURE_SUFFIX_LABELS = {
    "m0": "최신 가용값",
    "m1": "1개월 전",
    "roll3": "3개월 평균",
    "delta1": "1개월 변화",
    "sym0": "최신 기호값",
    "sym_roll3": "3개월 기호평균",
}
CLASS_ORDER = ("-", "0", "+")
CLASS_TO_INDEX = {label: idx for idx, label in enumerate(CLASS_ORDER)}
INDEX_TO_CLASS = {idx: label for label, idx in CLASS_TO_INDEX.items()}
INCLUDED_FRESHNESS = {"fresh", "usable_with_lag", "stale"}
CURRENT_FRESHNESS = {"fresh", "usable_with_lag"}
OPER_LAGS = {"oni": 2, "qbo": 2}
MIN_TRAIN_ROWS = 120
BACKTEST_START = (1993, 1)


@dataclass(frozen=True)
class PredictorSpec:
    predictor_id: str
    display_name: str
    source_type: str
    operational_lag: int
    freshness: str
    role: str
    use_in_current: bool
    raw_path: Path | None = None
    column: str | None = None
    history_ready: bool = True
    notes: str = ""


def _objective_dir(config: SystemConfig) -> Path:
    path = config.objective_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _reports_dir_for_issue(config: SystemConfig, issue_date: date) -> Path:
    path = config.reports_dir() / issue_date.isoformat()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _month_key(year: int, month: int) -> tuple[int, int]:
    return year, month


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    month_index = year * 12 + (month - 1) + delta
    return month_index // 12, month_index % 12 + 1


def _month_ordinal(year: int, month: int) -> int:
    return year * 12 + month


def _normalize_history_end(history_end: tuple[int, int] | None) -> tuple[int, int] | None:
    if history_end is None:
        return None
    year, month = history_end
    return int(year), int(month)


def _within_history_end(year: int, month: int, history_end: tuple[int, int] | None) -> bool:
    if history_end is None:
        return True
    end_year, end_month = history_end
    return _month_ordinal(year, month) <= _month_ordinal(end_year, end_month)


def _serialize_probability(probabilities: ProbabilityTriple) -> dict[str, float]:
    return probabilities.as_dict()


def _to_probability(probabilities: dict[str, float]) -> ProbabilityTriple:
    return ProbabilityTriple(
        lower=float(probabilities["lower"]),
        normal=float(probabilities["normal"]),
        upper=float(probabilities["upper"]),
    ).normalized()


def _forecast_symbol(probabilities: ProbabilityTriple) -> str:
    score = probabilities.upper - probabilities.lower
    if score >= 0.08:
        return "+"
    if score <= -0.08:
        return "-"
    return "0"


def _display_model_name(model_id: str) -> str:
    return MODEL_LABELS.get(model_id, model_id)


def _format_weights(weights: tuple[tuple[str, float], ...] | dict[str, float]) -> str:
    items = weights.items() if isinstance(weights, dict) else weights
    return ", ".join(f"{_display_model_name(name)}={float(weight):.2f}" for name, weight in items)


def _feature_display_name(feature_name: str, predictors: list[PredictorSpec]) -> str:
    if "__" not in feature_name:
        return feature_name
    prefix, suffix = feature_name.split("__", 1)
    if prefix == "obs_temperature":
        base = "관측 기온"
    elif prefix == "obs_precipitation":
        base = "관측 강수"
    else:
        predictor = next((item for item in predictors if item.predictor_id == prefix), None)
        base = predictor.display_name if predictor else prefix
    return f"{base} {FEATURE_SUFFIX_LABELS.get(suffix, suffix)}"


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    last_error: OSError | None = None
    for _ in range(20):
        try:
            temporary.replace(path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.1)
    if last_error is not None:
        raise last_error


def _value_symbol(cell: str) -> tuple[float | None, str | None]:
    cleaned = cell.strip()
    if not cleaned:
        return None, None
    match = re.fullmatch(r"\s*([-+]?\d+(?:\.\d+)?)\(([+\-0])\)\s*", cleaned)
    if not match:
        return None, None
    return float(match.group(1)), match.group(2)


def _observed_markdown_path(config: SystemConfig) -> Path:
    directory = config.root / "inputs" / "observed_symbols"
    matches = sorted(directory.glob("*.md"))
    if not matches:
        raise FileNotFoundError(f"No observed symbol markdown found in {directory}")
    return matches[0]


def _climate_factor_snapshot_path(config: SystemConfig, issue_date: date) -> Path | None:
    candidate = config.factors_dir() / f"{issue_date.isoformat()}.toml"
    if candidate.exists():
        return candidate
    matches: list[tuple[date, Path]] = []
    for path in sorted(config.factors_dir().glob("*.toml")):
        try:
            path_date = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if path_date <= issue_date:
            matches.append((path_date, path))
    return matches[-1][1] if matches else None


def _load_observed_monthly(config: SystemConfig) -> dict[tuple[int, int], dict[str, float | str | None]]:
    path = _observed_markdown_path(config)
    lines = path.read_text(encoding="utf-8").splitlines()
    observed: dict[tuple[int, int], dict[str, float | str | None]] = {}
    year: int | None = None
    temperature_values: list[str] = []
    temperature_symbols: list[str] = []
    precipitation_values: list[str] = []
    precipitation_symbols: list[str] = []

    def flush_year(current_year: int | None) -> None:
        if current_year is None:
            return
        for month in range(1, 13):
            temperature_value, temperature_symbol = _value_symbol(temperature_values[month - 1]) if temperature_values else (None, None)
            precipitation_value, precipitation_symbol = _value_symbol(precipitation_values[month - 1]) if precipitation_values else (None, None)
            direct_temp_symbol = temperature_symbols[month - 1].strip() or temperature_symbol
            direct_precip_symbol = precipitation_symbols[month - 1].strip() or precipitation_symbol
            observed[_month_key(current_year, month)] = {
                "temperature_value": temperature_value,
                "temperature_symbol": direct_temp_symbol,
                "precipitation_value": precipitation_value,
                "precipitation_symbol": direct_precip_symbol,
            }

    for line in lines:
        if line.startswith("## "):
            flush_year(year)
            year = int(line[3:].strip())
            temperature_values = []
            temperature_symbols = []
            precipitation_values = []
            precipitation_symbols = []
            continue
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells:
            continue
        label = cells[0]
        values = cells[1:13]
        if label == "기온 편차":
            temperature_values = values
        elif label == "기온 기호":
            temperature_symbols = values
        elif label == "강수량":
            precipitation_values = values
        elif label == "강수 기호":
            precipitation_symbols = values

    flush_year(year)
    return observed


def _load_psl_predictors(config: SystemConfig) -> tuple[list[PredictorSpec], dict[str, dict[tuple[int, int], float]]]:
    catalog = json.loads((config.psl_indices_dir() / "catalog.json").read_text(encoding="utf-8"))
    predictors: list[PredictorSpec] = []
    series_by_predictor: dict[str, dict[tuple[int, int], float]] = {}

    for item in catalog["indices"]:
        preferred = item.get("preferred") or {}
        freshness = preferred.get("freshness")
        raw_path_text = preferred.get("raw_path")
        if freshness not in INCLUDED_FRESHNESS or not raw_path_text:
            continue
        raw_path = Path(raw_path_text)
        if not raw_path.exists():
            continue
        parser_name, points = _parse_series(raw_path.read_text(encoding="utf-8", errors="replace"))
        if not points:
            continue
        predictor_id = str(item["index_id"])
        predictors.append(
            PredictorSpec(
                predictor_id=predictor_id,
                display_name=str(item["display_name"]),
                source_type="psl_preferred",
                operational_lag=OPER_LAGS.get(predictor_id, 1),
                freshness=str(freshness),
                role=str(preferred.get("outlook_role", "")),
                use_in_current=freshness in CURRENT_FRESHNESS,
                raw_path=raw_path,
                notes=f"parser={parser_name}",
            )
        )
        series_by_predictor[predictor_id] = {
            _month_key(point.year, point.month): float(point.value)
            for point in points
        }

    tele_path = config.psl_indices_dir() / "supplemental" / "cpc_tele_index_nh.txt"
    if tele_path.exists():
        rows = _parse_tele_index_rows(tele_path.read_text(encoding="utf-8", errors="replace"))
        for column in ("NAO", "EA", "WP", "EP/NP", "PNA", "EA/WR", "SCA", "TNH", "POL", "PT", "ExplainedVariance"):
            predictor_id = "tele_" + re.sub(r"[^a-z0-9]+", "_", column.lower()).strip("_")
            predictors.append(
                PredictorSpec(
                    predictor_id=predictor_id,
                    display_name=f"CPC {column}",
                    source_type="tele_index",
                    operational_lag=1,
                    freshness="fresh",
                    role="current_reference",
                    use_in_current=True,
                    raw_path=tele_path,
                    column=column,
                )
            )
            values: dict[tuple[int, int], float] = {}
            for row in rows:
                value = float(row["values"][column])
                if value <= -99.0:
                    continue
                values[_month_key(int(row["year"]), int(row["month"]))] = value
            series_by_predictor[predictor_id] = values

    return predictors, series_by_predictor


def _load_manual_snapshot_specs(config: SystemConfig, issue_date: date) -> list[PredictorSpec]:
    snapshot_path = _climate_factor_snapshot_path(config, issue_date)
    if snapshot_path is None:
        return []
    raw = tomllib.loads(snapshot_path.read_text(encoding="utf-8"))
    return [
        PredictorSpec(
            predictor_id=str(factor["id"]),
            display_name=str(factor["name"]),
            source_type="manual_snapshot_only",
            operational_lag=0,
            freshness="snapshot_only",
            role=str(factor.get("family", "")),
            use_in_current=False,
            history_ready=False,
            notes="현재 해석값만 있으며 과거 학습용 시계열은 아직 연결되지 않음",
        )
        for factor in raw.get("factors", [])
    ]


def _feature_cutoff(issue_year: int, issue_month: int, lag_months: int) -> tuple[int, int]:
    return _add_months(issue_year, issue_month, -lag_months)


def _series_value(series: dict[tuple[int, int], float], year: int, month: int) -> float:
    value = series.get(_month_key(year, month))
    return float(value) if value is not None else math.nan


def _rolling_mean(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return math.nan
    return float(sum(finite) / len(finite))


def _symbol_score(symbol: str | None) -> float:
    if symbol == "-":
        return -1.0
    if symbol == "+":
        return 1.0
    if symbol == "0":
        return 0.0
    return math.nan


def _build_truth_rows(
    observed: dict[tuple[int, int], dict[str, float | str | None]],
    history_end: tuple[int, int] | None = None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for issue_year, issue_month in sorted(observed):
        for lead in (1, 2, 3):
            target_year, target_month = _add_months(issue_year, issue_month, lead)
            if not _within_history_end(target_year, target_month, history_end):
                continue
            target = observed.get(_month_key(target_year, target_month))
            if target is None:
                continue
            for variable in ("temperature", "precipitation"):
                value = target[f"{variable}_value"]
                symbol = target[f"{variable}_symbol"]
                if value is None or symbol not in CLASS_TO_INDEX:
                    continue
                rows.append(
                    {
                        "issue_year": issue_year,
                        "issue_month": issue_month,
                        "lead": lead,
                        "variable": variable,
                        "target_year": target_year,
                        "target_month": target_month,
                        "observed_value": float(value),
                        "observed_symbol": str(symbol),
                        "observed_class": CLASS_TO_INDEX[str(symbol)],
                    }
                )
    return rows


def _build_feature_rows(
    observed: dict[tuple[int, int], dict[str, float | str | None]],
    truth_rows: list[dict[str, object]],
    predictors: list[PredictorSpec],
    series_by_predictor: dict[str, dict[tuple[int, int], float]],
    *,
    current_issue_date: date | None = None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for truth in truth_rows:
        issue_year = int(truth["issue_year"])
        issue_month = int(truth["issue_month"])
        target_year = int(truth["target_year"])
        target_month = int(truth["target_month"])
        current_mode = current_issue_date is not None and issue_year == current_issue_date.year and issue_month == current_issue_date.month

        row = dict(truth)
        row["issue_ordinal"] = _month_ordinal(issue_year, issue_month)
        row["target_ordinal"] = _month_ordinal(target_year, target_month)
        row["issue_trend"] = (row["issue_ordinal"] - _month_ordinal(1973, 1)) / 120.0
        row["target_trend"] = (row["target_ordinal"] - _month_ordinal(1973, 1)) / 120.0
        row["issue_month_sin"] = math.sin(2 * math.pi * issue_month / 12.0)
        row["issue_month_cos"] = math.cos(2 * math.pi * issue_month / 12.0)
        row["target_month_sin"] = math.sin(2 * math.pi * target_month / 12.0)
        row["target_month_cos"] = math.cos(2 * math.pi * target_month / 12.0)

        for variable in ("temperature", "precipitation"):
            prev1 = observed.get(_month_key(*_add_months(issue_year, issue_month, -1)), {})
            prev2 = observed.get(_month_key(*_add_months(issue_year, issue_month, -2)), {})
            prev3 = observed.get(_month_key(*_add_months(issue_year, issue_month, -3)), {})
            values = []
            symbols = []
            for source in (prev1, prev2, prev3):
                raw_value = source.get(f"{variable}_value")
                values.append(float(raw_value) if raw_value is not None else math.nan)
                symbols.append(_symbol_score(source.get(f"{variable}_symbol") if isinstance(source.get(f"{variable}_symbol"), str) else None))
            row[f"obs_{variable}__m0"] = values[0]
            row[f"obs_{variable}__m1"] = values[1]
            row[f"obs_{variable}__roll3"] = _rolling_mean(values)
            row[f"obs_{variable}__delta1"] = values[0] - values[1] if math.isfinite(values[0]) and math.isfinite(values[1]) else math.nan
            row[f"obs_{variable}__sym0"] = symbols[0]
            row[f"obs_{variable}__sym_roll3"] = _rolling_mean(symbols)

        for predictor in predictors:
            if not predictor.history_ready:
                continue
            feature_prefix = predictor.predictor_id
            if current_mode and not predictor.use_in_current:
                row[f"{feature_prefix}__m0"] = math.nan
                row[f"{feature_prefix}__m1"] = math.nan
                row[f"{feature_prefix}__roll3"] = math.nan
                row[f"{feature_prefix}__delta1"] = math.nan
                continue
            series = series_by_predictor.get(predictor.predictor_id, {})
            cutoff_year, cutoff_month = _feature_cutoff(issue_year, issue_month, predictor.operational_lag)
            prev_year, prev_month = _add_months(cutoff_year, cutoff_month, -1)
            prev2_year, prev2_month = _add_months(cutoff_year, cutoff_month, -2)
            latest = _series_value(series, cutoff_year, cutoff_month)
            prev1 = _series_value(series, prev_year, prev_month)
            prev2 = _series_value(series, prev2_year, prev2_month)
            row[f"{feature_prefix}__m0"] = latest
            row[f"{feature_prefix}__m1"] = prev1
            row[f"{feature_prefix}__roll3"] = _rolling_mean([latest, prev1, prev2])
            row[f"{feature_prefix}__delta1"] = latest - prev1 if math.isfinite(latest) and math.isfinite(prev1) else math.nan

        rows.append(row)
    return rows


def _feature_columns(feature_rows: list[dict[str, object]]) -> list[str]:
    if not feature_rows:
        return []
    excluded = {
        "issue_year",
        "issue_month",
        "lead",
        "variable",
        "target_year",
        "target_month",
        "observed_value",
        "observed_symbol",
        "observed_class",
        "issue_ordinal",
        "target_ordinal",
    }
    return [column for column in feature_rows[0] if column not in excluded]


def _select_feature_columns(rows: list[dict[str, object]], feature_names: list[str]) -> list[str]:
    if not rows:
        return []
    selected = []
    threshold = max(24, int(len(rows) * 0.30))
    for feature in feature_names:
        values = np.array([row[feature] for row in rows], dtype=float)
        finite_count = int(np.isfinite(values).sum())
        if finite_count < threshold:
            continue
        if finite_count == 0 or float(np.nanstd(values)) < 1e-9:
            continue
        selected.append(feature)
    return selected


def _rows_to_matrix(rows: list[dict[str, object]], feature_names: list[str]) -> np.ndarray:
    return np.array([[float(row[feature]) for feature in feature_names] for row in rows], dtype=float)


def _fit_climatology(rows: list[dict[str, object]]) -> dict[int, np.ndarray]:
    by_month: dict[int, np.ndarray] = {}
    for month in range(1, 13):
        counts = np.ones(3, dtype=float)
        for row in rows:
            if int(row["issue_month"]) == month:
                counts[int(row["observed_class"])] += 1.0
        by_month[month] = counts / counts.sum()
    return by_month


def _predict_climatology(model: dict[int, np.ndarray], issue_month: int) -> np.ndarray:
    return model[int(issue_month)]


def _fit_knn(train_rows: list[dict[str, object]], feature_names: list[str]):
    neighbors = min(25, max(5, int(round(math.sqrt(len(train_rows))))))
    pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("clf", KNeighborsClassifier(n_neighbors=neighbors, weights="distance")),
        ]
    )
    pipeline.fit(
        _rows_to_matrix(train_rows, feature_names),
        np.array([int(row["observed_class"]) for row in train_rows], dtype=int),
    )
    return pipeline


def _fit_logistic(train_rows: list[dict[str, object]], feature_names: list[str]):
    pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    C=0.45,
                    class_weight="balanced",
                    max_iter=400,
                    random_state=42,
                ),
            ),
        ]
    )
    pipeline.fit(
        _rows_to_matrix(train_rows, feature_names),
        np.array([int(row["observed_class"]) for row in train_rows], dtype=int),
    )
    return pipeline


def _fit_lightgbm(train_rows: list[dict[str, object]], feature_names: list[str]):
    if LGBMClassifier is None:
        return None
    imputer = SimpleImputer(strategy="median")
    x_train = imputer.fit_transform(_rows_to_matrix(train_rows, feature_names))
    y_train = np.array([int(row["observed_class"]) for row in train_rows], dtype=int)
    model = LGBMClassifier(
        objective="multiclass",
        num_class=3,
        n_estimators=80,
        learning_rate=0.05,
        max_depth=3,
        num_leaves=15,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.7,
        reg_lambda=2.0,
        random_state=42,
        verbose=-1,
    )
    model.fit(x_train, y_train)
    return {"imputer": imputer, "model": model}


def _fit_xgboost(train_rows: list[dict[str, object]], feature_names: list[str]):
    if XGBClassifier is None:
        return None
    imputer = SimpleImputer(strategy="median")
    x_train = imputer.fit_transform(_rows_to_matrix(train_rows, feature_names))
    y_train = np.array([int(row["observed_class"]) for row in train_rows], dtype=int)
    model = XGBClassifier(
        objective="multi:softprob",
        num_class=3,
        n_estimators=50,
        learning_rate=0.05,
        max_depth=3,
        min_child_weight=4,
        subsample=0.8,
        colsample_bytree=0.7,
        reg_lambda=2.0,
        random_state=42,
        eval_metric="mlogloss",
        verbosity=0,
    )
    model.fit(x_train, y_train)
    return {"imputer": imputer, "model": model}


def _fit_catboost(train_rows: list[dict[str, object]], feature_names: list[str]):
    if CatBoostClassifier is None:
        return None
    imputer = SimpleImputer(strategy="median")
    x_train = imputer.fit_transform(_rows_to_matrix(train_rows, feature_names))
    y_train = np.array([int(row["observed_class"]) for row in train_rows], dtype=int)
    model = CatBoostClassifier(
        loss_function="MultiClass",
        iterations=60,
        learning_rate=0.05,
        depth=4,
        l2_leaf_reg=5.0,
        random_seed=42,
        verbose=False,
        allow_writing_files=False,
    )
    model.fit(x_train, y_train)
    return {"imputer": imputer, "model": model}


def _proba3(classes: np.ndarray, probabilities: np.ndarray) -> np.ndarray:
    full = np.full(3, 1e-9, dtype=float)
    for idx, label in enumerate(classes):
        full[int(label)] = float(probabilities[idx])
    return full / full.sum()


def _predict_pipeline_proba(model, row: dict[str, object], feature_names: list[str]) -> np.ndarray:
    probabilities = model.predict_proba(_rows_to_matrix([row], feature_names))[0]
    return _proba3(model.named_steps["clf"].classes_, probabilities)


def _predict_lightgbm_proba(bundle: dict[str, object], row: dict[str, object], feature_names: list[str]) -> np.ndarray:
    transformed = bundle["imputer"].transform(_rows_to_matrix([row], feature_names))
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="X does not have valid feature names")
        probabilities = bundle["model"].predict_proba(transformed)[0]
    return _proba3(bundle["model"].classes_, probabilities)


def _predict_boosted_proba(bundle: dict[str, object], row: dict[str, object], feature_names: list[str]) -> np.ndarray:
    transformed = bundle["imputer"].transform(_rows_to_matrix([row], feature_names))
    probabilities = bundle["model"].predict_proba(transformed)[0]
    return _proba3(bundle["model"].classes_, probabilities)


def _fit_candidate_models(train_rows: list[dict[str, object]], feature_names: list[str]) -> dict[str, object]:
    models: dict[str, object] = {"climatology": _fit_climatology(train_rows)}
    classes = {int(row["observed_class"]) for row in train_rows}
    if len(train_rows) < MIN_TRAIN_ROWS or len(classes) < 2 or not feature_names:
        return models
    try:
        models["analog_knn"] = _fit_knn(train_rows, feature_names)
    except ValueError:
        pass
    try:
        models["softmax"] = _fit_logistic(train_rows, feature_names)
    except ValueError:
        pass
    try:
        lightgbm_model = _fit_lightgbm(train_rows, feature_names)
        if lightgbm_model is not None:
            models["lightgbm"] = lightgbm_model
    except ValueError:
        pass
    try:
        xgboost_model = _fit_xgboost(train_rows, feature_names)
        if xgboost_model is not None:
            models["xgboost"] = xgboost_model
    except ValueError:
        pass
    try:
        catboost_model = _fit_catboost(train_rows, feature_names)
        if catboost_model is not None:
            models["catboost"] = catboost_model
    except ValueError:
        pass
    return models


def _predict_candidate_models(models: dict[str, object], row: dict[str, object], feature_names: list[str]) -> dict[str, ProbabilityTriple]:
    climo = _predict_climatology(models["climatology"], int(row["issue_month"]))
    predictions: dict[str, ProbabilityTriple] = {
        "climatology": _to_probability({"lower": climo[0], "normal": climo[1], "upper": climo[2]})
    }
    if "analog_knn" in models:
        proba = _predict_pipeline_proba(models["analog_knn"], row, feature_names)
        predictions["analog_knn"] = _to_probability({"lower": proba[0], "normal": proba[1], "upper": proba[2]})
    if "softmax" in models:
        proba = _predict_pipeline_proba(models["softmax"], row, feature_names)
        predictions["softmax"] = _to_probability({"lower": proba[0], "normal": proba[1], "upper": proba[2]})
    if "lightgbm" in models:
        proba = _predict_lightgbm_proba(models["lightgbm"], row, feature_names)
        predictions["lightgbm"] = _to_probability({"lower": proba[0], "normal": proba[1], "upper": proba[2]})
    if "xgboost" in models:
        proba = _predict_boosted_proba(models["xgboost"], row, feature_names)
        predictions["xgboost"] = _to_probability({"lower": proba[0], "normal": proba[1], "upper": proba[2]})
    if "catboost" in models:
        proba = _predict_boosted_proba(models["catboost"], row, feature_names)
        predictions["catboost"] = _to_probability({"lower": proba[0], "normal": proba[1], "upper": proba[2]})
    return predictions


def _rps(probabilities: ProbabilityTriple, observed_class: int) -> float:
    values = np.array([probabilities.lower, probabilities.normal, probabilities.upper], dtype=float)
    cumulative = np.cumsum(values)
    observed = np.zeros(3, dtype=float)
    observed[int(observed_class)] = 1.0
    return float(np.sum((cumulative[:2] - np.cumsum(observed)[:2]) ** 2) / 2.0)


def _brier(probabilities: ProbabilityTriple, observed_class: int) -> float:
    values = np.array([probabilities.lower, probabilities.normal, probabilities.upper], dtype=float)
    observed = np.zeros(3, dtype=float)
    observed[int(observed_class)] = 1.0
    return float(np.mean((values - observed) ** 2))


def _accuracy(probabilities: ProbabilityTriple, observed_class: int) -> float:
    predicted = int(np.argmax([probabilities.lower, probabilities.normal, probabilities.upper]))
    return 1.0 if predicted == int(observed_class) else 0.0


def _weights_from_skill(model_metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    candidates = {
        name: metrics["rpss"]
        for name, metrics in model_metrics.items()
        if name != "climatology" and metrics["available_rows"] > 0 and metrics["rpss"] > 0
    }
    if not candidates:
        return {"climatology": 1.0}
    raw = {name: math.exp(score / 0.02) for name, score in candidates.items()}
    total = sum(raw.values())
    return {name: value / total for name, value in raw.items()}


def _ensemble_probability(predictions: dict[str, ProbabilityTriple], weights: dict[str, float]) -> ProbabilityTriple:
    usable = {name: weight for name, weight in weights.items() if name in predictions}
    if not usable:
        return predictions["climatology"]
    total = sum(usable.values())
    lower = sum(predictions[name].lower * weight for name, weight in usable.items()) / total
    normal = sum(predictions[name].normal * weight for name, weight in usable.items()) / total
    upper = sum(predictions[name].upper * weight for name, weight in usable.items()) / total
    return ProbabilityTriple(lower=lower, normal=normal, upper=upper).normalized()


def _group_rows(feature_rows: list[dict[str, object]]) -> dict[tuple[str, int], list[dict[str, object]]]:
    grouped: dict[tuple[str, int], list[dict[str, object]]] = {}
    for row in feature_rows:
        key = (str(row["variable"]), int(row["lead"]))
        grouped.setdefault(key, []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda item: (int(item["issue_year"]), int(item["issue_month"])))
    return grouped


def _backtest_rows(rows: list[dict[str, object]], feature_names: list[str], max_origins: int | None = None) -> list[dict[str, object]]:
    predictions: list[dict[str, object]] = []
    origins = 0
    for index, row in enumerate(rows):
        if (int(row["issue_year"]), int(row["issue_month"])) < BACKTEST_START:
            continue
        train_rows = rows[:index]
        if len(train_rows) < MIN_TRAIN_ROWS:
            continue
        selected_features = _select_feature_columns(train_rows, feature_names)
        models = _fit_candidate_models(train_rows, selected_features)
        predicted = _predict_candidate_models(models, row, selected_features)
        predictions.append(
            {
                "issue_year": int(row["issue_year"]),
                "issue_month": int(row["issue_month"]),
                "lead": int(row["lead"]),
                "variable": str(row["variable"]),
                "target_year": int(row["target_year"]),
                "target_month": int(row["target_month"]),
                "observed_symbol": str(row["observed_symbol"]),
                "observed_class": int(row["observed_class"]),
                "feature_count": len(selected_features),
                "probabilities": {
                    name: _serialize_probability(probability)
                    for name, probability in predicted.items()
                },
            }
        )
        origins += 1
        if max_origins is not None and origins >= max_origins:
            break
    return predictions


def _summarize_backtest(backtest_rows: list[dict[str, object]], max_origins: int | None) -> dict[str, object]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in backtest_rows:
        key = f"{row['variable']}_lead{row['lead']}"
        grouped.setdefault(key, []).append(row)

    summary: dict[str, object] = {
        "metadata": {"max_origins_per_group": max_origins},
        "groups": {},
    }
    for key, rows in grouped.items():
        model_names = sorted({name for row in rows for name in row["probabilities"]})
        model_metrics: dict[str, dict[str, float]] = {}
        for name in model_names:
            relevant = [row for row in rows if name in row["probabilities"]]
            if not relevant:
                continue
            rps_values = [_rps(_to_probability(row["probabilities"][name]), int(row["observed_class"])) for row in relevant]
            climatology_values = [_rps(_to_probability(row["probabilities"]["climatology"]), int(row["observed_class"])) for row in relevant]
            climatology_mean = float(np.mean(climatology_values))
            mean_rps = float(np.mean(rps_values))
            model_metrics[name] = {
                "available_rows": float(len(relevant)),
                "mean_rps": mean_rps,
                "rpss": 0.0 if climatology_mean <= 0 else float(1.0 - mean_rps / climatology_mean),
                "mean_brier": float(np.mean([_brier(_to_probability(row["probabilities"][name]), int(row["observed_class"])) for row in relevant])),
                "accuracy": float(np.mean([_accuracy(_to_probability(row["probabilities"][name]), int(row["observed_class"])) for row in relevant])),
            }
        weights = _weights_from_skill(model_metrics)
        ensemble_probs = []
        for row in rows:
            predictions = {
                name: _to_probability(probabilities)
                for name, probabilities in row["probabilities"].items()
            }
            ensemble_probs.append(_ensemble_probability(predictions, weights))
        summary["groups"][key] = {
            "row_count": len(rows),
            "model_metrics": model_metrics,
            "ensemble_weights": weights,
            "ensemble_metrics": {
                "mean_rps": float(np.mean([_rps(probability, int(row["observed_class"])) for probability, row in zip(ensemble_probs, rows, strict=True)])),
                "mean_brier": float(np.mean([_brier(probability, int(row["observed_class"])) for probability, row in zip(ensemble_probs, rows, strict=True)])),
                "accuracy": float(np.mean([_accuracy(probability, int(row["observed_class"])) for probability, row in zip(ensemble_probs, rows, strict=True)])),
            },
        }
    return summary


def _top_softmax_features(model: dict[str, object], row: dict[str, object], feature_names: list[str]) -> list[tuple[str, float]]:
    if "softmax" not in model or not feature_names:
        return []
    pipeline = model["softmax"]
    transformed = pipeline.named_steps["scaler"].transform(
        pipeline.named_steps["imputer"].transform(_rows_to_matrix([row], feature_names))
    )[0]
    classifier = pipeline.named_steps["clf"]
    if CLASS_TO_INDEX["-"] not in classifier.classes_ or CLASS_TO_INDEX["+"] not in classifier.classes_:
        return []
    minus_idx = int(np.where(classifier.classes_ == CLASS_TO_INDEX["-"])[0][0])
    plus_idx = int(np.where(classifier.classes_ == CLASS_TO_INDEX["+"])[0][0])
    ranked = sorted(
        zip(feature_names, transformed * (classifier.coef_[plus_idx] - classifier.coef_[minus_idx])),
        key=lambda item: abs(float(item[1])),
        reverse=True,
    )
    return [(name, round(float(value), 4)) for name, value in ranked[:5]]


def _top_model_features(models: dict[str, object], feature_names: list[str]) -> list[tuple[str, float]]:
    if "softmax" in models and feature_names:
        pipeline = models["softmax"]
        classifier = pipeline.named_steps["clf"]
        if CLASS_TO_INDEX["-"] in classifier.classes_ and CLASS_TO_INDEX["+"] in classifier.classes_:
            minus_idx = int(np.where(classifier.classes_ == CLASS_TO_INDEX["-"])[0][0])
            plus_idx = int(np.where(classifier.classes_ == CLASS_TO_INDEX["+"])[0][0])
            ranked = sorted(
                zip(feature_names, np.abs(classifier.coef_[plus_idx] - classifier.coef_[minus_idx])),
                key=lambda item: float(item[1]),
                reverse=True,
            )
            return [(name, round(float(value), 4)) for name, value in ranked[:10]]
    if "lightgbm" in models and feature_names:
        model = models["lightgbm"]["model"]
        ranked = sorted(
            zip(feature_names, model.feature_importances_),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        return [(name, round(float(value), 4)) for name, value in ranked[:10] if float(value) > 0]
    if "xgboost" in models and feature_names:
        model = models["xgboost"]["model"]
        ranked = sorted(
            zip(feature_names, model.feature_importances_),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        return [(name, round(float(value), 4)) for name, value in ranked[:10] if float(value) > 0]
    if "catboost" in models and feature_names:
        model = models["catboost"]["model"]
        ranked = sorted(
            zip(feature_names, model.get_feature_importance()),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        return [(name, round(float(value), 4)) for name, value in ranked[:10] if float(value) > 0]
    return []


def _build_training_rows(
    historical_groups: dict[tuple[str, int], list[dict[str, object]]],
    skill_summary: dict[str, object],
    feature_names: list[str],
    issue_date: date,
    predictors: list[PredictorSpec],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for variable in ("temperature", "precipitation"):
        for lead in (1, 2, 3):
            historical_rows = [
                row
                for row in historical_groups.get((variable, lead), [])
                if _month_ordinal(int(row["issue_year"]), int(row["issue_month"])) < _month_ordinal(issue_date.year, issue_date.month)
            ]
            selected_features = _select_feature_columns(historical_rows, feature_names)
            models = _fit_candidate_models(historical_rows, selected_features)
            summary_key = f"{variable}_lead{lead}"
            weights = {
                str(name): float(value)
                for name, value in skill_summary.get("groups", {}).get(summary_key, {}).get("ensemble_weights", {"climatology": 1.0}).items()
            }
            top_features = [
                {
                    "feature": name,
                    "display_name": _feature_display_name(name, predictors),
                    "score": value,
                }
                for name, value in _top_model_features(models, selected_features)
            ]
            rows.append(
                {
                    "variable": variable,
                    "lead": lead,
                    "training_rows": len(historical_rows),
                    "train_start": None if not historical_rows else f"{historical_rows[0]['issue_year']}-{int(historical_rows[0]['issue_month']):02d}",
                    "train_end": None if not historical_rows else f"{historical_rows[-1]['issue_year']}-{int(historical_rows[-1]['issue_month']):02d}",
                    "selected_feature_count": len(selected_features),
                    "selected_features": selected_features,
                    "available_models": sorted(models.keys()),
                    "ensemble_weights": weights,
                    "top_model_features": top_features,
                    "lag_policy": {
                        "default_index_lag": "M-1",
                        "delayed_index_lag": "ONI/QBO는 M-2",
                        "derived_features": ["m0", "m1", "roll3", "delta1"],
                    },
                }
            )
    return rows


def _render_training_markdown(training_rows: list[dict[str, object]]) -> str:
    lines = [
        "# 핵심기후인자 학습 모델 요약",
        "",
        "- 학습 목표: 한반도 월평균기온과 강수량의 `-, 0, +` 3분위 기호",
        "- 입력 시차 규칙: 대부분의 지수는 `M-1`, 지연 갱신 지수(예: `ONI`, `QBO`)는 `M-2`까지만 사용",
        "- 파생 입력: 최신 가용값(`m0`), 1개월 전(`m1`), 3개월 평균(`roll3`), 1개월 변화(`delta1`)",
        "- 모델군: 기후평년, 유사사례 kNN, 소프트맥스 회귀, LightGBM",
        "",
    ]
    for row in training_rows:
        variable_label = VARIABLE_LABELS.get(str(row["variable"]), str(row["variable"]))
        lead = int(row["lead"])
        weights = _format_weights({name: float(value) for name, value in row["ensemble_weights"].items()})
        top_features = ", ".join(
            f"{item['display_name']}({float(item['score']):.3f})" for item in row["top_model_features"][:5]
        ) or "없음"
        lines.extend(
            [
                f"## {variable_label} M+{lead}",
                "",
                f"- 학습 기간: `{row['train_start']}` ~ `{row['train_end']}`",
                f"- 학습 행 수: `{row['training_rows']}`",
                f"- 선택 feature 수: `{row['selected_feature_count']}`",
                f"- 학습된 후보모형: {', '.join(_display_model_name(name) for name in row['available_models'])}",
                f"- 백테스트 기반 앙상블 가중치: {weights}",
                f"- 대표 학습 feature: {top_features}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_dataset_markdown(
    truth_rows: list[dict[str, object]],
    feature_rows: list[dict[str, object]],
    predictors: list[PredictorSpec],
    history_end: tuple[int, int] | None,
) -> str:
    history_predictors = [item for item in predictors if item.history_ready]
    snapshot_only = [item for item in predictors if not item.history_ready]
    lines = [
        "# 객관예보 데이터셋 요약",
        "",
        f"- 학습 truth 행 수: `{len(truth_rows)}`",
        f"- feature 행 수: `{len(feature_rows)}`",
        f"- 학습·검증 목표월 종료: `{history_end[0]}-{history_end[1]:02d}`" if history_end else "- 학습·검증 목표월 종료: `최신 가용월`",
        f"- 과거 시계열 예측인자 수: `{len(history_predictors)}`",
        f"- 스냅샷 전용 인자 수: `{len(snapshot_only)}`",
        "- 영속 산출물 정책: objective 코어는 `json`, `md`, `toml`만 사용",
        "",
        "## 과거 시계열 예측인자",
        "",
        "| ID | 출처 유형 | 최신성 | 운영 지연월 | 현재예보 사용 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for predictor in history_predictors:
        lines.append(
            f"| {predictor.predictor_id} | {SOURCE_TYPE_LABELS.get(predictor.source_type, predictor.source_type)} | {FRESHNESS_LABELS.get(predictor.freshness, predictor.freshness)} | {predictor.operational_lag} | {'예' if predictor.use_in_current else '아니오'} |"
        )
    if snapshot_only:
        lines.extend(["", "## 스냅샷 전용 인자", "", "| ID | 출처 유형 | 비고 |", "| --- | --- | --- |"])
        for predictor in snapshot_only:
            lines.append(f"| {predictor.predictor_id} | {SOURCE_TYPE_LABELS.get(predictor.source_type, predictor.source_type)} | {predictor.notes} |")
    return "\n".join(lines) + "\n"


def _render_backtest_markdown(summary: dict[str, object]) -> str:
    history_end = summary.get("metadata", {}).get("history_end")
    lines = [
        "# 객관예보 백테스트 요약",
        "",
        "- 평가지표: RPSS, 다중범주 평균 Brier 점수, 적중률",
        "- 앙상블 가중치는 `RPSS > 0` 모델만 softmax 방식으로 부여",
        f"- 학습·검증 목표월 종료: `{history_end}`" if history_end else "- 학습·검증 목표월 종료: `최신 가용월`",
        "",
    ]
    for group_key, payload in summary["groups"].items():
        variable, lead = group_key.split("_lead", 1)
        lines.extend(
            [
                f"## {VARIABLE_LABELS.get(variable, variable)} M+{lead}",
                "",
                "| 모델 | 검증 행수 | RPSS | Brier | 적중률 |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for model_name, metrics in payload["model_metrics"].items():
            lines.append(
                f"| {_display_model_name(model_name)} | {int(metrics['available_rows'])} | {metrics['rpss']:.3f} | {metrics['mean_brier']:.3f} | {metrics['accuracy']:.3f} |"
            )
        weights = _format_weights(payload["ensemble_weights"])
        lines.extend(
            [
                "",
                f"- 앙상블 가중치: {weights}",
                f"- 앙상블 평균 RPS: {payload['ensemble_metrics']['mean_rps']:.3f}",
                f"- 앙상블 평균 Brier: {payload['ensemble_metrics']['mean_brier']:.3f}",
                f"- 앙상블 적중률: {payload['ensemble_metrics']['accuracy']:.3f}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _manual_snapshot_payload(config: SystemConfig, issue_date: date) -> list[dict[str, object]]:
    path = _climate_factor_snapshot_path(config, issue_date)
    if path is None:
        return []
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return [
        {
            "id": factor["id"],
            "name": factor["name"],
            "signal": factor["signal"],
            "confidence": factor["confidence"],
            "source_name": factor["source_name"],
            "summary": factor["summary"],
        }
        for factor in raw.get("factors", [])
    ]


def _render_current_markdown(
    run: ObjectiveForecastRun,
    manual_snapshot: list[dict[str, object]],
    predictors: list[PredictorSpec],
) -> str:
    lines = [
        "# 한반도 객관지수예보",
        "",
        f"- 발행일: `{run.issue_date.isoformat()}`",
        "- 영속 산출물 정책: `json`과 `md`만 사용",
        "- 독립성 원칙: 이 보고서는 핵심기후인자와 관측 기반 객관예측만 사용하며, 동적모델 prior는 사용하지 않음",
        "- 학습 모델 요약은 같은 날짜의 `objective_model_training_ko.md`에 별도 저장",
        "",
        "## 확률표",
        "",
        "| 변수 | 리드 | 목표월 | 낮음 | 비슷 | 높음 | 대표기호 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cell in run.cells:
        probabilities = cell.probabilities.as_dict()
        lines.append(
            f"| {VARIABLE_LABELS.get(cell.variable, cell.variable)} | M+{cell.lead} | {cell.target_month.year}-{cell.target_month.month:02d} | "
            f"{probabilities['lower']:.3f} | {probabilities['normal']:.3f} | {probabilities['upper']:.3f} | {cell.symbol} |"
        )
    lines.extend(["", "## 상위 설명 변수", ""])
    for cell in run.cells:
        weights = _format_weights(cell.model_weights) or "기후평년=1.00"
        features = ", ".join(
            f"{_feature_display_name(name, predictors)}({value:+.3f})"
            for name, value in cell.top_features
        ) or "없음"
        lines.extend(
            [
                f"### {VARIABLE_LABELS.get(cell.variable, cell.variable)} M+{cell.lead}",
                "",
                f"- 앙상블 가중치: {weights}",
                f"- 상위 설명 변수: {features}",
                "",
            ]
        )
    lines.extend(
        [
            "## 적용 방법",
            "",
            "- 목표변수: 한반도 월평균기온과 강수량을 `-, 0, +` 3분위 기호로 예측합니다.",
            "- 예측 단위: 기준월 `M`에서 `M+1`, `M+2`, `M+3`을 각각 별도 목표월로 둡니다.",
            "- 참값: `inputs/observed_symbols/남한_월별_실황_기호화.md`의 관측 실황을 읽어 학습용 정답으로 사용합니다.",
            "- 기후인자 입력: PSL 대표 시계열, `tele_index.nh` 보완 지수, 그리고 최근 한반도 관측 지속성 항을 사용합니다.",
            "- 입력 시차 규칙: 대부분의 지수는 `M-1`, 지연 갱신 지수(예: `ONI`, `QBO`)는 `M-2`까지만 사용합니다.",
            "- 특징량: 각 지수의 최신 가용값(`m0`), 1개월 전(`m1`), 3개월 평균(`roll3`), 1개월 변화량(`delta1`), 발행월/목표월 계절성(sin, cos)을 함께 만듭니다.",
            "- 후보모형: 기후평년, 유사사례 kNN, 다항 로지스틱 회귀, LightGBM을 병렬로 학습합니다.",
            "- 검증과 앙상블: 변수×리드별 expanding-window 백테스트에서 `RPSS > 0`인 모형만 남기고 softmax 가중으로 앙상블합니다.",
            "- 대표기호 결정: 최종 확률에서 `P(+) - P(-)`가 `+0.08` 이상이면 `+`, `-0.08` 이하이면 `-`, 그 사이는 `0`으로 둡니다.",
            "- 상위 설명 변수: 현재 사례에서 로지스틱 회귀 계열의 `+` 대 `-` 기여 차이를 기준으로 설명용 상위 항목을 제시합니다.",
            "- 해석용 스냅샷 인자: 아래 스냅샷 인자는 현재 버전에서 확률 학습 입력이 아니라, 예보 해석을 돕는 별도 참고 정보입니다.",
            "",
        ]
    )
    if manual_snapshot:
        lines.extend(["## 해석용 스냅샷 인자", ""])
        for factor in manual_snapshot:
            lines.append(
                f"- `{factor['id']}` 신호={factor['signal']} 신뢰도={factor['confidence']:.2f} "
                f"출처={factor['source_name']} ({factor['summary']})"
            )
        lines.append("")
    if run.warnings:
        lines.extend(["## 참고", ""])
        for warning in run.warnings:
            lines.append(f"- {warning}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_objective_dataset(
    config: SystemConfig,
    history_end: tuple[int, int] | None = None,
) -> dict[str, Path]:
    objective_dir = _objective_dir(config)
    observed = _load_observed_monthly(config)
    history_end = _normalize_history_end(history_end)
    truth_rows = _build_truth_rows(observed, history_end=history_end)
    predictors, series_by_predictor = _load_psl_predictors(config)
    predictors.extend(_load_manual_snapshot_specs(config, date.today()))
    feature_rows = _build_feature_rows(observed, truth_rows, predictors, series_by_predictor)

    truth_path = objective_dir / "truth_rows.json"
    features_path = objective_dir / "feature_rows.json"
    registry_path = objective_dir / "predictor_registry.json"
    summary_path = objective_dir / "dataset_summary.md"

    _write_text_atomic(truth_path, json.dumps(truth_rows, ensure_ascii=False, indent=2))
    _write_text_atomic(features_path, json.dumps(feature_rows, ensure_ascii=False, indent=2))
    _write_text_atomic(
        registry_path,
        json.dumps(
            [asdict(predictor) | {"raw_path": str(predictor.raw_path) if predictor.raw_path else None} for predictor in predictors],
            ensure_ascii=False,
            indent=2,
        ),
    )
    _write_text_atomic(summary_path, _render_dataset_markdown(truth_rows, feature_rows, predictors, history_end))
    return {
        "truth_rows": truth_path,
        "feature_rows": features_path,
        "predictor_registry": registry_path,
        "dataset_summary": summary_path,
    }


def backtest_objective_forecast(
    config: SystemConfig,
    max_origins: int | None = None,
    history_end: tuple[int, int] | None = None,
) -> dict[str, Path]:
    history_end = _normalize_history_end(history_end)
    dataset_outputs = build_objective_dataset(config, history_end=history_end)
    feature_rows = json.loads(dataset_outputs["feature_rows"].read_text(encoding="utf-8"))
    feature_names = _feature_columns(feature_rows)
    grouped = _group_rows(feature_rows)

    backtest_rows: list[dict[str, object]] = []
    for rows in grouped.values():
        backtest_rows.extend(_backtest_rows(rows, feature_names, max_origins=max_origins))
    backtest_rows.sort(key=lambda row: (row["variable"], row["lead"], row["issue_year"], row["issue_month"]))

    summary = _summarize_backtest(backtest_rows, max_origins)
    summary["metadata"]["history_end"] = (
        f"{history_end[0]}-{history_end[1]:02d}" if history_end else None
    )
    objective_dir = _objective_dir(config)
    predictions_path = objective_dir / "backtest_predictions.json"
    summary_path = objective_dir / "skill_summary.json"
    markdown_path = objective_dir / "backtest_summary.md"

    _write_text_atomic(predictions_path, json.dumps(backtest_rows, ensure_ascii=False, indent=2))
    _write_text_atomic(summary_path, json.dumps(summary, ensure_ascii=False, indent=2))
    _write_text_atomic(markdown_path, _render_backtest_markdown(summary))
    return {
        "backtest_predictions": predictions_path,
        "skill_summary": summary_path,
        "backtest_summary": markdown_path,
    }


def run_objective_forecast(
    config: SystemConfig,
    issue_date: date,
    history_end: tuple[int, int] | None = None,
) -> dict[str, Path]:
    history_end = _normalize_history_end(history_end)
    dataset_outputs = build_objective_dataset(config, history_end=history_end)
    objective_dir = _objective_dir(config)
    skill_summary_path = objective_dir / "skill_summary.json"
    expected_history_end = f"{history_end[0]}-{history_end[1]:02d}" if history_end else None
    if skill_summary_path.exists():
        skill_summary = json.loads(skill_summary_path.read_text(encoding="utf-8"))
        existing_history_end = skill_summary.get("metadata", {}).get("history_end")
        if existing_history_end != expected_history_end:
            backtest_objective_forecast(config, history_end=history_end)
    else:
        backtest_objective_forecast(config, history_end=history_end)

    feature_rows = json.loads(dataset_outputs["feature_rows"].read_text(encoding="utf-8"))
    skill_summary = json.loads(skill_summary_path.read_text(encoding="utf-8"))
    observed = _load_observed_monthly(config)
    predictors, series_by_predictor = _load_psl_predictors(config)
    predictors.extend(_load_manual_snapshot_specs(config, issue_date))
    current_truth_rows = []
    for lead in (1, 2, 3):
        target_year, target_month = _add_months(issue_date.year, issue_date.month, lead)
        for variable in ("temperature", "precipitation"):
            current_truth_rows.append(
                {
                    "issue_year": issue_date.year,
                    "issue_month": issue_date.month,
                    "lead": lead,
                    "variable": variable,
                    "target_year": target_year,
                    "target_month": target_month,
                    "observed_value": math.nan,
                    "observed_symbol": "",
                    "observed_class": -1,
                }
            )
    current_rows = _build_feature_rows(observed, current_truth_rows, predictors, series_by_predictor, current_issue_date=issue_date)
    feature_names = _feature_columns(feature_rows)
    historical_groups = _group_rows(feature_rows)
    current_groups = _group_rows(current_rows)
    training_rows = _build_training_rows(historical_groups, skill_summary, feature_names, issue_date, predictors)
    warnings = []
    cells: list[ObjectiveForecastCell] = []

    max_origins = skill_summary.get("metadata", {}).get("max_origins_per_group")
    history_end_label = skill_summary.get("metadata", {}).get("history_end")
    if max_origins is not None:
        warnings.append(f"현재 skill summary는 제한 백테스트(max_origins_per_group={max_origins}) 기준입니다")
    if history_end_label is not None:
        warnings.append(f"학습·검증은 목표월 기준 `{history_end_label}`까지의 자료만 사용했습니다")

    for (variable, lead), group_rows in current_groups.items():
        historical_rows = [
            row
            for row in historical_groups.get((variable, lead), [])
            if _month_ordinal(int(row["issue_year"]), int(row["issue_month"])) < _month_ordinal(issue_date.year, issue_date.month)
        ]
        if len(historical_rows) < MIN_TRAIN_ROWS:
            warnings.append(f"{VARIABLE_LABELS.get(variable, variable)} M+{lead}: 학습 표본이 부족해 기후평년 위주로 해석해야 합니다")
        selected_features = _select_feature_columns(historical_rows, feature_names)
        models = _fit_candidate_models(historical_rows, selected_features)
        current_row = group_rows[0]
        predictions = _predict_candidate_models(models, current_row, selected_features)
        summary_key = f"{variable}_lead{lead}"
        weights = {
            str(name): float(value)
            for name, value in skill_summary.get("groups", {}).get(summary_key, {}).get("ensemble_weights", {"climatology": 1.0}).items()
        }
        ensemble = _ensemble_probability(predictions, weights)
        cells.append(
            ObjectiveForecastCell(
                variable=variable,
                lead=lead,
                target_month=TargetMonth(lead=lead, year=int(current_row["target_year"]), month=int(current_row["target_month"])),
                probabilities=ensemble,
                symbol=_forecast_symbol(ensemble),
                model_weights=tuple((name, round(weight, 4)) for name, weight in weights.items()),
                top_features=tuple(_top_softmax_features(models, current_row, selected_features)),
            )
        )

    run = ObjectiveForecastRun(
        issue_date=issue_date,
        output_dir=_reports_dir_for_issue(config, issue_date),
        cells=tuple(sorted(cells, key=lambda cell: (cell.variable, cell.lead))),
        warnings=tuple(warnings),
    )
    manual_snapshot = _manual_snapshot_payload(config, issue_date)
    forecast_json = objective_dir / f"objective_forecast_{issue_date.isoformat()}.json"
    forecast_md = _reports_dir_for_issue(config, issue_date) / "objective_forecast_ko.md"
    training_json = objective_dir / f"trained_models_{issue_date.isoformat()}.json"
    training_md = _reports_dir_for_issue(config, issue_date) / "objective_model_training_ko.md"

    _write_text_atomic(
        forecast_json,
        json.dumps(
            {
                "issue_date": issue_date.isoformat(),
                "cells": [
                    {
                        "variable": cell.variable,
                        "lead": cell.lead,
                        "target_month": {"year": cell.target_month.year, "month": cell.target_month.month},
                        "probabilities": _serialize_probability(cell.probabilities),
                        "symbol": cell.symbol,
                        "model_weights": list(cell.model_weights),
                        "top_features": list(cell.top_features),
                    }
                    for cell in run.cells
                ],
                "warnings": list(run.warnings),
                "manual_snapshot_factors": manual_snapshot,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    _write_text_atomic(forecast_md, _render_current_markdown(run, manual_snapshot, predictors))
    _write_text_atomic(training_json, json.dumps(training_rows, ensure_ascii=False, indent=2))
    _write_text_atomic(training_md, _render_training_markdown(training_rows))
    return {
        "current_forecast_json": forecast_json,
        "current_forecast_md": forecast_md,
        "trained_models_json": training_json,
        "trained_models_md": training_md,
    }
