from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
import csv
import json
import tomllib

from .config import SystemConfig
from .models import (
    CandidateScorecard,
    ClimateFactor,
    ClimateFactorEffect,
    DynamicPrior,
    ForecastCell,
    ForecastRun,
    ProbabilityTriple,
    REGION_ORDER,
    TargetMonth,
    VARIABLE_ORDER,
)


def add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    absolute = year * 12 + (month - 1) + delta
    return absolute // 12, absolute % 12 + 1


def target_months(issue_date: date) -> tuple[TargetMonth, ...]:
    items = []
    for lead in (1, 2, 3):
        year, month = add_months(issue_date.year, issue_date.month, lead)
        items.append(TargetMonth(lead=lead, year=year, month=month))
    return tuple(items)


def _load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _dated_input_path(directory: Path, issue_date: date) -> Path:
    return directory / f"{issue_date.isoformat()}.toml"


def _resolve_input_path(directory: Path, issue_date: date) -> tuple[Path, bool]:
    exact = _dated_input_path(directory, issue_date)
    if exact.exists():
        return exact, False

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
    return candidates[0][1], True


def load_dynamic_priors(config: SystemConfig, issue_date: date) -> tuple[bool, list[DynamicPrior]]:
    path, delayed = _resolve_input_path(config.priors_dir(), issue_date)
    payload = _load_toml(path)
    priors = []
    for entry in payload["priors"]:
        priors.append(
            DynamicPrior(
                model_id=entry["model_id"],
                region=entry["region"],
                variable=entry["variable"],
                lead=int(entry["lead"]),
                probabilities=ProbabilityTriple(
                    lower=float(entry["lower"]),
                    normal=float(entry["normal"]),
                    upper=float(entry["upper"]),
                ).normalized(),
                rpss_recent=float(entry["rpss_recent"]),
                rpss_all=float(entry["rpss_all"]),
                bss_recent=float(entry["bss_recent"]),
                bss_all=float(entry["bss_all"]),
                acc_recent=float(entry["acc_recent"]),
                acc_all=float(entry["acc_all"]),
            )
        )
    return delayed, priors


def load_climate_factors(config: SystemConfig, issue_date: date) -> tuple[str, list[ClimateFactor]]:
    path, delayed = _resolve_input_path(config.factors_dir(), issue_date)
    payload = _load_toml(path)
    factors = []
    for entry in payload["factors"]:
        effects = tuple(
            ClimateFactorEffect(
                region=item["region"],
                variable=item["variable"],
                lead=int(item["lead"]),
                magnitude=float(item["magnitude"]),
            )
            for item in entry.get("effects", [])
        )
        factors.append(
            ClimateFactor(
                factor_id=entry["id"],
                name=entry["name"],
                family=entry["family"],
                state=entry["state"],
                signal=int(entry["signal"]),
                confidence=float(entry["confidence"]),
                source_name=entry["source_name"],
                source_url=entry["source_url"],
                summary=entry["summary"],
                effects=effects,
            )
        )
    status = payload.get("data_status", "current")
    return ("delayed" if delayed else status), factors


def _normalized_skill_weights(priors: list[DynamicPrior], model_defaults: dict[str, float]) -> dict[str, float]:
    scores = {}
    for prior in priors:
        recent = (prior.rpss_recent + prior.bss_recent + prior.acc_recent) / 3.0
        full = (prior.rpss_all + prior.bss_all + prior.acc_all) / 3.0
        scores[prior.model_id] = 0.6 * recent + 0.4 * full

    if not scores:
        return {}

    minimum = min(scores.values())
    maximum = max(scores.values())
    weights = {}
    for model_id, score in scores.items():
        scaled = 1.0 if maximum == minimum else 0.5 + (score - minimum) / (maximum - minimum)
        weights[model_id] = scaled * model_defaults.get(model_id, 1.0)

    total = sum(weights.values())
    return {model_id: value / total for model_id, value in weights.items()}


def fuse_dynamic_priors(config: SystemConfig, priors: list[DynamicPrior]) -> dict[tuple[str, str, int], tuple[ProbabilityTriple, float, tuple[str, ...]]]:
    model_defaults = {entry["id"]: float(entry["default_weight"]) for entry in config.models}
    grouped: dict[tuple[str, str, int], list[DynamicPrior]] = defaultdict(list)
    for prior in priors:
        grouped[(prior.region, prior.variable, prior.lead)].append(prior)

    fused = {}
    for key, members in grouped.items():
        weights = _normalized_skill_weights(members, model_defaults)
        lower = 0.0
        normal = 0.0
        upper = 0.0
        dominant_votes = defaultdict(int)
        for prior in members:
            weight = weights[prior.model_id]
            lower += prior.probabilities.lower * weight
            normal += prior.probabilities.normal * weight
            upper += prior.probabilities.upper * weight
            dominant_votes[prior.probabilities.dominant_category()] += 1

        combined = ProbabilityTriple(lower=lower, normal=normal, upper=upper).normalized()
        agreement = max(dominant_votes.values()) / len(members)
        fused[key] = (combined, agreement, tuple(sorted(weights.keys())))
    return fused


def _apply_signed_shift(probabilities: ProbabilityTriple, adjustment: float) -> ProbabilityTriple:
    lower = probabilities.lower
    normal = probabilities.normal
    upper = probabilities.upper

    if adjustment > 0:
        move = min(adjustment, lower + normal)
        take_from_lower = min(lower, move * 0.7)
        take_from_normal = min(normal, move - take_from_lower)
        lower -= take_from_lower
        normal -= take_from_normal
        upper += take_from_lower + take_from_normal
    elif adjustment < 0:
        move = min(abs(adjustment), upper + normal)
        take_from_upper = min(upper, move * 0.7)
        take_from_normal = min(normal, move - take_from_upper)
        upper -= take_from_upper
        normal -= take_from_normal
        lower += take_from_upper + take_from_normal

    return ProbabilityTriple(lower=lower, normal=normal, upper=upper).normalized()


