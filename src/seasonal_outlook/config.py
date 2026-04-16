from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class SystemConfig:
    root: Path
    raw: dict

    @property
    def system(self) -> dict:
        return self.raw["system"]

    @property
    def models(self) -> list[dict]:
        return list(self.raw["models"])

    @property
    def regions(self) -> dict:
        return dict(self.raw["regions"])

    @property
    def variables(self) -> dict:
        return dict(self.raw["variables"])

    @property
    def lead_multipliers(self) -> dict:
        return dict(self.raw["lead_multipliers"])

    def reports_dir(self) -> Path:
        return self.root / self.system["reports_dir"]

    def priors_dir(self) -> Path:
        return self.root / self.system["priors_dir"]

    def factors_dir(self) -> Path:
        return self.root / self.system["factors_dir"]

    def factor_reports_dir(self) -> Path:
        return self.root / self.system["factor_reports_dir"]

    def state_dir(self) -> Path:
        return self.root / self.system["state_dir"]

    def psl_indices_dir(self) -> Path:
        return self.root / self.system["psl_indices_dir"]

    def objective_dir(self) -> Path:
        return self.root / self.system.get("objective_dir", "state/objective_forecast")


def load_config(root: Path | None = None) -> SystemConfig:
    resolved_root = root or Path.cwd()
    config_path = resolved_root / "config" / "system.toml"
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)
    return SystemConfig(root=resolved_root, raw=raw)
