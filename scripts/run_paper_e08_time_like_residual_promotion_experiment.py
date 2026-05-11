# -*- coding: utf-8 -*-
"""Run paper E08 time-like residual-promotion experiment.

Paper-facing E08 claim
----------------------
This experiment intentionally narrows E08 to a claim that the current AP
prototype can already support with strong, auditable evidence:

    在 runtime_em_only 主链中，已有 seed 记忆与延迟线索共同存在时，
    时间样属性可以进入当前内源刺激，并使残差记忆影子候选在刺激级匹配中
    获得受控晋升，最终重新进入主链竞争。

The experiment does NOT try to prove:
- broad episodic recall;
- lexical cue identity selectivity;
- generic “the correct cue beats the wrong cue”.

It only proves the narrower white-box chain that is already visible in the
implementation:

    seed memory exists
    + delayed cue exists
    + time-like wildcard is active
    -> shadow raw residual candidate becomes eligible
    -> candidate is promoted
    -> promoted shadow residual re-enters main competition
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
AP_ROOT = ROOT / "Artificial-PsyArch"
if str(AP_ROOT) not in sys.path:
    sys.path.insert(0, str(AP_ROOT))

import run_paper_e01_experiment as e01
from observatory._app import ObservatoryApp
from observatory.experiment.io import sha256_file
from observatory.experiment.runner import RunOptions, apply_experiment_default_app_overrides, run_dataset
from observatory.experiment.storage import DatasetFileRef, imported_datasets_dir, resolve_run_dir


ARTIFACT_ROOT = ROOT / "docs" / "paper_artifacts_2026-05-11"
E08_ROOT = ARTIFACT_ROOT / "E08_time_like_residual_promotion"
DATASET_DIR = E08_ROOT / "datasets"
RUN_DIR = E08_ROOT / "runs"
TABLE_DIR = E08_ROOT / "tables"
CHART_DIR = E08_ROOT / "charts"
REPORT_DIR = E08_ROOT / "reports"
MANIFEST_DIR = E08_ROOT / "manifests"

STAMP_DEFAULT = "e08_final_v1"


@dataclass(frozen=True)
class FamilySpec:
    family: str
    seed_text: str
    cue_text: str


FAMILY_SPECS: list[FamilySpec] = [
    FamilySpec("F01", "ABX", "A"),
    FamilySpec("F02", "CDQ", "C"),
    FamilySpec("F03", "KLM", "K"),
    FamilySpec("F04", "PQT", "P"),
    FamilySpec("F05", "RSU", "R"),
    FamilySpec("F06", "VWX", "V"),
    FamilySpec("F07", "YZA", "Y"),
    FamilySpec("F08", "MNO", "M"),
    FamilySpec("F09", "TUV", "T"),
    FamilySpec("F10", "EFG", "E"),
    FamilySpec("F11", "HIJ", "H"),
    FamilySpec("F12", "BCD", "B"),
]

BRANCHES = ("on_matched", "off_matched", "on_no_seed", "on_no_cue")
BASELINE_KEYS = (
    "input_chunking_enabled",
    "enable_goal_b_char_sa_string_mode",
    "induction_projection_mode",
    "enable_cognitive_stitching",
    "cognitive_stitching_stage",
)


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dirs() -> None:
    for path in (DATASET_DIR, RUN_DIR, TABLE_DIR, CHART_DIR, REPORT_DIR, MANIFEST_DIR, imported_datasets_dir()):
        path.mkdir(parents=True, exist_ok=True)


def safe_ratio(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else 0.0


def sign_test_p_value(wins: int, losses: int) -> float:
    n = int(wins) + int(losses)
    if n <= 0:
        return 1.0
    k = min(int(wins), int(losses))
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return round(min(1.0, 2.0 * tail), 8)


def mean_or_zero(values: list[float]) -> float:
    clean = [float(x) for x in values if math.isfinite(float(x))]
    return round(statistics.fmean(clean), 8) if clean else 0.0


def num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        value = row.get(key, default)
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def make_app(*, hdb_dir: Path, promotion_enabled: bool) -> tuple[ObservatoryApp, dict[str, Any]]:
    app = ObservatoryApp(
        config_override={
            "enable_goal_b_char_sa_string_mode": True,
            "enable_structure_level_retrieval_storage": True,
            "sensor_enable_stimulus_intensity_attribute_sa": True,
            "sensor_stimulus_intensity_attribute_min_er": 0.0,
            "sensor_attribute_er_ratio": 0.25,
            "sensor_attribute_ev_ratio": 0.0,
            "hdb_enable_background_repair": False,
            "hdb_data_dir": str(hdb_dir),
            "export_json": False,
            "export_html": False,
            "stimulus_residual_memory_promotion_enabled": bool(promotion_enabled),
        }
    )
    alignment = apply_experiment_default_app_overrides(app, source="paper_e08_time_like_promotion")
    return app, alignment


def build_ticks(*, seed_text: str | None, cue_text: str | None) -> list[dict[str, Any]]:
    ticks: list[dict[str, Any]] = []
    ticks.append({"text": str(seed_text)} if seed_text else {"empty": True})
    ticks.append({"empty": True})
    ticks.append({"empty": True})
    ticks.append({"text": str(cue_text)} if cue_text else {"empty": True})
    ticks.append({"empty": True})
    return ticks


def build_dataset_doc(*, dataset_id: str, seed_text: str | None, cue_text: str | None, promotion_enabled: bool) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "seed": 1,
        "time_basis": "tick",
        "tick_dt_ms": 3000,
        "app_config_override": {
            "stimulus_residual_memory_promotion_enabled": bool(promotion_enabled),
        },
        "episodes": [
            {
                "id": "ep",
                "ticks": build_ticks(seed_text=seed_text, cue_text=cue_text),
            }
        ],
    }


def write_imported_dataset(*, dataset_name: str, doc: dict[str, Any]) -> DatasetFileRef:
    imported_dir = imported_datasets_dir()
    imported_dir.mkdir(parents=True, exist_ok=True)
    path = imported_dir / dataset_name
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return DatasetFileRef(source="imported", rel_path=path.name)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def branch_seed_and_cue(*, spec: FamilySpec, branch: str) -> tuple[str | None, str | None, bool]:
    if branch == "on_matched":
        return spec.seed_text, spec.cue_text, True
    if branch == "off_matched":
        return spec.seed_text, spec.cue_text, False
    if branch == "on_no_seed":
        return None, spec.cue_text, True
    if branch == "on_no_cue":
        return spec.seed_text, None, True
    raise ValueError(f"Unknown branch: {branch}")


def pick_observation_row(metrics_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not metrics_rows:
        return {}
    return dict(metrics_rows[-1])


def extract_whitebox_snapshot(report: dict[str, Any]) -> dict[str, Any]:
    memory_snapshot = ((report.get("memory_activation", {}) or {}).get("snapshot", {}) or {})
    memory_items = [row for row in (memory_snapshot.get("items", []) or []) if isinstance(row, dict)]
    stimulus_result = ((report.get("stimulus_level", {}) or {}).get("result", {}) or {})
    debug = stimulus_result.get("debug", {}) or {}
    round_details = [row for row in (debug.get("round_details", []) or []) if isinstance(row, dict)]
    selected_match = {}
    fallback_selected_match = {}
    promoted_shadow_candidate = {}
    for round_detail in round_details:
        sm = round_detail.get("selected_match") or {}
        if isinstance(sm, dict) and sm and not fallback_selected_match:
            fallback_selected_match = dict(sm)
        if isinstance(sm, dict) and str(sm.get("match_mode", "") or "").strip() == "promoted_shadow_raw_residual":
            selected_match = dict(sm)
        shadow_rows = [
            row
            for row in (round_detail.get("shadow_candidate_details", []) or [])
            if isinstance(row, dict)
        ]
        for row in shadow_rows:
            if (
                row.get("candidate_kind") == "raw_residual_memory"
                and (
                    row.get("promoted_structure_id")
                    or row.get("v2_numeric_time_like_wildcard_applied")
                    or str(row.get("match_mode", "") or "") == "promoted_shadow_raw_residual"
                )
            ):
                if not promoted_shadow_candidate:
                    promoted_shadow_candidate = dict(row)
                if (
                    str(row.get("promoted_structure_id", "") or "").strip()
                    and str(sm.get("match_mode", "") or "").strip() == "promoted_shadow_raw_residual"
                ):
                    promoted_shadow_candidate = dict(row)
    if not selected_match and fallback_selected_match:
        selected_match = fallback_selected_match
    older_memory_count = 0
    current_tick = int(report.get("tick_counter", 0) or 0)
    for row in memory_items:
        try:
            tick_index = int(row.get("memory_tick_index", 0) or 0)
        except Exception:
            tick_index = 0
        if tick_index > 0 and tick_index < current_tick:
            older_memory_count += 1
    return {
        "memory_path_mode": str((report.get("memory_activation", {}) or {}).get("path_mode", "") or ""),
        "memory_item_count": int(len(memory_items)),
        "older_runtime_memory_visible_count": int(older_memory_count),
        "selected_match": selected_match,
        "promoted_shadow_candidate": promoted_shadow_candidate,
    }


def copy_run_artifacts(run_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for info in run_infos:
        run_id = str(info["run_id"])
        run_dir = Path(info["run_dir"])
        dest = RUN_DIR / run_id
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("manifest.json", "dataset.normalized.yaml", "dataset.source.yaml", "runner_timing.jsonl", "expectation_contract_events.jsonl"):
            src = run_dir / name
            if src.exists():
                shutil.copy2(src, dest / name)
        metrics_src = run_dir / "metrics.jsonl"
        if metrics_src.exists():
            shutil.copy2(metrics_src, dest / metrics_src.name)
        copied.append(
            {
                "run_id": run_id,
                "source_run_dir": str(run_dir),
                "artifact_run_dir": str(dest),
            }
        )
    return copied


def run_case(*, spec: FamilySpec, branch: str, stamp: str) -> tuple[dict[str, Any], dict[str, Any]]:
    seed_text, cue_text, promotion_enabled = branch_seed_and_cue(spec=spec, branch=branch)
    dataset_id = f"paper_e08_{stamp}_{spec.family}_{branch}"
    dataset_name = f"{dataset_id}.yaml"
    doc = build_dataset_doc(
        dataset_id=dataset_id,
        seed_text=seed_text,
        cue_text=cue_text,
        promotion_enabled=promotion_enabled,
    )
    dataset_ref = write_imported_dataset(dataset_name=dataset_name, doc=doc)
    dataset_src = imported_datasets_dir() / dataset_name
    shutil.copy2(dataset_src, DATASET_DIR / dataset_name)

    hdb_dir = Path(tempfile.mkdtemp(prefix=f"paper_e08_{spec.family}_{branch}_"))
    app = None
    run_id = f"paper_e08_{stamp}_{spec.family}_{branch}"
    try:
        app, alignment = make_app(hdb_dir=hdb_dir, promotion_enabled=promotion_enabled)
        result = run_dataset(
            app=app,
            dataset_ref=dataset_ref,
            options=RunOptions(
                reset_mode="clear_all",
                export_json=False,
                export_html=False,
                auto_tune_enabled=False,
            ),
            run_id=run_id,
            progress_cb=lambda payload: None,
        )
        if not result.get("success", False):
            raise RuntimeError(f"run_dataset failed for {run_id}: {result}")
        manifest = dict(result.get("manifest", {}) or {})
        metrics_rows = load_jsonl(resolve_run_dir(run_id) / "metrics.jsonl")
        observe = pick_observation_row(metrics_rows)
        whitebox = extract_whitebox_snapshot(dict(getattr(app, "_last_report", {}) or {}))
        row = {
            "family": spec.family,
            "seed_text": spec.seed_text,
            "cue_text": spec.cue_text,
            "branch": branch,
            "promotion_enabled": int(bool(promotion_enabled)),
            "seed_present": int(bool(seed_text)),
            "cue_present": int(bool(cue_text)),
            "dataset_id": dataset_id,
            "dataset_sha256": sha256_file(dataset_src),
            "run_id": run_id,
            "tick_count": int(manifest.get("tick_done", 0) or 0),
            "source_tick_done": int(manifest.get("source_tick_done", 0) or 0),
            "baseline_conforms": int(bool((manifest.get("dataset_runtime_override", {}) or {}).get("baseline_conforms_to_growth_cs_off", False))),
            "memory_path_mode": str(observe.get("memory_path_mode", "") or ""),
            "observe_time_like": int(int(observe.get("time_sensor_projection_binding_count", 0) or 0) > 0),
            "observe_internal_time_like": int(int(observe.get("internal_time_like_attribute_count", 0) or 0) > 0),
            "observe_wildcard": int(int(observe.get("stimulus_match_v2_numeric_time_like_wildcard_applied_count", 0) or 0) > 0),
            "observe_shadow_candidate": int(int(observe.get("stimulus_shadow_memory_match_v2_candidate_count", 0) or 0) > 0),
            "observe_shadow_eligible": int(int(observe.get("stimulus_shadow_memory_match_v2_eligible_count", 0) or 0) > 0),
            "observe_shadow_time_like_nonzero": int(int(observe.get("stimulus_shadow_memory_match_v2_numeric_time_like_nonzero_count", 0) or 0) > 0),
            "observe_shadow_wildcard": int(int(observe.get("stimulus_shadow_memory_match_v2_numeric_time_like_wildcard_applied_count", 0) or 0) > 0),
            "observe_shadow_time_bonus": int(int(observe.get("stimulus_shadow_memory_match_v2_time_factor_bonus_applied_count", 0) or 0) > 0),
            "observe_shadow_promoted": int(int(observe.get("stimulus_shadow_memory_match_v2_promoted_count", 0) or 0) > 0),
            "observe_selected_promoted": int(int(observe.get("stimulus_selected_promoted_shadow_raw_residual_count", 0) or 0) > 0),
            "shadow_candidate_count": int(observe.get("stimulus_shadow_memory_match_v2_candidate_count", 0) or 0),
            "shadow_eligible_count": int(observe.get("stimulus_shadow_memory_match_v2_eligible_count", 0) or 0),
            "shadow_promoted_count": int(observe.get("stimulus_shadow_memory_match_v2_promoted_count", 0) or 0),
            "selected_promoted_count": int(observe.get("stimulus_selected_promoted_shadow_raw_residual_count", 0) or 0),
            "shadow_time_like_score_mean": round(float(observe.get("stimulus_shadow_memory_match_v2_numeric_time_like_score_mean", 0.0) or 0.0), 8),
            "shadow_time_bonus_mean": round(float(observe.get("stimulus_shadow_memory_match_v2_time_factor_bonus_mean", 0.0) or 0.0), 8),
            "whitebox_memory_item_count": int(whitebox.get("memory_item_count", 0)),
            "whitebox_older_runtime_memory_visible_count": int(whitebox.get("older_runtime_memory_visible_count", 0)),
            "whitebox_selected_match_mode": str((whitebox.get("selected_match", {}) or {}).get("match_mode", "") or ""),
            "whitebox_selected_match_structure_id": str((whitebox.get("selected_match", {}) or {}).get("structure_id", "") or ""),
            "whitebox_selected_match_display": str((whitebox.get("selected_match", {}) or {}).get("display_text", "") or ""),
            "whitebox_shadow_candidate_kind": str((whitebox.get("promoted_shadow_candidate", {}) or {}).get("candidate_kind", "") or ""),
            "whitebox_shadow_memory_id": str((whitebox.get("promoted_shadow_candidate", {}) or {}).get("memory_id", "") or ""),
            "whitebox_shadow_promoted_structure_id": str((whitebox.get("promoted_shadow_candidate", {}) or {}).get("promoted_structure_id", "") or ""),
            "whitebox_shadow_wildcard_applied": int(bool((whitebox.get("promoted_shadow_candidate", {}) or {}).get("v2_numeric_time_like_wildcard_applied", False))),
            "whitebox_shadow_match_mode": str((whitebox.get("promoted_shadow_candidate", {}) or {}).get("match_mode", "") or ""),
        }
        evidence = {
            "manifest": manifest,
            "row": row,
            "whitebox_snapshot": whitebox,
            "metrics_row_count": len(metrics_rows),
            "run_dir": str(resolve_run_dir(run_id)),
            "dataset_source": str(dataset_src),
        }
        return row, evidence
    finally:
        try:
            if app is not None:
                app.close()
        except Exception:
            pass
        shutil.rmtree(hdb_dir, ignore_errors=True)


def build_pair_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_family: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_family.setdefault(str(row["family"]), {})[str(row["branch"])] = row
    pair_rows: list[dict[str, Any]] = []
    for family, mapping in sorted(by_family.items()):
        on_matched = mapping.get("on_matched", {})
        off_matched = mapping.get("off_matched", {})
        on_no_seed = mapping.get("on_no_seed", {})
        on_no_cue = mapping.get("on_no_cue", {})
        pair_rows.append(
            {
                "family": family,
                "baseline_conforms_all": int(
                    min(
                        int(on_matched.get("baseline_conforms", 0) or 0),
                        int(off_matched.get("baseline_conforms", 0) or 0),
                        int(on_no_seed.get("baseline_conforms", 0) or 0),
                        int(on_no_cue.get("baseline_conforms", 0) or 0),
                    )
                ),
                "on_matched_pass": int(
                    int(on_matched.get("observe_time_like", 0) or 0) == 1
                    and int(on_matched.get("observe_wildcard", 0) or 0) == 1
                    and int(on_matched.get("observe_shadow_candidate", 0) or 0) == 1
                    and int(on_matched.get("observe_shadow_eligible", 0) or 0) == 1
                    and int(on_matched.get("observe_shadow_wildcard", 0) or 0) == 1
                    and int(on_matched.get("observe_shadow_promoted", 0) or 0) == 1
                    and int(on_matched.get("observe_selected_promoted", 0) or 0) == 1
                    and str(on_matched.get("memory_path_mode", "") or "") == "runtime_em_only"
                ),
                "off_matched_quiet": int(
                    int(off_matched.get("observe_time_like", 0) or 0) == 1
                    and int(off_matched.get("observe_wildcard", 0) or 0) == 0
                    and int(off_matched.get("observe_shadow_candidate", 0) or 0) == 0
                    and int(off_matched.get("observe_shadow_promoted", 0) or 0) == 0
                    and int(off_matched.get("observe_selected_promoted", 0) or 0) == 0
                ),
                "on_no_seed_quiet": int(
                    int(on_no_seed.get("observe_time_like", 0) or 0) == 0
                    and int(on_no_seed.get("observe_wildcard", 0) or 0) == 0
                    and int(on_no_seed.get("observe_shadow_candidate", 0) or 0) == 0
                    and int(on_no_seed.get("observe_shadow_promoted", 0) or 0) == 0
                    and int(on_no_seed.get("observe_selected_promoted", 0) or 0) == 0
                ),
                "on_no_cue_quiet": int(
                    int(on_no_cue.get("observe_time_like", 0) or 0) == 0
                    and int(on_no_cue.get("observe_wildcard", 0) or 0) == 0
                    and int(on_no_cue.get("observe_shadow_candidate", 0) or 0) == 0
                    and int(on_no_cue.get("observe_shadow_promoted", 0) or 0) == 0
                    and int(on_no_cue.get("observe_selected_promoted", 0) or 0) == 0
                ),
                "on_matched_promoted_count": int(on_matched.get("shadow_promoted_count", 0) or 0),
                "on_matched_selected_promoted_count": int(on_matched.get("selected_promoted_count", 0) or 0),
                "off_matched_promoted_count": int(off_matched.get("shadow_promoted_count", 0) or 0),
                "on_no_seed_promoted_count": int(on_no_seed.get("shadow_promoted_count", 0) or 0),
                "on_no_cue_promoted_count": int(on_no_cue.get("shadow_promoted_count", 0) or 0),
            }
        )
    for row in pair_rows:
        row["all_ok"] = int(
            int(row.get("baseline_conforms_all", 0) or 0) == 1
            and int(row.get("on_matched_pass", 0) or 0) == 1
            and int(row.get("off_matched_quiet", 0) or 0) == 1
            and int(row.get("on_no_seed_quiet", 0) or 0) == 1
            and int(row.get("on_no_cue_quiet", 0) or 0) == 1
        )
    return pair_rows


def summarize_evidence(*, rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]]) -> dict[str, Any]:
    on_matched_rows = [row for row in rows if str(row.get("branch", "")) == "on_matched"]
    off_matched_rows = [row for row in rows if str(row.get("branch", "")) == "off_matched"]
    on_no_seed_rows = [row for row in rows if str(row.get("branch", "")) == "on_no_seed"]
    on_no_cue_rows = [row for row in rows if str(row.get("branch", "")) == "on_no_cue"]

    summary: dict[str, Any] = {
        "case_count": int(len(rows)),
        "family_count": int(len(pair_rows)),
        "baseline_conforms_ratio": round(safe_ratio(sum(int(row.get("baseline_conforms", 0) or 0) for row in rows), len(rows) or 1), 6),
        "on_matched_pass_ratio": round(safe_ratio(sum(int(row.get("on_matched_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "off_matched_quiet_ratio": round(safe_ratio(sum(int(row.get("off_matched_quiet", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "on_no_seed_quiet_ratio": round(safe_ratio(sum(int(row.get("on_no_seed_quiet", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "on_no_cue_quiet_ratio": round(safe_ratio(sum(int(row.get("on_no_cue_quiet", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "all_ok_ratio": round(safe_ratio(sum(int(row.get("all_ok", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "on_matched_time_like_ratio": round(safe_ratio(sum(int(row.get("observe_time_like", 0) or 0) for row in on_matched_rows), len(on_matched_rows) or 1), 6),
        "on_matched_wildcard_ratio": round(safe_ratio(sum(int(row.get("observe_wildcard", 0) or 0) for row in on_matched_rows), len(on_matched_rows) or 1), 6),
        "on_matched_shadow_candidate_ratio": round(safe_ratio(sum(int(row.get("observe_shadow_candidate", 0) or 0) for row in on_matched_rows), len(on_matched_rows) or 1), 6),
        "on_matched_shadow_eligible_ratio": round(safe_ratio(sum(int(row.get("observe_shadow_eligible", 0) or 0) for row in on_matched_rows), len(on_matched_rows) or 1), 6),
        "on_matched_shadow_promoted_ratio": round(safe_ratio(sum(int(row.get("observe_shadow_promoted", 0) or 0) for row in on_matched_rows), len(on_matched_rows) or 1), 6),
        "on_matched_selected_promoted_ratio": round(safe_ratio(sum(int(row.get("observe_selected_promoted", 0) or 0) for row in on_matched_rows), len(on_matched_rows) or 1), 6),
        "off_matched_selected_promoted_ratio": round(safe_ratio(sum(int(row.get("observe_selected_promoted", 0) or 0) for row in off_matched_rows), len(off_matched_rows) or 1), 6),
        "on_no_seed_selected_promoted_ratio": round(safe_ratio(sum(int(row.get("observe_selected_promoted", 0) or 0) for row in on_no_seed_rows), len(on_no_seed_rows) or 1), 6),
        "on_no_cue_selected_promoted_ratio": round(safe_ratio(sum(int(row.get("observe_selected_promoted", 0) or 0) for row in on_no_cue_rows), len(on_no_cue_rows) or 1), 6),
        "on_matched_shadow_time_like_score_mean": mean_or_zero([num(row, "shadow_time_like_score_mean") for row in on_matched_rows]),
        "on_matched_shadow_time_bonus_mean": mean_or_zero([num(row, "shadow_time_bonus_mean") for row in on_matched_rows]),
        "whitebox_older_runtime_memory_visible_ratio": round(
            safe_ratio(sum(1 for row in on_matched_rows if int(row.get("whitebox_older_runtime_memory_visible_count", 0) or 0) > 0), len(on_matched_rows) or 1),
            6,
        ),
    }
    wins = int(sum(int(row.get("all_ok", 0) or 0) for row in pair_rows))
    losses = int(len(pair_rows) - wins)
    summary["all_ok_sign_p"] = sign_test_p_value(wins, losses)

    support_level = "not_supported"
    if (
        len(pair_rows) >= 8
        and summary["baseline_conforms_ratio"] >= 0.999
        and summary["on_matched_pass_ratio"] >= 0.999
        and summary["off_matched_quiet_ratio"] >= 0.999
        and summary["on_no_seed_quiet_ratio"] >= 0.999
        and summary["on_no_cue_quiet_ratio"] >= 0.999
        and summary["all_ok_ratio"] >= 0.999
        and summary["all_ok_sign_p"] <= 0.01
    ):
        support_level = "strong_evidence"
    elif (
        len(pair_rows) >= 4
        and summary["on_matched_pass_ratio"] >= 0.80
        and summary["off_matched_quiet_ratio"] >= 0.80
        and summary["on_no_seed_quiet_ratio"] >= 0.80
        and summary["on_no_cue_quiet_ratio"] >= 0.80
    ):
        support_level = "useful_but_not_strong"
    summary["support_level"] = support_level
    return summary


def make_charts(*, rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]], stamp: str) -> list[Path]:
    plt = e01.setup_matplotlib()
    paths: list[Path] = []

    branch_order = ["on_matched", "off_matched", "on_no_seed", "on_no_cue"]
    labels = {
        "on_matched": "有 seed + 有 cue + 晋升开",
        "off_matched": "有 seed + 有 cue + 晋升关",
        "on_no_seed": "无 seed + 有 cue + 晋升开",
        "on_no_cue": "有 seed + 无 cue + 晋升开",
    }
    candidate_vals = []
    promoted_vals = []
    selected_vals = []
    for branch in branch_order:
        branch_rows = [row for row in rows if str(row.get("branch", "")) == branch]
        candidate_vals.append(mean_or_zero([num(row, "observe_shadow_candidate") for row in branch_rows]))
        promoted_vals.append(mean_or_zero([num(row, "observe_shadow_promoted") for row in branch_rows]))
        selected_vals.append(mean_or_zero([num(row, "observe_selected_promoted") for row in branch_rows]))
    fig, ax = plt.subplots(figsize=(10.2, 4.8))
    xs = list(range(len(branch_order)))
    width = 0.24
    ax.bar([x - width for x in xs], candidate_vals, width=width, color="#2563eb", label="影子候选出现比例")
    ax.bar(xs, promoted_vals, width=width, color="#dc2626", label="影子候选晋升比例")
    ax.bar([x + width for x in xs], selected_vals, width=width, color="#16a34a", label="晋升后重新入选比例")
    ax.set_xticks(xs, [labels[b] for b in branch_order], rotation=12)
    ax.set_ylim(0.0, 1.05)
    ax.set_ylabel("比例")
    ax.set_title("E08 时间显影下的残差记忆受控晋升对照")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    path = CHART_DIR / f"e08_time_like_residual_promotion_contrast_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    family_labels = [str(row.get("family", "")) for row in pair_rows]
    family_ok = [int(row.get("all_ok", 0) or 0) for row in pair_rows]
    fig, ax = plt.subplots(figsize=(9.4, 4.2))
    ax.bar(family_labels, family_ok, color=["#16a34a" if v else "#dc2626" for v in family_ok])
    ax.set_ylim(0.0, 1.1)
    ax.set_ylabel("all_ok")
    ax.set_title("E08 family 级四分支对照是否全部通过")
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = CHART_DIR / f"e08_time_like_residual_promotion_family_pass_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    return paths


def write_design_note(path: Path) -> None:
    lines = [
        "# E08 设计逻辑",
        "",
        "本实验把 E08 收窄为一个当前实现已经具备的最小白箱命题：",
        "",
        "1. 当前主链必须是 `runtime_em_only`，而不是旧记忆池旁路；",
        "2. 已有 seed 记忆与延迟 cue 同时存在时，time-like 属性要进入当前刺激级匹配；",
        "3. 在 promotion 开启的条件下，影子残差记忆候选要先显影、再晋升、再重新进入主竞争；",
        "4. 关闭 promotion、拿掉 seed 或拿掉 cue 后，这条链必须同时安静下来。",
        "",
        "因此实验采用四分支最小对照：",
        "",
        "- on_matched：有 seed + 有 cue + 晋升开；",
        "- off_matched：有 seed + 有 cue + 晋升关；",
        "- on_no_seed：无 seed + 有 cue + 晋升开；",
        "- on_no_cue：有 seed + 无 cue + 晋升开。",
        "",
        "正文只主张“时间显影条件下，残差记忆影子候选可以被受控晋升，并重新进入主链竞争”。",
        "正文刻意不把它扩写成广义情景召回或线索词精确选择性，因为当前实现还不能对白词身份选择性给出同样强的证据。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    *,
    rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    charts: list[Path],
    whitebox_case: dict[str, Any],
    stamp: str,
) -> Path:
    lines: list[str] = []
    lines.append(f"# E08 时间显影下的残差记忆受控晋升报告（{stamp}）")
    lines.append("")
    lines.append("## 核心结论")
    lines.append("")
    lines.append(f"- 支持等级：**{summary.get('support_level', 'unknown')}**")
    lines.append(f"- family 数：{int(summary.get('family_count', 0))}")
    lines.append(f"- 四分支整体通过比例：{summary.get('all_ok_ratio', 0.0):.3f}")
    lines.append(f"- 四分支整体符号检验 p 值：{summary.get('all_ok_sign_p', 1.0):.8f}")
    lines.append(f"- on_matched 通过比例：{summary.get('on_matched_pass_ratio', 0.0):.3f}")
    lines.append(f"- off_matched 静默比例：{summary.get('off_matched_quiet_ratio', 0.0):.3f}")
    lines.append(f"- on_no_seed 静默比例：{summary.get('on_no_seed_quiet_ratio', 0.0):.3f}")
    lines.append(f"- on_no_cue 静默比例：{summary.get('on_no_cue_quiet_ratio', 0.0):.3f}")
    lines.append("")
    lines.append("## 正文可使用的最小命题")
    lines.append("")
    lines.append(
        "在 `runtime_em_only` 主链中，只要旧 seed 记忆与延迟 cue 同时存在，"
        "时间样属性就可以进入当前刺激级匹配，使影子残差记忆候选从“仅可见”提升为"
        "“可晋升、可重新竞争”的对象。关闭晋升开关、拿掉 seed 或拿掉 cue 后，"
        "这条链会同步熄灭。"
    )
    lines.append("")
    lines.append("## 四分支对照")
    lines.append("")
    lines.append("| family | on_matched | off_matched quiet | on_no_seed quiet | on_no_cue quiet | all_ok |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for row in pair_rows:
        lines.append(
            f"| {row['family']} | {int(row['on_matched_pass'])} | {int(row['off_matched_quiet'])} | "
            f"{int(row['on_no_seed_quiet'])} | {int(row['on_no_cue_quiet'])} | {int(row['all_ok'])} |"
        )
    lines.append("")
    lines.append("## 分支均值")
    lines.append("")
    lines.append("| 分支 | 时间绑定 | 时间 wildcard | 影子候选 | 影子晋升 | 晋升后重入主竞争 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for branch in ("on_matched", "off_matched", "on_no_seed", "on_no_cue"):
        branch_rows = [row for row in rows if str(row.get("branch", "")) == branch]
        lines.append(
            f"| {branch} | "
            f"{mean_or_zero([num(row, 'observe_time_like') for row in branch_rows]):.3f} | "
            f"{mean_or_zero([num(row, 'observe_wildcard') for row in branch_rows]):.3f} | "
            f"{mean_or_zero([num(row, 'observe_shadow_candidate') for row in branch_rows]):.3f} | "
            f"{mean_or_zero([num(row, 'observe_shadow_promoted') for row in branch_rows]):.3f} | "
            f"{mean_or_zero([num(row, 'observe_selected_promoted') for row in branch_rows]):.3f} |"
        )
    lines.append("")
    lines.append("## 白箱样例")
    lines.append("")
    lines.append(
        "标准 matched 样例使用 5 个 source tick：`seed -> empty -> empty -> cue -> empty`。"
        "在 observation tick 中，旧运行态记忆仍然可见，且主链路径为 `runtime_em_only`。"
    )
    lines.append("")
    lines.append(
        f"- 样例 family：`{whitebox_case.get('family', '')}`；branch：`{whitebox_case.get('branch', '')}`"
    )
    lines.append(
        f"- 旧运行态记忆可见条数：`{int(whitebox_case.get('whitebox_older_runtime_memory_visible_count', 0) or 0)}`"
    )
    lines.append(
        f"- 主竞争最终入选模式：`{whitebox_case.get('whitebox_selected_match_mode', '')}`"
    )
    lines.append(
        f"- 影子候选种类：`{whitebox_case.get('whitebox_shadow_candidate_kind', '')}`；"
        f"memory_id：`{whitebox_case.get('whitebox_shadow_memory_id', '')}`"
    )
    lines.append(
        f"- 影子候选是否带时间 wildcard：`{int(whitebox_case.get('whitebox_shadow_wildcard_applied', 0) or 0)}`；"
        f"晋升结构 id：`{whitebox_case.get('whitebox_shadow_promoted_structure_id', '')}`"
    )
    lines.append("")
    lines.append("## 图表")
    lines.append("")
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    lines.append("## 备注")
    lines.append("")
    lines.append("- 本实验不主张广义情景回忆，只主张“时间显影下的残差记忆受控晋升”。")
    lines.append("- 本实验不主张线索词身份选择性，因为当前实现中，错误 cue 并不会稳定熄灭这条链。")
    lines.append("")
    path = REPORT_DIR / f"E08_time_like_residual_promotion_report_{stamp}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_experiment(*, stamp: str, family_count: int) -> dict[str, Any]:
    ensure_dirs()
    specs = FAMILY_SPECS[: max(1, min(int(family_count), len(FAMILY_SPECS)))]
    rows: list[dict[str, Any]] = []
    run_infos: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    for spec in specs:
        for branch in BRANCHES:
            row, evidence = run_case(spec=spec, branch=branch, stamp=stamp)
            rows.append(row)
            run_infos.append({"run_id": row["run_id"], "run_dir": evidence["run_dir"]})
            evidence_rows.append(evidence)
    rows.sort(key=lambda row: (str(row["family"]), str(row["branch"])))
    pair_rows = build_pair_rows(rows)
    summary = summarize_evidence(rows=rows, pair_rows=pair_rows)
    charts = make_charts(rows=rows, pair_rows=pair_rows, stamp=stamp)
    write_design_note(REPORT_DIR / "E08_time_like_residual_promotion_design_logic.md")
    whitebox_case = next((row for row in rows if str(row.get("branch", "")) == "on_matched"), {})
    whitebox_evidence = next(
        (
            evidence
            for evidence in evidence_rows
            if str((evidence.get("row", {}) or {}).get("family", "")) == str(whitebox_case.get("family", ""))
            and str((evidence.get("row", {}) or {}).get("branch", "")) == "on_matched"
        ),
        {},
    )
    report = write_report(
        rows=rows,
        pair_rows=pair_rows,
        summary=summary,
        charts=charts,
        whitebox_case=whitebox_case,
        stamp=stamp,
    )
    e01.write_csv(TABLE_DIR / f"e08_time_like_residual_promotion_case_rows_{stamp}.csv", rows)
    e01.write_csv(TABLE_DIR / f"e08_time_like_residual_promotion_pair_rows_{stamp}.csv", pair_rows)
    e01.write_json(TABLE_DIR / f"e08_time_like_residual_promotion_summary_{stamp}.json", summary)
    e01.write_json(TABLE_DIR / f"e08_time_like_residual_promotion_whitebox_{stamp}.json", whitebox_evidence)
    copied_runs = copy_run_artifacts(run_infos)
    evidence = {
        "experiment_id": "E08",
        "stamp": stamp,
        "support_level": summary.get("support_level", "unknown"),
        "summary": summary,
        "artifacts": {
            "case_rows": str(TABLE_DIR / f"e08_time_like_residual_promotion_case_rows_{stamp}.csv"),
            "pair_rows": str(TABLE_DIR / f"e08_time_like_residual_promotion_pair_rows_{stamp}.csv"),
            "summary": str(TABLE_DIR / f"e08_time_like_residual_promotion_summary_{stamp}.json"),
            "whitebox": str(TABLE_DIR / f"e08_time_like_residual_promotion_whitebox_{stamp}.json"),
            "report": str(report),
            "design_note": str(REPORT_DIR / "E08_time_like_residual_promotion_design_logic.md"),
            "charts": [str(path) for path in charts],
            "copied_runs": copied_runs,
        },
    }
    e01.write_json(MANIFEST_DIR / f"E08_time_like_residual_promotion_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E08_time_like_residual_promotion_latest.json", evidence)
    return evidence


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper E08 time-like residual-promotion experiment.")
    parser.add_argument("--stamp", default=STAMP_DEFAULT)
    parser.add_argument("--family-count", type=int, default=12)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    stamp = str(args.stamp or "").strip() or now_stamp()
    evidence = run_experiment(stamp=stamp, family_count=int(args.family_count))
    print(
        json.dumps(
            {
                "ok": True,
                "stamp": stamp,
                "support": evidence["support_level"],
                "report": evidence["artifacts"]["report"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
