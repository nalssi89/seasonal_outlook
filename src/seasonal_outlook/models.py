from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


VARIABLE_ORDER = ("temperature", "precipitation")
REGION_ORDER = ("korea", "east_asia")


@dataclass(frozen=True)
class TargetMonth:
    lead: int
    year: int
    month: int

    @property
    def label(self) -> str:
        return f"M+{self.lead} ({self.year}-{self.month:02d})"


@dataclass(frozen=True)
class ProbabilityTriple:
    lower: float
    normal: float
    upper: float

    def normalized(self) -> "ProbabilityTriple":
        total = self.lower + self.normal + self.upper
        if total <= 0:
            return ProbabilityTriple(1 / 3, 1 / 3, 1 / 3)
        return ProbabilityTriple(
            lower=self.lower / total,
            normal=self.normal / total,
            upper=self.upper / total,
        )

    def dominant_category(self) -> str:
        values = {"lower": self.lower, "normal": self.normal, "upper": self.upper}
        return max(values, key=values.get)

    def as_dict(self) -> dict[str, float]:
        return {
            "lower": round(self.lower, 4),
            "normal": round(self.normal, 4),
            "upper": round(self.upper, 4),
        }


@dataclass(frozen=True)
class DynamicPrior:
    model_id: str
    region: str
    variable: str
    lead: int
    probabilities: ProbabilityTriple
    rpss_recent: float
    rpss_all: float
    bss_recent: float
    bss_all: float
    acc_recent: float
    acc_all: float


@dataclass(frozen=True)
class ClimateFactorEffect:
    region: str
    variable: str
    lead: int
    magnitude: float


@dataclass(frozen=True)
class ClimateFactor:
    factor_id: str
    name: str
    family: str
    state: str
    signal: int
    confidence: float
    source_name: str
    source_url: str
    summary: str
    effects: tuple[ClimateFactorEffect, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ForecastCell:
    region: str
    variable: str
    lead: int
    target_month: TargetMonth
    prior: ProbabilityTriple
    posterior: ProbabilityTriple
    total_adjustment: float
    dominant_category: str
    model_agreement: float
    supporting_models: tuple[str, ...]
    factor_contributions: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class ForecastRun:
    issue_date: date
    output_dir: Path
    targets: tuple[TargetMonth, ...]
    cells: tuple[ForecastCell, ...]
    factors: tuple[ClimateFactor, ...]
    warnings: tuple[str, ...]
    source_status: str


@dataclass(frozen=True)
class CandidateScorecard:
    composite_score: float
    korea_temp_bss: float
    korea_precip_bss: float
    reliability: float
    note: str = ""


@dataclass(frozen=True)
class ObjectiveForecastCell:
    variable: str
    lead: int
    target_month: TargetMonth
    probabilities: ProbabilityTriple
    symbol: str
    model_weights: tuple[tuple[str, float], ...]
    top_features: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class ObjectiveForecastRun:
    issue_date: date
    output_dir: Path
    cells: tuple[ObjectiveForecastCell, ...]
    warnings: tuple[str, ...]
