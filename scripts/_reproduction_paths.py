from __future__ import annotations

import os
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ATTACHMENT_ROOT = SCRIPT_DIR.parent


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    if raw:
        return Path(raw).expanduser().resolve()
    return default.resolve()


AP_ROOT = _env_path("AP_ROOT", ATTACHMENT_ROOT.parent / "Artificial-PsyArch")
ARTIFACT_ROOT = _env_path("AP_PAPER_ARTIFACT_ROOT", ATTACHMENT_ROOT / "reproduction_outputs")
PUBLISHED_EXPERIMENT_ROOT = _env_path("AP_PUBLISHED_EXPERIMENT_ROOT", ATTACHMENT_ROOT / "experiments")
PAPER_QUALITY_OUTPUT_ROOT = _env_path(
    "AP_PAPER_QUALITY_OUTPUT_ROOT",
    ATTACHMENT_ROOT / "reproduction_outputs" / "paper_quality_charts_v02",
)
