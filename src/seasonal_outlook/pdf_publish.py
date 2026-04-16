from __future__ import annotations

from datetime import date
from pathlib import Path
from shutil import copy2


def publish_pdf_copy(source_path: Path, issue_date: date, root_dir: Path, basename: str | None = None) -> Path:
    pdf_dir = root_dir / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    output_name = f"{basename or source_path.stem}_{issue_date.isoformat()}{source_path.suffix.lower()}"
    target_path = pdf_dir / output_name
    copy2(source_path, target_path)
    return target_path