def apply_factor_adjustments(
    config: SystemConfig,
    baseline: dict[tuple[str, str, int], tuple[ProbabilityTriple, float, tuple[str, ...]]],
    factors: list[ClimateFactor],
    targets: tuple[TargetMonth, ...],
) -> tuple[list[ForecastCell], list[str]]:
    warnings = []
    cap = float(config.system["default_adjustment_cap"])
    lead_multipliers = config.lead_multipliers
    cells: list[ForecastCell] = []

    for region in REGION_ORDER:
        for variable in VARIABLE_ORDER:
            for target in targets:
                key = (region, variable, target.lead)
                if key not in baseline:
                    continue

                prior, agreement, models = baseline[key]
                contributions = []
                total_adjustment = 0.0
                for factor in factors:
                    family_multiplier = float(lead_multipliers[factor.family][str(target.lead)])
                    for effect in factor.effects:
                        if effect.region != region or effect.variable != variable or effect.lead != target.lead:
                            continue
                        signed_adjustment = effect.magnitude * factor.signal * factor.confidence * family_multiplier
                        contributions.append((factor.name, round(signed_adjustment, 4)))
                        total_adjustment += signed_adjustment

                clipped_adjustment = max(-cap, min(cap, total_adjustment))
                if clipped_adjustment != total_adjustment:
                    warnings.append(
                        f"{region}/{variable}/M+{target.lead} adjustment capped from {total_adjustment:.3f} to {clipped_adjustment:.3f}"
                    )

                posterior = _apply_signed_shift(prior, clipped_adjustment)
                cells.append(
                    ForecastCell(
                        region=region,
                        variable=variable,
                        lead=target.lead,
                        target_month=target,
                        prior=prior,
                        posterior=posterior,
                        total_adjustment=round(clipped_adjustment, 4),
                        dominant_category=posterior.dominant_category(),
                        model_agreement=round(agreement, 4),
                        supporting_models=models,
                        factor_contributions=tuple(contributions),
                    )
                )
    return cells, warnings


def generate_forecast(config: SystemConfig, issue_date: date) -> ForecastRun:
    targets = target_months(issue_date)
    priors_delayed, priors = load_dynamic_priors(config, issue_date)
    baseline = fuse_dynamic_priors(config, priors)
    factors: list[ClimateFactor] = []
    cells, warnings = apply_factor_adjustments(config, baseline, factors, targets)
    output_dir = config.reports_dir() / issue_date.isoformat()
    return ForecastRun(
        issue_date=issue_date,
        output_dir=output_dir,
        targets=targets,
        cells=tuple(cells),
        factors=tuple(factors),
        warnings=tuple(warnings),
        source_status=("delayed" if priors_delayed else "current"),
    )


def write_probability_exports(run: ForecastRun) -> None:
    run.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = run.output_dir / "tercile_probabilities.json"
    csv_path = run.output_dir / "tercile_probabilities.csv"

    payload = []
    for cell in run.cells:
        payload.append(
            {
                "issue_date": run.issue_date.isoformat(),
                "region": cell.region,
                "variable": cell.variable,
                "lead": cell.lead,
                "target_year": cell.target_month.year,
                "target_month": cell.target_month.month,
                "prior": cell.prior.as_dict(),
                "posterior": cell.posterior.as_dict(),
                "dominant_category": cell.dominant_category,
                "total_adjustment": cell.total_adjustment,
                "model_agreement": cell.model_agreement,
            }
        )
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "issue_date",
                "region",
                "variable",
                "lead",
                "target_year",
                "target_month",
                "lower",
                "normal",
                "upper",
                "dominant_category",
                "total_adjustment",
                "model_agreement",
            ]
        )
        for cell in run.cells:
            writer.writerow(
                [
                    run.issue_date.isoformat(),
                    cell.region,
                    cell.variable,
                    cell.lead,
                    cell.target_month.year,
                    cell.target_month.month,
                    f"{cell.posterior.lower:.4f}",
                    f"{cell.posterior.normal:.4f}",
                    f"{cell.posterior.upper:.4f}",
                    cell.dominant_category,
                    f"{cell.total_adjustment:.4f}",
                    f"{cell.model_agreement:.4f}",
                ]
            )


def append_results_ledger(config: SystemConfig, payload: dict[str, object]) -> Path:
    ledger_path = config.root / config.system["history_file"]
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    return ledger_path


def load_scorecard(path: Path) -> CandidateScorecard:
    payload = _load_toml(path)
    return CandidateScorecard(
        composite_score=float(payload["composite_score"]),
        korea_temp_bss=float(payload["korea_temp_bss"]),
        korea_precip_bss=float(payload["korea_precip_bss"]),
        reliability=float(payload["reliability"]),
        note=payload.get("note", ""),
    )


def evaluate_candidate(current: CandidateScorecard, candidate: CandidateScorecard) -> dict[str, object]:
    composite_gain = candidate.composite_score - current.composite_score
    relative_gain = composite_gain / current.composite_score if current.composite_score else 0.0
    temp_delta = candidate.korea_temp_bss - current.korea_temp_bss
    precip_delta = candidate.korea_precip_bss - current.korea_precip_bss
    accepted = relative_gain >= 0.02 and temp_delta > -0.05 and precip_delta > -0.05
    return {
        "accepted": accepted,
        "relative_gain": round(relative_gain, 4),
        "temp_bss_delta": round(temp_delta, 4),
        "precip_bss_delta": round(precip_delta, 4),
        "candidate_note": candidate.note,
    }
