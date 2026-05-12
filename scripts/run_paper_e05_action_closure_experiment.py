# -*- coding: utf-8 -*-
"""Run paper E05 action-closure experiment.

Paper-facing E05 claim
----------------------
This experiment tests a narrow and auditable claim:

1. an explicit weather request can complete a source-visible native action loop
   inside AP rather than only firing an external stub;
2. after that loop has completed, a later weak weather probe for the same
   target shows a stronger action-readiness state than a matched branch that
   only saw the weak probe itself and never completed the action.

The design intentionally avoids broad claims such as "AP has already learned a
general weather policy".  It only verifies a minimum closure chain:

explicit query -> source-visible weather execution on the next tick ->
runtime action-node projection -> stronger later weak-probe readiness.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from _reproduction_paths import AP_ROOT, ARTIFACT_ROOT, ATTACHMENT_ROOT

if str(AP_ROOT) not in sys.path:
    sys.path.insert(0, str(AP_ROOT))

import run_paper_e01_experiment as e01
import run_paper_e03_reward_shaping_experiment as e03
import run_paper_e04_punish_correction_experiment as e04
from observatory._app import ObservatoryApp
from observatory.experiment.io import sha256_file
from observatory.experiment.runner import RunOptions, run_dataset
from observatory.experiment.storage import DatasetFileRef, imported_datasets_dir, resolve_run_dir


E05_ROOT = ARTIFACT_ROOT / "E05_action_closure"
DATASET_DIR = E05_ROOT / "datasets"
RUN_DIR = E05_ROOT / "runs"
TABLE_DIR = E05_ROOT / "tables"
CHART_DIR = E05_ROOT / "charts"
REPORT_DIR = E05_ROOT / "reports"
MANIFEST_DIR = E05_ROOT / "manifests"

LABEL_KEY = "paper_e05_action_closure"
CURRICULUM_VERSION = "paper_e05_v1_action_closure"

BRANCH_EXECUTED = "executed_history"
BRANCH_WEAK = "weak_only_control"
BRANCHES = (BRANCH_EXECUTED, BRANCH_WEAK)


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dirs() -> None:
    for path in (DATASET_DIR, RUN_DIR, TABLE_DIR, CHART_DIR, REPORT_DIR, MANIFEST_DIR, imported_datasets_dir()):
        path.mkdir(parents=True, exist_ok=True)


def num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        value = row.get(key, default)
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator) / float(denominator) if abs(float(denominator)) > 1e-12 else 0.0


def sign_test_p_value(wins: int, losses: int) -> float:
    n = int(wins) + int(losses)
    if n <= 0:
        return 1.0
    k = min(int(wins), int(losses))
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return round(min(1.0, 2.0 * tail), 8)


def family_specs(limit: int) -> list[dict[str, str]]:
    return e04.family_specs(limit)


def app_config_override(*, reward_coef: float, punish_coef: float, alias_ttl: int) -> dict[str, Any]:
    # Reuse the E03 runtime baseline because it already disables trivial
    # carry-over through threshold fatigue while keeping action-side modulation
    # observable and reproducible.
    return e03.app_config_override(reward_coef=reward_coef, punish_coef=punish_coef, alias_ttl=alias_ttl)


def tick_doc(
    *,
    text: str,
    case_id: str,
    branch: str,
    phase: str,
    source_text_index: int,
) -> dict[str, Any]:
    return {
        "text": str(text),
        "tags": ["paper", "E05", "action_closure", branch, case_id, phase],
        "labels": {
            LABEL_KEY: {
                "case_id": case_id,
                "branch": branch,
                "phase": phase,
                "source_text_index": int(source_text_index),
                "curriculum_version": CURRICULUM_VERSION,
            },
            "stream": {
                "role": "user",
                "kind": "message",
                "phase": "action_closure",
                "pure_text": True,
            },
        },
        "meta": {
            "role": "user",
            "kind": "message",
            "phase": "action_closure",
            "real_input_index": int(source_text_index),
        },
    }


def build_ticks(spec: dict[str, str], *, branch: str) -> list[dict[str, Any]]:
    case_id = str(spec["case_id"])
    if branch == BRANCH_EXECUTED:
        return [
            tick_doc(
                text=str(spec["right_train"]),
                case_id=case_id,
                branch=branch,
                phase="train",
                source_text_index=0,
            ),
            tick_doc(
                text=str(spec["neutral_text_b"]),
                case_id=case_id,
                branch=branch,
                phase="buffer",
                source_text_index=1,
            ),
            tick_doc(
                text=str(spec["right_probe"]),
                case_id=case_id,
                branch=branch,
                phase="probe",
                source_text_index=2,
            ),
        ]
    if branch == BRANCH_WEAK:
        return [
            tick_doc(
                text=str(spec["right_probe"]),
                case_id=case_id,
                branch=branch,
                phase="train",
                source_text_index=0,
            ),
            tick_doc(
                text=str(spec["neutral_text_b"]),
                case_id=case_id,
                branch=branch,
                phase="buffer",
                source_text_index=1,
            ),
            tick_doc(
                text=str(spec["right_probe"]),
                case_id=case_id,
                branch=branch,
                phase="probe",
                source_text_index=2,
            ),
        ]
    raise ValueError(f"unknown branch: {branch}")


def dataset_doc(
    spec: dict[str, str],
    *,
    branch: str,
    replicate: int,
    reward_coef: float,
    punish_coef: float,
    alias_ttl: int,
) -> dict[str, Any]:
    ticks = build_ticks(spec, branch=branch)
    dataset_id = f"paper_e05_{spec['case_id']}_{branch}_r{replicate}_v1"
    return {
        "dataset_id": dataset_id,
        "title": f"E05 先天行动闭环 - {spec['case_id']} - {branch} - r{replicate}",
        "description": "E05 定向实验：验证显式天气请求是否完成原生行动闭环，并在后续弱 probe 上留下更强的行动准备度。",
        "schema_version": "observatory.dataset.v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "time_basis": "tick",
        "tick_dt_ms": 3000,
        "seed": 2026051105 + int(replicate),
        "app_config_override": app_config_override(
            reward_coef=reward_coef,
            punish_coef=punish_coef,
            alias_ttl=alias_ttl,
        ),
        "meta": {
            "paper_experiment": "E05_action_closure",
            "curriculum_version": CURRICULUM_VERSION,
            "case_id": spec["case_id"],
            "branch": branch,
            "replicate": int(replicate),
            "city": spec["city_right"],
            "event": spec["event"],
            "explicit_train": spec["right_train"],
            "weak_probe": spec["right_probe"],
            "reward_coef": float(reward_coef),
            "punish_coef": float(punish_coef),
            "alias_ttl": int(alias_ttl),
        },
        "episodes": [
            {
                "id": f"paper_e05_{spec['case_id']}_{branch}_r{replicate}",
                "title": f"E05 {spec['case_id']} {branch} r{replicate}",
                "tags": ["paper", "E05", "action_closure", branch, str(spec["case_id"])],
                "repeat": 1,
                "ticks": ticks,
            }
        ],
    }


def write_datasets(
    *,
    replicates: int,
    family_limit: int,
    reward_coef: float,
    punish_coef: float,
    alias_ttl: int,
) -> list[dict[str, Any]]:
    datasets: list[dict[str, Any]] = []
    for spec in family_specs(family_limit):
        for replicate in range(1, replicates + 1):
            for branch in BRANCHES:
                doc = dataset_doc(
                    spec,
                    branch=branch,
                    replicate=replicate,
                    reward_coef=reward_coef,
                    punish_coef=punish_coef,
                    alias_ttl=alias_ttl,
                )
                name = f"{doc['dataset_id']}.yaml"
                text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
                artifact_path = DATASET_DIR / name
                imported_path = imported_datasets_dir() / name
                artifact_path.write_text(text, encoding="utf-8")
                imported_path.write_text(text, encoding="utf-8")
                datasets.append(
                    {
                        "case_id": spec["case_id"],
                        "branch": branch,
                        "replicate": replicate,
                        "city": spec["city_right"],
                        "event": spec["event"],
                        "explicit_train": spec["right_train"],
                        "weak_probe": spec["right_probe"],
                        "dataset_id": doc["dataset_id"],
                        "dataset_name": name,
                        "artifact_path": artifact_path,
                        "imported_path": imported_path,
                        "sha256": sha256_file(imported_path),
                    }
                )
    return datasets


def quiet_progress(payload: dict[str, Any]) -> None:
    stage = str(payload.get("stage", "") or "")
    if stage in {"loading_dataset", "resetting_runtime", "running_tick", "finished", "failed"}:
        done = payload.get("source_tick_done", payload.get("tick_done", ""))
        planned = payload.get("tick_planned", "")
        if stage == "running_tick" and done not in {0, "", None}:
            print(f"[E05] {stage}: {done}/{planned}", flush=True)


def run_one_dataset(dataset_info: dict[str, Any], *, run_stamp: str, max_ticks: int | None) -> dict[str, Any]:
    run_id = f"paper_e05_{dataset_info['case_id']}_{dataset_info['branch']}_r{dataset_info['replicate']}_{run_stamp}"
    print(f"[E05] start run_id={run_id}", flush=True)
    app = ObservatoryApp()
    try:
        app._config["outputs_cleanup_enabled"] = False  # type: ignore[attr-defined]
        app._config["export_cycle_json_history"] = False  # type: ignore[attr-defined]
        app._config["export_cycle_html_history"] = False  # type: ignore[attr-defined]
        setattr(app, "_cleanup_jsonl_logs", lambda: None)
        setattr(app, "_cleanup_output_reports", lambda: None)
    except Exception:
        pass
    try:
        result = run_dataset(
            app=app,
            dataset_ref=DatasetFileRef(source="imported", rel_path=str(dataset_info["dataset_name"])),
            options=RunOptions(
                reset_mode="clear_all",
                clean_run=False,
                export_json=False,
                export_html=False,
                auto_tune_enabled=False,
                max_ticks=max_ticks,
            ),
            run_id=run_id,
            progress_cb=quiet_progress,
        )
    finally:
        app.close()
    run_dir = resolve_run_dir(run_id)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    return {
        **dataset_info,
        "run_id": run_id,
        "run_dir": run_dir,
        "manifest": manifest,
        "success": bool(result.get("success", False)),
        "status": manifest.get("status", ""),
    }


def phase_rows_for_run(run_info: dict[str, Any]) -> list[dict[str, Any]]:
    rows = e01.read_metrics_rows_from_run_dir(Path(run_info["run_dir"]))
    out: list[dict[str, Any]] = []
    for row in rows:
        label_block = ((row.get("labels") or {}).get(LABEL_KEY) or {}) if isinstance(row.get("labels"), dict) else {}
        if not isinstance(label_block, dict):
            continue
        phase = str(label_block.get("phase", "") or "")
        if phase not in {"train", "buffer", "probe"}:
            continue
        entry = {
            "case_id": str(run_info["case_id"]),
            "branch": str(run_info["branch"]),
            "replicate": int(run_info["replicate"]),
            "run_id": str(run_info["run_id"]),
            "tick_index": int(row.get("tick_index", 0) or 0),
            "phase": phase,
            "synthetic_tick": int(bool(row.get("synthetic_tick", False))),
            "input_is_empty": int(bool(row.get("input_is_empty", False))),
            "source_dataset_tick_index": row.get("source_dataset_tick_index"),
            "input_text_preview": str(row.get("input_text_preview", "") or ""),
            "action_attempted_weather_stub": int(num(row, "action_attempted_weather_stub")),
            "action_executed_weather_stub": int(num(row, "action_executed_weather_stub")),
            "action_executed_weather_stub_source_visible": int(num(row, "action_executed_weather_stub_source_visible")),
            "action_scheduled_weather_stub": int(num(row, "action_scheduled_weather_stub")),
            "action_scheduled_weather_stub_source_visible": int(num(row, "action_scheduled_weather_stub_source_visible")),
            "action_drive_weather_stub_max": round(num(row, "action_drive_weather_stub_max"), 8),
            "action_drive_margin_weather_stub_max": round(num(row, "action_drive_margin_weather_stub_max"), 8),
            "action_node_weather_stub_count": int(num(row, "action_node_weather_stub_count")),
            "action_active_weather_stub_count": int(num(row, "action_active_weather_stub_count")),
            "action_ready_weather_stub_count": int(num(row, "action_ready_weather_stub_count")),
            "runtime_signal_node_count": int(num(row, "runtime_signal_node_count")),
            "runtime_signal_node_active_count": int(num(row, "runtime_signal_node_active_count")),
            "runtime_action_node_count": int(num(row, "runtime_action_node_count")),
            "runtime_action_node_active_count": int(num(row, "runtime_action_node_active_count")),
            "runtime_action_node_executed_count": int(num(row, "runtime_action_node_executed_count")),
            "runtime_action_target_ref_count": int(num(row, "runtime_action_target_ref_count")),
            "runtime_action_target_item_count": int(num(row, "runtime_action_target_item_count")),
            "runtime_action_node_weather_stub_count": int(num(row, "runtime_action_node_weather_stub_count")),
            "runtime_action_node_weather_stub_active_count": int(num(row, "runtime_action_node_weather_stub_active_count")),
            "runtime_action_node_weather_stub_executed_count": int(num(row, "runtime_action_node_weather_stub_executed_count")),
        }
        out.append(entry)
    out.sort(key=lambda x: int(x["tick_index"]))
    return out


def build_row_metrics(run_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run_info in run_infos:
        rows.extend(phase_rows_for_run(run_info))
    rows.sort(key=lambda x: (str(x["case_id"]), int(x["replicate"]), str(x["branch"]), int(x["tick_index"])))
    return rows


def build_pair_rows(run_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index: dict[tuple[str, int, str], dict[str, Any]] = {}
    for run_info in run_infos:
        phases = phase_rows_for_run(run_info)
        pack = {
            "train": next((row for row in phases if str(row.get("phase", "")) == "train"), None),
            "buffer": next((row for row in phases if str(row.get("phase", "")) == "buffer"), None),
            "probe": next((row for row in phases if str(row.get("phase", "")) == "probe"), None),
            "meta": run_info,
        }
        index[(str(run_info["case_id"]), int(run_info["replicate"]), str(run_info["branch"]))] = pack

    pair_rows: list[dict[str, Any]] = []
    for case_id in sorted({str(run_info["case_id"]) for run_info in run_infos}):
        replicates = sorted({int(run_info["replicate"]) for run_info in run_infos if str(run_info["case_id"]) == case_id})
        for replicate in replicates:
            executed_pack = index.get((case_id, replicate, BRANCH_EXECUTED))
            weak_pack = index.get((case_id, replicate, BRANCH_WEAK))
            if not executed_pack or not weak_pack:
                continue
            executed_train = executed_pack["train"] or {}
            executed_buffer = executed_pack["buffer"] or {}
            executed_probe = executed_pack["probe"] or {}
            weak_train = weak_pack["train"] or {}
            weak_buffer = weak_pack["buffer"] or {}
            weak_probe = weak_pack["probe"] or {}
            meta = executed_pack["meta"]

            pair: dict[str, Any] = {
                "case_id": case_id,
                "replicate": replicate,
                "city": str(meta.get("city", "") or ""),
                "event": str(meta.get("event", "") or ""),
                "probe_text": str(meta.get("weak_probe", "") or ""),
                "executed_train_attempted": int(num(executed_train, "action_attempted_weather_stub")),
                "weak_train_attempted": int(num(weak_train, "action_attempted_weather_stub")),
                "executed_buffer_executed_source_visible": int(num(executed_buffer, "action_executed_weather_stub_source_visible")),
                "weak_buffer_executed_source_visible": int(num(weak_buffer, "action_executed_weather_stub_source_visible")),
                "executed_buffer_runtime_action_weather_executed": int(num(executed_buffer, "runtime_action_node_weather_stub_executed_count")),
                "weak_buffer_runtime_action_weather_executed": int(num(weak_buffer, "runtime_action_node_weather_stub_executed_count")),
                "executed_probe_drive": round(num(executed_probe, "action_drive_weather_stub_max"), 8),
                "weak_probe_drive": round(num(weak_probe, "action_drive_weather_stub_max"), 8),
                "executed_probe_margin": round(num(executed_probe, "action_drive_margin_weather_stub_max"), 8),
                "weak_probe_margin": round(num(weak_probe, "action_drive_margin_weather_stub_max"), 8),
                "executed_probe_action_node_count": int(num(executed_probe, "action_node_weather_stub_count")),
                "weak_probe_action_node_count": int(num(weak_probe, "action_node_weather_stub_count")),
                "executed_probe_runtime_action_count": int(num(executed_probe, "runtime_action_node_weather_stub_count")),
                "weak_probe_runtime_action_count": int(num(weak_probe, "runtime_action_node_weather_stub_count")),
                "executed_probe_runtime_action_active_count": int(num(executed_probe, "runtime_action_node_weather_stub_active_count")),
                "weak_probe_runtime_action_active_count": int(num(weak_probe, "runtime_action_node_weather_stub_active_count")),
            }
            pair["probe_drive_advantage"] = round(pair["executed_probe_drive"] - pair["weak_probe_drive"], 8)
            pair["probe_margin_advantage"] = round(pair["executed_probe_margin"] - pair["weak_probe_margin"], 8)
            pair["supports_explicit_train_trigger"] = int(pair["executed_train_attempted"] >= 1)
            pair["supports_weak_train_quiet"] = int(
                pair["weak_train_attempted"] == 0
                and pair["weak_buffer_executed_source_visible"] == 0
                and pair["weak_buffer_runtime_action_weather_executed"] == 0
            )
            pair["supports_source_visible_execution"] = int(pair["executed_buffer_executed_source_visible"] >= 1)
            pair["supports_runtime_projection"] = int(pair["executed_buffer_runtime_action_weather_executed"] >= 1)
            pair["supports_probe_drive_advantage"] = int(pair["probe_drive_advantage"] > 0.0)
            pair["supports_probe_margin_advantage"] = int(pair["probe_margin_advantage"] > 0.0)
            pair["supports_probe_runtime_presence"] = int(
                pair["executed_probe_runtime_action_count"] >= 1
                and pair["executed_probe_runtime_action_active_count"] >= 1
            )
            pair["supports_clean_closure_chain"] = int(
                pair["supports_explicit_train_trigger"] == 1
                and pair["supports_weak_train_quiet"] == 1
                and pair["supports_source_visible_execution"] == 1
                and pair["supports_runtime_projection"] == 1
                and pair["supports_probe_drive_advantage"] == 1
                and pair["supports_probe_margin_advantage"] == 1
                and pair["supports_probe_runtime_presence"] == 1
            )
            pair_rows.append(pair)
    pair_rows.sort(key=lambda x: (str(x["case_id"]), int(x["replicate"])))
    return pair_rows


def summarize_evidence(pair_rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(pair_rows)
    drive_advantages = [num(row, "probe_drive_advantage") for row in pair_rows]
    margin_advantages = [num(row, "probe_margin_advantage") for row in pair_rows]
    explicit_train_count = sum(int(row.get("supports_explicit_train_trigger", 0)) for row in pair_rows)
    weak_quiet_count = sum(int(row.get("supports_weak_train_quiet", 0)) for row in pair_rows)
    source_visible_count = sum(int(row.get("supports_source_visible_execution", 0)) for row in pair_rows)
    runtime_projection_count = sum(int(row.get("supports_runtime_projection", 0)) for row in pair_rows)
    probe_runtime_presence_count = sum(int(row.get("supports_probe_runtime_presence", 0)) for row in pair_rows)
    drive_adv_count = sum(int(row.get("supports_probe_drive_advantage", 0)) for row in pair_rows)
    margin_adv_count = sum(int(row.get("supports_probe_margin_advantage", 0)) for row in pair_rows)
    clean_chain_count = sum(int(row.get("supports_clean_closure_chain", 0)) for row in pair_rows)

    drive_wins = sum(1 for x in drive_advantages if x > 0.0)
    drive_losses = sum(1 for x in drive_advantages if x < 0.0)
    margin_wins = sum(1 for x in margin_advantages if x > 0.0)
    margin_losses = sum(1 for x in margin_advantages if x < 0.0)

    summary: dict[str, Any] = {
        "pair_count": n,
        "explicit_train_trigger_ratio": round(safe_ratio(explicit_train_count, n or 1), 6),
        "weak_control_quiet_ratio": round(safe_ratio(weak_quiet_count, n or 1), 6),
        "source_visible_execution_ratio": round(safe_ratio(source_visible_count, n or 1), 6),
        "runtime_projection_ratio": round(safe_ratio(runtime_projection_count, n or 1), 6),
        "probe_runtime_presence_ratio": round(safe_ratio(probe_runtime_presence_count, n or 1), 6),
        "probe_drive_advantage_ratio": round(safe_ratio(drive_adv_count, n or 1), 6),
        "probe_margin_advantage_ratio": round(safe_ratio(margin_adv_count, n or 1), 6),
        "clean_closure_chain_ratio": round(safe_ratio(clean_chain_count, n or 1), 6),
        "probe_drive_advantage_mean": round(statistics.fmean(drive_advantages), 8) if drive_advantages else 0.0,
        "probe_margin_advantage_mean": round(statistics.fmean(margin_advantages), 8) if margin_advantages else 0.0,
        "explicit_probe_drive_mean": round(statistics.fmean([num(row, "executed_probe_drive") for row in pair_rows]), 8) if pair_rows else 0.0,
        "weak_probe_drive_mean": round(statistics.fmean([num(row, "weak_probe_drive") for row in pair_rows]), 8) if pair_rows else 0.0,
        "probe_drive_advantage_sign_p": sign_test_p_value(drive_wins, drive_losses),
        "probe_margin_advantage_sign_p": sign_test_p_value(margin_wins, margin_losses),
    }

    support_level = "not_supported"
    if (
        n >= 12
        and summary["explicit_train_trigger_ratio"] >= 0.95
        and summary["weak_control_quiet_ratio"] >= 0.95
        and summary["source_visible_execution_ratio"] >= 0.95
        and summary["runtime_projection_ratio"] >= 0.95
        and summary["probe_runtime_presence_ratio"] >= 0.95
        and summary["probe_drive_advantage_ratio"] >= 0.95
        and summary["probe_margin_advantage_ratio"] >= 0.95
        and summary["clean_closure_chain_ratio"] >= 0.95
        and summary["probe_drive_advantage_mean"] >= 0.10
        and summary["probe_margin_advantage_mean"] >= 0.10
        and summary["probe_drive_advantage_sign_p"] <= 0.01
        and summary["probe_margin_advantage_sign_p"] <= 0.01
    ):
        support_level = "strong_evidence"
    elif (
        n >= 6
        and summary["explicit_train_trigger_ratio"] >= 0.75
        and summary["source_visible_execution_ratio"] >= 0.75
        and summary["probe_drive_advantage_ratio"] >= 0.75
    ):
        support_level = "useful_but_not_strong"
    summary["support_level"] = support_level
    return summary


def copy_run_artifacts(run_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for run_info in run_infos:
        src = Path(run_info["run_dir"])
        dst = RUN_DIR / str(run_info["run_id"])
        dst.mkdir(parents=True, exist_ok=True)
        copied_files: list[str] = []
        for name in ("manifest.json", "dataset.normalized.yaml", "dataset.source.yaml", "metrics.jsonl", "runner_timing.jsonl"):
            src_path = src / name
            if not src_path.exists():
                continue
            shutil.copy2(src_path, dst / name)
            copied_files.append(name)
        copied.append({"run_id": str(run_info["run_id"]), "path": str(dst), "files": copied_files})
    return copied


def make_charts(pair_rows: list[dict[str, Any]], stamp: str) -> list[Path]:
    plt = e01.setup_matplotlib()
    paths: list[Path] = []

    xs = list(range(len(pair_rows)))
    labels = [f"{row['case_id']}-r{row['replicate']}" for row in pair_rows]

    fig, ax = plt.subplots(figsize=(12.8, 5.4), dpi=160)
    ax.bar([x - 0.18 for x in xs], [num(row, "executed_probe_drive") for row in pair_rows], width=0.36, color="#2b8a3e", label="显式执行史 probe drive")
    ax.bar([x + 0.18 for x in xs], [num(row, "weak_probe_drive") for row in pair_rows], width=0.36, color="#1c7ed6", label="弱历史对照 probe drive")
    ax.axhline(0.6, color="#999999", linestyle="--", linewidth=1.0, label="weather_stub 阈值")
    ax.set_xticks(xs, labels, rotation=35, ha="right")
    ax.set_ylabel("action_drive_weather_stub_max")
    ax.set_title("E05 后续弱天气 probe 的行动准备度对比")
    ax.legend(frameon=False)
    fig.tight_layout()
    chart_path = CHART_DIR / f"e05_action_closure_probe_drive_{stamp}.png"
    fig.savefig(chart_path, bbox_inches="tight")
    plt.close(fig)
    paths.append(chart_path)

    fig, ax = plt.subplots(figsize=(10.8, 4.8), dpi=160)
    stages = ["显式训练触发", "source-visible 执行", "runtime 回投", "probe drive 优势", "probe margin 优势", "完整闭环"]
    values = [
        safe_ratio(sum(int(row.get("supports_explicit_train_trigger", 0)) for row in pair_rows), len(pair_rows) or 1),
        safe_ratio(sum(int(row.get("supports_source_visible_execution", 0)) for row in pair_rows), len(pair_rows) or 1),
        safe_ratio(sum(int(row.get("supports_runtime_projection", 0)) for row in pair_rows), len(pair_rows) or 1),
        safe_ratio(sum(int(row.get("supports_probe_drive_advantage", 0)) for row in pair_rows), len(pair_rows) or 1),
        safe_ratio(sum(int(row.get("supports_probe_margin_advantage", 0)) for row in pair_rows), len(pair_rows) or 1),
        safe_ratio(sum(int(row.get("supports_clean_closure_chain", 0)) for row in pair_rows), len(pair_rows) or 1),
    ]
    ax.bar(range(len(stages)), values, color=["#2b8a3e", "#2f9e44", "#40c057", "#1971c2", "#1c7ed6", "#0b7285"])
    ax.set_ylim(0.0, 1.05)
    ax.set_xticks(range(len(stages)), stages, rotation=20, ha="right")
    ax.set_ylabel("通过比例")
    ax.set_title("E05 行动闭环各阶段通过比例")
    for idx, value in enumerate(values):
        ax.text(idx, value + 0.02, f"{value:.3f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    chart_path = CHART_DIR / f"e05_action_closure_chain_ratios_{stamp}.png"
    fig.savefig(chart_path, bbox_inches="tight")
    plt.close(fig)
    paths.append(chart_path)
    return paths


def write_design_note(path: Path) -> None:
    lines = [
        "# E05 设计逻辑",
        "",
        "本实验故意把命题收窄到一个最小且容易被证伪的链条：",
        "",
        "1. 显式天气请求必须先在 source-visible tick 里触发 `weather_stub` 行动尝试；",
        "2. 该行动必须在下一条 source-visible buffer tick 中完成，而不是只停留在外部脚本层；",
        "3. 完成后的行动状态必须以 runtime action node 的形式回投到 AP 内部可观测状态中；",
        "4. 随后再次输入同目标的弱天气 probe 时，其行动准备度必须高于只见过弱 probe 本身、但从未完成行动的对照支路。",
        "",
        "关键控制如下：",
        "",
        "- 使用与 E03 一致的实验基线，关闭全局阈值调制和行动疲劳，并把 `drive_decay_ratio` 设为 `0.0`；",
        "- 这样做的目的是排除“仅仅因为上一个 tick 还残留 drive，所以后一个 tick 看起来更强”这一平凡解释；",
        "- 因此，后续弱 probe 上出现的优势不能被解释为简单的 drive 连续携带，而更应解释为一次已完成行动及其反馈在系统内部留下了可再利用的痕迹。",
        "",
        "对照支路不是随机文本，而是“同一个弱天气 probe 自己训练自己”的弱历史支路。这样可以把文本表面相似度控制住，使分支差异主要来自是否真的完成过原生行动闭环。",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(
    *,
    pair_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    charts: list[Path],
    datasets: list[dict[str, Any]],
    run_infos: list[dict[str, Any]],
    stamp: str,
    reward_coef: float,
    punish_coef: float,
    alias_ttl: int,
) -> Path:
    lines: list[str] = []
    lines.append(f"# E05 先天行动闭环报告（{stamp}）")
    lines.append("")
    lines.append("## 核心结论")
    lines.append(f"- 支持等级：**{summary.get('support_level', 'unknown')}**")
    lines.append(f"- pair 数量：{int(summary.get('pair_count', 0))}")
    lines.append(f"- 显式训练触发比例：{summary.get('explicit_train_trigger_ratio', 0.0):.3f}")
    lines.append(f"- source-visible 执行比例：{summary.get('source_visible_execution_ratio', 0.0):.3f}")
    lines.append(f"- runtime 回投比例：{summary.get('runtime_projection_ratio', 0.0):.3f}")
    lines.append(f"- probe runtime presence 比例：{summary.get('probe_runtime_presence_ratio', 0.0):.3f}")
    lines.append(f"- probe drive 优势比例：{summary.get('probe_drive_advantage_ratio', 0.0):.3f}")
    lines.append(f"- probe margin 优势比例：{summary.get('probe_margin_advantage_ratio', 0.0):.3f}")
    lines.append(f"- 完整闭环比例：{summary.get('clean_closure_chain_ratio', 0.0):.3f}")
    lines.append(f"- probe drive 优势均值：{summary.get('probe_drive_advantage_mean', 0.0):.4f}")
    lines.append(f"- probe margin 优势均值：{summary.get('probe_margin_advantage_mean', 0.0):.4f}")
    lines.append(f"- drive sign test p：{summary.get('probe_drive_advantage_sign_p', 1.0):.8f}")
    lines.append(f"- margin sign test p：{summary.get('probe_margin_advantage_sign_p', 1.0):.8f}")
    lines.append("")
    lines.append("## 运行参数")
    lines.append(f"- local reward coef：{reward_coef:.3f}")
    lines.append(f"- local punish coef：{punish_coef:.3f}")
    lines.append(f"- alias TTL：{alias_ttl}")
    lines.append("- drive_decay_ratio：0.0")
    lines.append("- action_fatigue_enabled：false")
    lines.append("- threshold_scale_by_rwd_pun_enabled：false")
    lines.append("")
    lines.append("## 判据解释")
    lines.append("")
    lines.append("本实验不要求后续弱天气 probe 直接跨过 weather_stub 阈值，也不把“是否已经形成完整天气策略”作为命题。")
    lines.append("正文只使用更窄的两段链条：")
    lines.append("")
    lines.append("1. 显式查询分支必须形成 source-visible 的原生行动完成与 runtime action-node 回投。")
    lines.append("2. 在同样的后续弱天气 probe 下，显式执行史分支必须比弱历史对照分支表现出更高的行动准备度。")
    lines.append("")
    lines.append("由于实验中把 `drive_decay_ratio` 设为 `0.0`，后续 probe 上的优势不能被解释为简单的前一 tick drive 残留。")
    lines.append("")
    lines.append("## 图表")
    lines.append("")
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    lines.append("## Pair 明细")
    lines.append("")
    lines.append("| case | rep | city | event | explicit buffer exec | runtime projection | explicit probe drive | weak probe drive | drive advantage | margin advantage | clean chain |")
    lines.append("| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in pair_rows:
        lines.append(
            f"| {row['case_id']} | {row['replicate']} | {row['city']} | {row['event']} | "
            f"{int(row.get('executed_buffer_executed_source_visible', 0))} | {int(row.get('executed_buffer_runtime_action_weather_executed', 0))} | "
            f"{num(row, 'executed_probe_drive'):.3f} | {num(row, 'weak_probe_drive'):.3f} | "
            f"{num(row, 'probe_drive_advantage'):.3f} | {num(row, 'probe_margin_advantage'):.3f} | "
            f"{int(row.get('supports_clean_closure_chain', 0))} |"
        )
    lines.append("")
    lines.append("## 附件统计")
    lines.append(f"- datasets: {len(datasets)}")
    lines.append(f"- runs: {len(run_infos)}")
    path = REPORT_DIR / f"E05_action_closure_report_{stamp}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def analyze(
    run_infos: list[dict[str, Any]],
    datasets: list[dict[str, Any]],
    stamp: str,
    *,
    reward_coef: float,
    punish_coef: float,
    alias_ttl: int,
) -> dict[str, Any]:
    row_metrics = build_row_metrics(run_infos)
    pair_rows = build_pair_rows(run_infos)
    summary = summarize_evidence(pair_rows)
    e01.write_csv(TABLE_DIR / f"e05_action_closure_row_metrics_{stamp}.csv", row_metrics)
    e01.write_csv(TABLE_DIR / f"e05_action_closure_pair_rows_{stamp}.csv", pair_rows)
    e01.write_json(TABLE_DIR / f"e05_action_closure_summary_{stamp}.json", summary)
    write_design_note(REPORT_DIR / "E05_action_closure_design_logic.md")
    charts = make_charts(pair_rows, stamp)
    copied = copy_run_artifacts(run_infos)
    report = write_report(
        pair_rows=pair_rows,
        summary=summary,
        charts=charts,
        datasets=datasets,
        run_infos=run_infos,
        stamp=stamp,
        reward_coef=reward_coef,
        punish_coef=punish_coef,
        alias_ttl=alias_ttl,
    )
    evidence = {
        "experiment": "E05_action_closure",
        "stamp": stamp,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "support_level": summary.get("support_level", ""),
        "summary": summary,
        "params": {
            "reward_coef": float(reward_coef),
            "punish_coef": float(punish_coef),
            "alias_ttl": int(alias_ttl),
            "drive_decay_ratio": 0.0,
            "action_fatigue_enabled": False,
            "threshold_scale_by_rwd_pun_enabled": False,
        },
        "datasets": [
            {
                **d,
                "artifact_path": str(d.get("artifact_path", "")),
                "imported_path": str(d.get("imported_path", "")),
            }
            for d in datasets
        ],
        "runs": [
            {
                "run_id": r["run_id"],
                "case_id": r["case_id"],
                "branch": r["branch"],
                "replicate": r["replicate"],
                "status": r.get("status", ""),
            }
            for r in run_infos
        ],
        "copied_runs": copied,
        "tables": {
            "row_metrics": str(TABLE_DIR / f"e05_action_closure_row_metrics_{stamp}.csv"),
            "pair_rows": str(TABLE_DIR / f"e05_action_closure_pair_rows_{stamp}.csv"),
            "summary": str(TABLE_DIR / f"e05_action_closure_summary_{stamp}.json"),
        },
        "charts": [str(path) for path in charts],
        "report": str(report),
        "design_note": str(REPORT_DIR / "E05_action_closure_design_logic.md"),
    }
    e01.write_json(MANIFEST_DIR / f"E05_action_closure_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E05_action_closure_latest.json", evidence)
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run paper E05 action-closure experiment.")
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument("--families", type=int, default=12)
    parser.add_argument("--reward-coef", type=float, default=0.90)
    parser.add_argument("--punish-coef", type=float, default=0.90)
    parser.add_argument("--alias-ttl", type=int, default=6)
    parser.add_argument("--max-ticks", type=int, default=0)
    parser.add_argument("--stamp", default="")
    args = parser.parse_args(argv)

    ensure_dirs()
    stamp = str(args.stamp or now_stamp())
    replicates = max(1, int(args.replicates))
    family_limit = max(1, int(args.families))
    reward_coef = max(0.0, float(args.reward_coef))
    punish_coef = max(0.0, float(args.punish_coef))
    alias_ttl = max(1, int(args.alias_ttl))
    max_ticks = int(args.max_ticks) if int(args.max_ticks) > 0 else None

    datasets = write_datasets(
        replicates=replicates,
        family_limit=family_limit,
        reward_coef=reward_coef,
        punish_coef=punish_coef,
        alias_ttl=alias_ttl,
    )
    print(f"[E05] generated {len(datasets)} datasets", flush=True)

    run_infos: list[dict[str, Any]] = []
    for dataset_info in datasets:
        run_infos.append(run_one_dataset(dataset_info, run_stamp=stamp, max_ticks=max_ticks))

    evidence = analyze(
        run_infos,
        datasets,
        stamp,
        reward_coef=reward_coef,
        punish_coef=punish_coef,
        alias_ttl=alias_ttl,
    )
    print(json.dumps({"ok": True, "stamp": stamp, "support": evidence["support_level"], "report": evidence["report"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
