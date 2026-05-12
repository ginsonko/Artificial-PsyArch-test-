# -*- coding: utf-8 -*-
"""E01 v4: minimal crossover probe experiment.

This version narrows E01 to the smallest causal claim we can test cleanly:
after a shared cold start, does prior exposure to one ordered context make the
same later probe cheaper than an alternative history that only exposes the
same characters in a different order?

The design is symmetric:

1. both conditions see the same cold_A;
2. treatment sees ordered_B while control sees permuted_B;
3. both conditions are then probed with ordered_B and permuted_B.

Thus the same probe text appears once as a "previously seen exact context" and
once as a "same characters but different prior order" comparison.  This avoids
the weakest objection to earlier designs: that one side may simply have had an
easier text regardless of history.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from _reproduction_paths import AP_ROOT, ARTIFACT_ROOT, ATTACHMENT_ROOT

if str(AP_ROOT) not in sys.path:
    sys.path.insert(0, str(AP_ROOT))

from observatory._app import ObservatoryApp
from observatory.experiment.io import sha256_file
from observatory.experiment.runner import RunOptions, run_dataset
from observatory.experiment.storage import DatasetFileRef, imported_datasets_dir, resolve_run_dir

import run_paper_e01_experiment as e01


E01_ROOT = ARTIFACT_ROOT / "E01_lexical_abstraction"
V4_ROOT = E01_ROOT / "strong_reuse_v4_crossover_probe"
DATASET_DIR = V4_ROOT / "datasets"
RUN_DIR = V4_ROOT / "runs"
TABLE_DIR = V4_ROOT / "tables"
CHART_DIR = V4_ROOT / "charts"
REPORT_DIR = V4_ROOT / "reports"
MANIFEST_DIR = V4_ROOT / "manifests"

CURRICULUM_VERSION = "e01_crossover_probe_v4"
LABEL_KEY = "paper_e01_crossover_probe"

PHASE_ORDER = {
    "cold_A": 0,
    "history_B": 1,
    "probe_ordered_B": 2,
    "probe_permuted_B": 3,
}

REUSE_KEYS = [
    "stimulus_owner_local_residual_raw_signature_hit_count",
    "stimulus_owner_local_residual_common_signature_hit_count",
    "stimulus_owner_local_residual_fuzzy_equivalent_signature_hit_count",
    "stimulus_owner_local_residual_raw_reinforce_count",
    "stimulus_owner_local_residual_common_reinforce_count",
    "stimulus_owner_local_residual_parent_common_reuse_count",
    "stimulus_owner_local_residual_common_entry_reinforce_count",
    "stimulus_owner_local_residual_common_structure_reuse_count",
]

NEW_PATH_KEYS = [
    "stimulus_owner_local_residual_raw_append_count",
    "stimulus_owner_local_residual_common_entry_append_count",
    "stimulus_owner_local_residual_common_structure_create_count",
]


def ensure_dirs() -> None:
    for path in (DATASET_DIR, RUN_DIR, TABLE_DIR, CHART_DIR, REPORT_DIR, MANIFEST_DIR, imported_datasets_dir()):
        path.mkdir(parents=True, exist_ok=True)


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def mean(values: list[float]) -> float:
    clean = [float(v) for v in values if math.isfinite(float(v))]
    return round(statistics.fmean(clean), 8) if clean else 0.0


def median(values: list[float]) -> float:
    clean = sorted(float(v) for v in values if math.isfinite(float(v)))
    if not clean:
        return 0.0
    mid = len(clean) // 2
    return round(clean[mid] if len(clean) % 2 else (clean[mid - 1] + clean[mid]) / 2.0, 8)


def safe_ratio(num: float, den: float) -> float:
    return round(float(num) / float(den), 8) if den else 0.0


def app_config_for_profile(profile: str) -> dict[str, Any]:
    base = {
        "input_chunking_enabled": False,
        "action_enabled": False,
        "sensor_enable_echo": False,
        "sensor_include_echoes_in_packet": False,
    }
    if profile == "baseline":
        return base
    if profile == "context_strict_probe":
        return {
            **base,
            "hdb_stimulus_level_max_rounds": 72,
            "hdb_stimulus_early_stop_patience_rounds": 5,
            "hdb_stimulus_object_projection_dominance_min_rounds": 14,
            "hdb_stimulus_anchor_existing_structure_bonus": 0.12,
            "hdb_stimulus_anchor_owner_residual_bonus": 1.65,
            "hdb_stimulus_anchor_left_to_right_bias_rounds": 4,
        }
    raise ValueError(f"unknown profile: {profile}")


def permute_context(context: str, variant: int) -> str:
    chars = list(str(context or ""))
    if len(chars) < 2:
        return str(context or "")
    if variant % 2 == 0:
        return "".join(reversed(chars))
    return "".join(chars[1:] + chars[:1])


def family_specs() -> list[dict[str, str]]:
    return [
        {"case_id": "F01", "context": "甲乙丙丁戊己", "a": "开始记录", "b": "复核表格"},
        {"case_id": "F02", "context": "庚辛壬癸子丑", "a": "安排复查", "b": "通知小林"},
        {"case_id": "F03", "context": "寅卯辰巳午未", "a": "发送小周", "b": "写入白板"},
        {"case_id": "F04", "context": "申酉戌亥天地", "a": "记录进度", "b": "提醒同伴"},
        {"case_id": "F05", "context": "山川湖海星月", "a": "标出差异", "b": "保存版本"},
        {"case_id": "F06", "context": "春夏秋冬风雨", "a": "定位来源", "b": "追加备注"},
    ]


def text_for(context: str, tail: str) -> str:
    return f"{context}{tail}"


def ordered_specs(*, family_count: int, replicate: int) -> list[dict[str, str]]:
    specs = family_specs()[: max(1, min(family_count, len(family_specs())))]
    shift = (max(1, replicate) - 1) % len(specs)
    return specs[shift:] + specs[:shift]


def build_records(condition: str, *, replicate: int, family_count: int, case_id: str = "") -> list[dict[str, Any]]:
    specs = ordered_specs(family_count=family_count, replicate=replicate)
    if case_id:
        specs = [spec for spec in specs if spec["case_id"] == case_id]
    rows: list[dict[str, Any]] = []
    for spec in specs:
        ordered_ctx = spec["context"]
        perm_ctx = permute_context(spec["context"], 2)
        ordered_b = text_for(ordered_ctx, spec["b"])
        perm_b = text_for(perm_ctx, spec["b"])
        if condition == "treatment":
            seq = [
                ("cold_A", "A0", text_for(ordered_ctx, spec["a"]), ordered_ctx, "A"),
                ("history_B", "B_hist", ordered_b, ordered_ctx, "B_ordered_history"),
                ("probe_ordered_B", "B_probe_ord", ordered_b, ordered_ctx, "B_ordered_probe"),
                ("probe_permuted_B", "B_probe_perm", perm_b, perm_ctx, "B_permuted_probe"),
            ]
        elif condition == "control":
            seq = [
                ("cold_A", "A0", text_for(ordered_ctx, spec["a"]), ordered_ctx, "A"),
                ("history_B", "B_hist", perm_b, perm_ctx, "B_permuted_history"),
                ("probe_ordered_B", "B_probe_ord", ordered_b, ordered_ctx, "B_ordered_probe"),
                ("probe_permuted_B", "B_probe_perm", perm_b, perm_ctx, "B_permuted_probe"),
            ]
        elif condition == "calibration":
            seq = [
                ("cold_A", "A0", text_for(ordered_ctx, spec["a"]), ordered_ctx, "A"),
                ("history_B", "B_hist", ordered_b, ordered_ctx, "B_ordered_history"),
                ("probe_ordered_B", "B_probe_ord1", ordered_b, ordered_ctx, "B_ordered_probe"),
                ("probe_ordered_B", "B_probe_ord2", ordered_b, ordered_ctx, "B_ordered_probe"),
            ]
        else:
            raise ValueError(f"unknown condition: {condition}")
        for local_index, (phase, step_id, text, actual_context, probe_kind) in enumerate(seq):
            rows.append(
                {
                    "condition": condition,
                    "replicate": replicate,
                    "case_id": spec["case_id"],
                    "phase": phase,
                    "step_id": step_id,
                    "local_index": local_index,
                    "text": text,
                    "text_len": len(text),
                    "expected_context": ordered_ctx,
                    "actual_context": actual_context,
                    "probe_kind": probe_kind,
                    "tail": text.replace(actual_context, "", 1),
                }
            )
    return rows


def dataset_doc(
    *,
    condition: str,
    replicate: int,
    family_count: int,
    profile: str,
    empty_repeat: int,
    case_id: str = "",
) -> dict[str, Any]:
    records = build_records(condition, replicate=replicate, family_count=family_count, case_id=case_id)
    ticks: list[dict[str, Any]] = []
    for source_index, record in enumerate(records):
        ticks.append(
            {
                "text": record["text"],
                "tags": [LABEL_KEY, "E01", "reuse_v4", condition, record["phase"], record["case_id"]],
                "labels": {
                    LABEL_KEY: {
                        **{k: v for k, v in record.items() if k != "text"},
                        "source_text_index": source_index,
                        "curriculum_version": CURRICULUM_VERSION,
                        "profile": profile,
                    }
                },
                "meta": {
                    "role": "user",
                    "kind": "message",
                    "phase": "e01_crossover_probe",
                    "pure_text": True,
                    "real_input_index": source_index,
                },
            }
        )
        for gap_index in range(max(0, int(empty_repeat))):
            ticks.append(
                {
                    "empty": True,
                    "tags": [LABEL_KEY, "E01", "idle_gap", condition],
                    "labels": {
                        LABEL_KEY: {
                            "condition": condition,
                            "replicate": replicate,
                            "phase": "idle_gap",
                            "after_source_text_index": source_index,
                            "gap_index": gap_index,
                            "curriculum_version": CURRICULUM_VERSION,
                            "profile": profile,
                        }
                    },
                }
            )
    family_part = f"_{case_id}" if case_id else f"_f{family_count}"
    dataset_id = f"paper_e01_crossover_{condition}{family_part}_r{replicate}_{profile}_v4"
    return {
        "dataset_id": dataset_id,
        "title": f"E01 v4 crossover probe - {condition} - r{replicate}",
        "description": "共享冷启动后，用交叉 probe 验证稳定顺序语境是否比同字符乱序历史更省新增存储。",
        "schema_version": "observatory.dataset.v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "time_basis": "tick",
        "tick_dt_ms": 3000,
        "seed": 2026051104 + int(replicate),
        "app_config_override": app_config_for_profile(profile),
        "meta": {
            "paper_experiment": "E01_crossover_probe",
            "curriculum_version": CURRICULUM_VERSION,
            "condition": condition,
            "replicate": replicate,
            "family_count": family_count,
            "case_id": case_id,
            "runtime_profile": profile,
            "evidence_goal": "the same probe should be cheaper after exact ordered history than after same-character permuted history",
        },
        "episodes": [
            {
                "id": f"paper_e01_crossover_{condition}_r{replicate}_main",
                "title": f"E01 crossover {condition} r{replicate}",
                "tags": [LABEL_KEY, "E01", "reuse_v4", condition],
                "repeat": 1,
                "ticks": ticks,
            }
        ],
    }


def write_datasets(
    *,
    conditions: list[str],
    replicates: int,
    family_count: int,
    profile: str,
    empty_repeat: int,
    separate_family_runs: bool,
) -> list[dict[str, Any]]:
    datasets: list[dict[str, Any]] = []
    for condition in conditions:
        for replicate in range(1, replicates + 1):
            case_ids = [spec["case_id"] for spec in ordered_specs(family_count=family_count, replicate=replicate)] if separate_family_runs else [""]
            for case_id in case_ids:
                doc = dataset_doc(
                    condition=condition,
                    replicate=replicate,
                    family_count=family_count,
                    profile=profile,
                    empty_repeat=empty_repeat,
                    case_id=case_id,
                )
                name = f"{doc['dataset_id']}.yaml"
                text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
                artifact_path = DATASET_DIR / name
                imported_path = imported_datasets_dir() / name
                artifact_path.write_text(text, encoding="utf-8")
                imported_path.write_text(text, encoding="utf-8")
                records = build_records(condition, replicate=replicate, family_count=family_count, case_id=case_id)
                run_slug = f"{condition}_{case_id or ('f' + str(family_count))}_r{replicate}_{profile}"
                datasets.append(
                    {
                        "condition": condition,
                        "replicate": replicate,
                        "case_id": case_id,
                        "dataset_id": doc["dataset_id"],
                        "dataset_name": name,
                        "run_slug": run_slug,
                        "artifact_path": artifact_path,
                        "imported_path": imported_path,
                        "sha256": sha256_file(imported_path),
                        "source_text_ticks": len(records),
                        "total_source_ticks": len(doc["episodes"][0]["ticks"]),
                        "profile": profile,
                        "family_count": family_count,
                    }
                )
    return datasets


def quiet_progress(payload: dict[str, Any]) -> None:
    stage = str(payload.get("stage", "") or "")
    if stage in {"loading_dataset", "resetting_runtime", "running_tick", "finished", "failed"}:
        done = payload.get("source_tick_done", payload.get("tick_done", ""))
        planned = payload.get("tick_planned", "")
        if stage == "running_tick" and done not in {0, "", None}:
            print(f"[E01-v4] {stage}: {done}/{planned}", flush=True)


def run_one_dataset(dataset_info: dict[str, Any], *, run_stamp: str, max_ticks: int | None) -> dict[str, Any]:
    condition = str(dataset_info["condition"])
    replicate = int(dataset_info["replicate"])
    profile = str(dataset_info.get("profile") or "baseline")
    run_slug = str(dataset_info.get("run_slug") or f"{condition}_r{replicate}_{profile}")
    run_id = f"paper_e01_crossover_{run_slug}_{run_stamp}"
    print(f"[E01-v4] start run_id={run_id}", flush=True)
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
    out = {
        **dataset_info,
        "run_id": run_id,
        "run_dir": run_dir,
        "manifest": manifest,
        "success": bool(result.get("success", False)),
        "status": manifest.get("status", ""),
    }
    print(f"[E01-v4] finished run_id={run_id} status={out['status']}", flush=True)
    return out


def copy_run_artifacts(run_infos: list[dict[str, Any]]) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    for info in run_infos:
        run_id = str(info["run_id"])
        src_dir = Path(info["run_dir"])
        dest = RUN_DIR / run_id
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("manifest.json", "dataset.normalized.yaml", "dataset.source.yaml", "runner_timing.jsonl"):
            src = src_dir / name
            if src.exists():
                shutil.copy2(src, dest / name)
        for src in src_dir.glob("metrics*.jsonl*"):
            if src.exists():
                shutil.copy2(src, dest / src.name)
        copied.append({"run_id": run_id, "artifact_dir": str(dest)})
    return copied


def build_row_metrics(run_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for info in run_infos:
        prev_structure = 0.0
        prev_residual = 0.0
        seen_targets_by_case: dict[str, set[str]] = defaultdict(set)
        for row in e01.read_metrics_rows_from_run_dir(Path(info["run_dir"])):
            labels = row.get("labels", {}).get(LABEL_KEY, {}) if isinstance(row.get("labels"), dict) else {}
            if bool(row.get("input_is_empty", False)) or labels.get("phase") == "idle_gap":
                continue
            phase = str(labels.get("phase", "") or "")
            case_id = str(labels.get("case_id", "") or "")
            target_id = str(row.get("stimulus_best_match_target_id", "") or "")
            hdb_structure = e01._numeric(row, "hdb_structure_count")
            hdb_residual = e01._numeric(row, "hdb_residual_diff_entry_count")
            structure_delta = max(0.0, hdb_structure - prev_structure)
            residual_delta = max(0.0, hdb_residual - prev_residual)
            prev_structure = hdb_structure
            prev_residual = hdb_residual
            text_len = max(1.0, float(labels.get("text_len") or e01._numeric(row, "input_len") or 1.0))
            reuse_signal = sum(e01._numeric(row, key) for key in REUSE_KEYS)
            new_path_signal = sum(e01._numeric(row, key) for key in NEW_PATH_KEYS)
            target_seen_before = 1.0 if target_id and target_id in seen_targets_by_case[case_id] else 0.0
            if target_id:
                seen_targets_by_case[case_id].add(target_id)
            storage_cost = structure_delta + residual_delta
            rows.append(
                {
                    "run_id": info["run_id"],
                    "condition": labels.get("condition", info.get("condition", "")),
                    "replicate": int(labels.get("replicate", info.get("replicate", 0)) or 0),
                    "case_id": case_id,
                    "phase": phase,
                    "phase_order": PHASE_ORDER.get(phase, 99),
                    "step_id": labels.get("step_id", ""),
                    "probe_kind": labels.get("probe_kind", ""),
                    "input_text_preview": row.get("input_text_preview", ""),
                    "expected_context": labels.get("expected_context", ""),
                    "actual_context": labels.get("actual_context", ""),
                    "tail": labels.get("tail", ""),
                    "input_len": text_len,
                    "stimulus_best_match_target_id": target_id,
                    "target_seen_before": target_seen_before,
                    "stimulus_best_match_score": e01._numeric(row, "stimulus_best_match_score"),
                    "stimulus_match_v2_context_support_mean": e01._numeric(row, "stimulus_match_v2_context_support_mean"),
                    "stimulus_match_v2_order_alignment_mean": e01._numeric(row, "stimulus_match_v2_order_alignment_mean"),
                    "stimulus_match_v2_structure_inclusion_mean": e01._numeric(row, "stimulus_match_v2_structure_inclusion_mean"),
                    "stimulus_match_v2_energy_profile_mean": e01._numeric(row, "stimulus_match_v2_energy_profile_mean"),
                    "stimulus_residual_ratio": e01._numeric(row, "stimulus_residual_ratio"),
                    "stimulus_round_count": e01._numeric(row, "stimulus_round_count"),
                    "stimulus_final_residual_total": e01._numeric(row, "stimulus_final_residual_total"),
                    "structure_delta": structure_delta,
                    "residual_delta": residual_delta,
                    "storage_cost": storage_cost,
                    "storage_cost_per_char": safe_ratio(storage_cost, text_len),
                    "reuse_signal_count": reuse_signal,
                    "new_path_count": new_path_signal,
                    "pool_cp_top1_cp": e01._numeric(row, "pool_cp_top1_cp"),
                    "pool_ev_top1_ev": e01._numeric(row, "pool_ev_top1_ev"),
                    "mechanism_positive": 1.0 if reuse_signal > 0 else 0.0,
                    **{key: e01._numeric(row, key) for key in REUSE_KEYS + NEW_PATH_KEYS if key in row},
                }
            )
    return rows


def summarize_phase(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["condition"]), str(row["phase"]))].append(row)
    metrics = [
        "storage_cost_per_char",
        "stimulus_best_match_score",
        "reuse_signal_count",
        "new_path_count",
        "stimulus_match_v2_context_support_mean",
        "stimulus_match_v2_order_alignment_mean",
        "pool_cp_top1_cp",
        "pool_ev_top1_ev",
        "mechanism_positive",
    ]
    out: list[dict[str, Any]] = []
    for (condition, phase), group in sorted(groups.items(), key=lambda kv: (kv[0][0], PHASE_ORDER.get(kv[0][1], 99))):
        rec: dict[str, Any] = {"condition": condition, "phase": phase, "n": len(group)}
        for key in metrics:
            vals = [float(row.get(key, 0.0) or 0.0) for row in group]
            rec[f"{key}_mean"] = mean(vals)
            rec[f"{key}_median"] = median(vals)
            rec[f"{key}_sum"] = round(sum(vals), 8)
        out.append(rec)
    return out


def family_phase_map(rows: list[dict[str, Any]], *, condition: str) -> dict[tuple[int, str], dict[str, dict[str, Any]]]:
    out: dict[tuple[int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if str(row.get("condition")) != condition:
            continue
        out[(int(row.get("replicate", 0) or 0), str(row.get("case_id", "")))][str(row.get("phase", ""))] = row
    return out


def compare_families(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    treatment = family_phase_map(rows, condition="treatment")
    control = family_phase_map(rows, condition="control")
    out: list[dict[str, Any]] = []
    for key, treat_phases in sorted(treatment.items()):
        ctrl_phases = control.get(key, {})
        if not treat_phases or not ctrl_phases:
            continue
        cold_t = float(treat_phases.get("cold_A", {}).get("storage_cost_per_char", 0.0) or 0.0)
        cold_c = float(ctrl_phases.get("cold_A", {}).get("storage_cost_per_char", 0.0) or 0.0)
        ord_t = treat_phases.get("probe_ordered_B", {})
        ord_c = ctrl_phases.get("probe_ordered_B", {})
        perm_t = treat_phases.get("probe_permuted_B", {})
        perm_c = ctrl_phases.get("probe_permuted_B", {})
        ord_t_storage = float(ord_t.get("storage_cost_per_char", 0.0) or 0.0)
        ord_c_storage = float(ord_c.get("storage_cost_per_char", 0.0) or 0.0)
        perm_t_storage = float(perm_t.get("storage_cost_per_char", 0.0) or 0.0)
        perm_c_storage = float(perm_c.get("storage_cost_per_char", 0.0) or 0.0)
        ord_t_match = float(ord_t.get("stimulus_best_match_score", 0.0) or 0.0)
        ord_c_match = float(ord_c.get("stimulus_best_match_score", 0.0) or 0.0)
        perm_t_match = float(perm_t.get("stimulus_best_match_score", 0.0) or 0.0)
        perm_c_match = float(perm_c.get("stimulus_best_match_score", 0.0) or 0.0)
        ord_t_path = float(ord_t.get("new_path_count", 0.0) or 0.0)
        ord_c_path = float(ord_c.get("new_path_count", 0.0) or 0.0)
        perm_t_path = float(perm_t.get("new_path_count", 0.0) or 0.0)
        perm_c_path = float(perm_c.get("new_path_count", 0.0) or 0.0)
        out.append(
            {
                "replicate": key[0],
                "case_id": key[1],
                "cold_abs_diff": abs(cold_t - cold_c),
                "ordered_probe_storage_treatment": ord_t_storage,
                "ordered_probe_storage_control": ord_c_storage,
                "ordered_probe_advantage": round(ord_c_storage - ord_t_storage, 8),
                "ordered_probe_match_diff": round(ord_t_match - ord_c_match, 8),
                "ordered_probe_reuse_advantage": round(float(ord_t.get("reuse_signal_count", 0.0) or 0.0) - float(ord_c.get("reuse_signal_count", 0.0) or 0.0), 8),
                "ordered_probe_path_advantage": round(ord_c_path - ord_t_path, 8),
                "ordered_probe_context_support_advantage": round(float(ord_t.get("stimulus_match_v2_context_support_mean", 0.0) or 0.0) - float(ord_c.get("stimulus_match_v2_context_support_mean", 0.0) or 0.0), 8),
                "permuted_probe_storage_treatment": perm_t_storage,
                "permuted_probe_storage_control": perm_c_storage,
                "permuted_probe_advantage": round(perm_t_storage - perm_c_storage, 8),
                "permuted_probe_match_diff": round(perm_c_match - perm_t_match, 8),
                "permuted_probe_reuse_advantage": round(float(perm_c.get("reuse_signal_count", 0.0) or 0.0) - float(perm_t.get("reuse_signal_count", 0.0) or 0.0), 8),
                "permuted_probe_path_advantage": round(perm_t_path - perm_c_path, 8),
                "treatment_match_preference": round(perm_t_storage - ord_t_storage, 8),
                "control_match_preference": round(ord_c_storage - perm_c_storage, 8),
                "pass_cold_equal": int(abs(cold_t - cold_c) <= 0.05),
                "pass_ordered_probe": int(
                    (ord_c_storage - ord_t_storage) >= 0.20
                    and (ord_t_match - ord_c_match) >= -0.03
                ),
                "pass_permuted_probe": int(
                    (perm_t_storage - perm_c_storage) >= 0.20
                    and (perm_c_match - perm_t_match) >= -0.03
                ),
                "pass_history_specificity": int((perm_t_storage - ord_t_storage) >= 0.20 and (ord_c_storage - perm_c_storage) >= 0.20),
                "pass_mechanism": int(
                    ((ord_c_path - ord_t_path) >= 2.0 and (perm_t_path - perm_c_path) >= 2.0)
                    or ((ord_c_storage - ord_t_storage) >= 0.20 and (perm_t_storage - perm_c_storage) >= 0.20 and (perm_t_storage - ord_t_storage) >= 0.20 and (ord_c_storage - perm_c_storage) >= 0.20)
                ),
            }
        )
    return out


def summarize_family_evidence(family_rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(family_rows)
    if not n:
        return {"n": 0, "support_level": "no_data"}
    summary = {
        "n": n,
        "ordered_probe_advantage_mean": mean([float(r["ordered_probe_advantage"]) for r in family_rows]),
        "ordered_probe_match_diff_mean": mean([float(r["ordered_probe_match_diff"]) for r in family_rows]),
        "ordered_probe_reuse_advantage_mean": mean([float(r["ordered_probe_reuse_advantage"]) for r in family_rows]),
        "ordered_probe_path_advantage_mean": mean([float(r["ordered_probe_path_advantage"]) for r in family_rows]),
        "permuted_probe_advantage_mean": mean([float(r["permuted_probe_advantage"]) for r in family_rows]),
        "permuted_probe_match_diff_mean": mean([float(r["permuted_probe_match_diff"]) for r in family_rows]),
        "permuted_probe_reuse_advantage_mean": mean([float(r["permuted_probe_reuse_advantage"]) for r in family_rows]),
        "permuted_probe_path_advantage_mean": mean([float(r["permuted_probe_path_advantage"]) for r in family_rows]),
        "ordered_probe_context_support_advantage_mean": mean([float(r["ordered_probe_context_support_advantage"]) for r in family_rows]),
        "treatment_match_preference_mean": mean([float(r["treatment_match_preference"]) for r in family_rows]),
        "control_match_preference_mean": mean([float(r["control_match_preference"]) for r in family_rows]),
        "cold_abs_diff_mean": mean([float(r["cold_abs_diff"]) for r in family_rows]),
    }
    for key in ("pass_cold_equal", "pass_ordered_probe", "pass_permuted_probe", "pass_history_specificity", "pass_mechanism"):
        count = sum(int(r.get(key, 0) or 0) for r in family_rows)
        summary[f"{key}_count"] = count
        summary[f"{key}_rate"] = safe_ratio(count, n)
    strong = (
        summary["pass_cold_equal_rate"] >= 0.90
        and summary["pass_ordered_probe_rate"] >= 0.80
        and summary["pass_permuted_probe_rate"] >= 0.80
        and summary["pass_history_specificity_rate"] >= 0.80
        and summary["pass_mechanism_rate"] >= 0.60
    )
    useful = (
        summary["pass_cold_equal_rate"] >= 0.90
        and summary["ordered_probe_advantage_mean"] > 0.0
        and summary["permuted_probe_advantage_mean"] > 0.0
    )
    summary["support_level"] = "strong_evidence" if strong else "useful_but_not_strong" if useful else "not_supported"
    return summary


def make_charts(rows: list[dict[str, Any]], family_rows: list[dict[str, Any]], stamp: str) -> list[Path]:
    if not rows:
        return []
    plt = e01.setup_matplotlib()
    paths: list[Path] = []
    phase_names = [phase for phase in PHASE_ORDER if any(r.get("phase") == phase for r in rows)]
    condition_colors = {"treatment": "#2563eb", "control": "#dc2626", "calibration": "#059669"}
    condition_labels = {"treatment": "有序历史", "control": "乱序历史", "calibration": "精确重复校准"}

    fig, axes = plt.subplots(2, 2, figsize=(12.0, 7.2), dpi=160)
    metrics = [
        ("storage_cost_per_char", "新增存储/字"),
        ("stimulus_best_match_score", "最佳匹配分"),
        ("reuse_signal_count", "复用链路信号"),
        ("stimulus_match_v2_context_support_mean", "语境支持均值"),
    ]
    for ax, (metric, title) in zip(axes.flatten(), metrics):
        for condition in ("treatment", "control", "calibration"):
            vals = []
            for phase in phase_names:
                phase_vals = [float(r.get(metric, 0.0) or 0.0) for r in rows if str(r.get("condition")) == condition and str(r.get("phase")) == phase]
                vals.append(mean(phase_vals))
            ax.plot(list(range(len(phase_names))), vals, marker="o", linewidth=2.0, color=condition_colors.get(condition, "#333333"), label=condition_labels.get(condition, condition))
        ax.set_title(title)
        ax.set_xticks(list(range(len(phase_names))))
        ax.set_xticklabels(phase_names, rotation=22, ha="right")
        ax.grid(True, alpha=0.24)
    axes[0][0].legend(loc="best")
    fig.suptitle("E01 v4 最小强证据实验：阶段曲线")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    phase_path = CHART_DIR / f"e01_v4_crossover_phase_curves_{stamp}.png"
    fig.savefig(phase_path)
    plt.close(fig)
    paths.append(phase_path)

    if family_rows:
        labels = [f"{row['replicate']}-{row['case_id']}" for row in family_rows]
        x = list(range(len(labels)))
        fig, ax = plt.subplots(figsize=(12.0, 4.8), dpi=160)
        ax.axhline(0, color="#111827", linewidth=1.0, alpha=0.75)
        ax.bar(x, [float(r["ordered_probe_advantage"]) for r in family_rows], color="#2563eb", alpha=0.82, label="有序 probe 优势")
        ax.plot(x, [float(r["permuted_probe_advantage"]) for r in family_rows], color="#dc2626", marker="o", label="乱序 probe 优势")
        ax.set_title("E01 v4：逐家族交叉 probe 效果")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        ax.grid(axis="y", alpha=0.24)
        ax.legend(loc="best")
        fig.tight_layout()
        family_path = CHART_DIR / f"e01_v4_crossover_family_effects_{stamp}.png"
        fig.savefig(family_path)
        plt.close(fig)
        paths.append(family_path)
    return paths


def write_design_note(path: Path) -> None:
    lines = [
        "# E01 v4 最小交叉 probe 实验设计说明\n\n",
        "## 证明目标\n\n",
        "本实验验证一个更小、更干净的因果命题：在共享冷启动后，同一条 probe 文本，如果此前已经以完全相同的有序语境出现过，应当比此前只出现过同字符乱序版本时更省新增存储，并且匹配质量不下降。\n\n",
        "## 设计优势\n\n",
        "1. 冷启动相同：两组首条输入完全一致。\n",
        "2. probe 相同：关键对比使用同一条 probe 文本，而不是不同文本之间的横向比较。\n",
        "3. 历史不同：唯一改变的是历史第二条输入是有序 B 还是乱序 B。\n",
        "4. 反向 probe：随后再用乱序 B 反向 probe，可检查优势是否真来自历史特异性，而不是任意重复都会降成本。\n\n",
        "## 判据\n\n",
        "强证据需要同时满足：共享冷启动可比；有序 probe 在 treatment 中比 control 更省新增存储；乱序 probe 在 control 中比 treatment 更省新增存储；两组内部都更偏向各自历史已见的 probe；并且至少一条机制链路支持这种历史特异性。\n",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def write_report(
    *,
    phase_summary: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    evidence_summary: dict[str, Any],
    chart_paths: list[Path],
    run_infos: list[dict[str, Any]],
    datasets: list[dict[str, Any]],
    stamp: str,
    profile: str,
) -> Path:
    lines: list[str] = []
    lines.append("# E01 v4 最小强证据实验报告\n\n")
    lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"- 批次标识：`{stamp}`\n")
    lines.append(f"- 运行参数档：`{profile}`\n")
    lines.append(f"- 判定：`{evidence_summary.get('support_level', 'unknown')}`\n")
    lines.append(f"- 家族样本数：{evidence_summary.get('n', 0)}\n\n")
    lines.append("## 设计逻辑\n\n")
    lines.append("本实验使用交叉 probe，而不是直接拿两条不同文本做比较。共享冷启动后，两组只在历史第二条输入不同：一组见过有序 B，另一组见过乱序 B。后续把同一条有序 B probe 同时喂给两组，因此任何差异都更容易解释为历史路径差异，而不是文本本身难度差异。\n\n")
    lines.append("## 数据集与运行\n\n")
    lines.append("| 条件 | 家族 | 重复 | dataset_id | sha256 | run_id | 状态 | 文本 tick |\n")
    lines.append("|---|---|---:|---|---|---|---|---:|\n")
    for ds in datasets:
        match = next((info for info in run_infos if info["condition"] == ds["condition"] and int(info["replicate"]) == int(ds["replicate"]) and str(info.get("case_id", "")) == str(ds.get("case_id", ""))), {})
        lines.append(f"| {ds['condition']} | {ds.get('case_id', '') or 'all'} | {ds['replicate']} | `{ds['dataset_id']}` | `{ds['sha256'][:12]}...` | `{match.get('run_id', '')}` | {match.get('status', '')} | {ds['source_text_ticks']} |\n")

    lines.append("\n## 阶段均值\n\n")
    lines.append("| 条件 | 阶段 | n | 新增存储/字 | 匹配分 | 复用信号 | 新路径 | 语境支持 | 机制阳性率 |\n")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|\n")
    for row in phase_summary:
        lines.append(
            f"| {row['condition']} | {row['phase']} | {row['n']} | "
            f"{float(row.get('storage_cost_per_char_mean', 0.0)):.4f} | "
            f"{float(row.get('stimulus_best_match_score_mean', 0.0)):.4f} | "
            f"{float(row.get('reuse_signal_count_mean', 0.0)):.4f} | "
            f"{float(row.get('new_path_count_mean', 0.0)):.4f} | "
            f"{float(row.get('stimulus_match_v2_context_support_mean_mean', 0.0)):.4f} | "
            f"{float(row.get('mechanism_positive_mean', 0.0)):.4f} |\n"
        )

    lines.append("\n## 逐家族判定\n\n")
    lines.append("| 重复 | 家族 | 冷启动差 | 有序 probe 优势 | 乱序 probe 优势 | treatment 历史偏好 | control 历史偏好 | 机制优势 | 通过项 |\n")
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---|\n")
    for row in family_rows:
        passes = ",".join(key.replace("pass_", "") for key in ("pass_cold_equal", "pass_ordered_probe", "pass_history_specificity", "pass_mechanism") if int(row.get(key, 0) or 0))
        lines.append(
            f"| {row['replicate']} | {row['case_id']} | "
            f"{float(row.get('cold_abs_diff', 0.0)):.4f} | "
            f"{float(row.get('ordered_probe_advantage', 0.0)):.4f} | "
            f"{float(row.get('permuted_probe_advantage', 0.0)):.4f} | "
            f"{float(row.get('treatment_match_preference', 0.0)):.4f} | "
            f"{float(row.get('control_match_preference', 0.0)):.4f} | "
            f"{float(row.get('ordered_probe_path_advantage', 0.0)):.4f} | {passes or '-'} |\n"
        )

    lines.append("\n## 汇总结论\n\n")
    lines.append(f"- 冷启动可比通过率：{float(evidence_summary.get('pass_cold_equal_rate', 0.0)):.4f}。\n")
    lines.append(f"- 有序 probe 优势通过率：{float(evidence_summary.get('pass_ordered_probe_rate', 0.0)):.4f}；平均优势：{float(evidence_summary.get('ordered_probe_advantage_mean', 0.0)):.4f}。\n")
    lines.append(f"- 乱序 probe 优势通过率：{float(evidence_summary.get('pass_permuted_probe_rate', 0.0)):.4f}；平均优势：{float(evidence_summary.get('permuted_probe_advantage_mean', 0.0)):.4f}。\n")
    lines.append(f"- 历史特异性通过率：{float(evidence_summary.get('pass_history_specificity_rate', 0.0)):.4f}；treatment 内历史偏好：{float(evidence_summary.get('treatment_match_preference_mean', 0.0)):.4f}；control 内历史偏好：{float(evidence_summary.get('control_match_preference_mean', 0.0)):.4f}。\n")
    lines.append(f"- 机制通过率：{float(evidence_summary.get('pass_mechanism_rate', 0.0)):.4f}；平均有序 probe 路径优势：{float(evidence_summary.get('ordered_probe_path_advantage_mean', 0.0)):.4f}；平均乱序 probe 路径优势：{float(evidence_summary.get('permuted_probe_path_advantage_mean', 0.0)):.4f}。\n\n")
    lines.append("## 附件\n\n")
    for path in chart_paths:
        lines.append(f"- `{path.relative_to(ATTACHMENT_ROOT)}`\n")
    for name in (
        f"e01_v4_crossover_row_metrics_{stamp}.csv",
        f"e01_v4_crossover_phase_summary_{stamp}.csv",
        f"e01_v4_crossover_family_evidence_{stamp}.csv",
    ):
        lines.append(f"- `{(TABLE_DIR / name).relative_to(ATTACHMENT_ROOT)}`\n")
    lines.append(f"- `{(REPORT_DIR / 'E01_v4_crossover_design_logic.md').relative_to(ATTACHMENT_ROOT)}`\n")
    path = REPORT_DIR / f"E01_v4_crossover_report_{stamp}.md"
    path.write_text("".join(lines), encoding="utf-8")
    return path


def analyze(run_infos: list[dict[str, Any]], datasets: list[dict[str, Any]], stamp: str, profile: str) -> dict[str, Any]:
    rows = build_row_metrics(run_infos)
    phase_summary = summarize_phase(rows)
    family_rows = compare_families(rows)
    evidence_summary = summarize_family_evidence(family_rows)
    charts = make_charts(rows, family_rows, stamp)

    e01.write_csv(TABLE_DIR / f"e01_v4_crossover_row_metrics_{stamp}.csv", rows)
    e01.write_csv(TABLE_DIR / f"e01_v4_crossover_phase_summary_{stamp}.csv", phase_summary)
    e01.write_csv(TABLE_DIR / f"e01_v4_crossover_family_evidence_{stamp}.csv", family_rows)
    e01.write_json(TABLE_DIR / f"e01_v4_crossover_evidence_summary_{stamp}.json", evidence_summary)
    write_design_note(REPORT_DIR / "E01_v4_crossover_design_logic.md")
    copied = copy_run_artifacts(run_infos)
    report = write_report(
        phase_summary=phase_summary,
        family_rows=family_rows,
        evidence_summary=evidence_summary,
        chart_paths=charts,
        run_infos=run_infos,
        datasets=datasets,
        stamp=stamp,
        profile=profile,
    )
    evidence = {
        "experiment": "E01_v4_crossover_probe",
        "stamp": stamp,
        "profile": profile,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "support_level": evidence_summary.get("support_level", ""),
        "evidence_summary": evidence_summary,
        "datasets": [{"condition": d["condition"], "replicate": d["replicate"], "dataset_id": d["dataset_id"], "sha256": d["sha256"], "artifact_path": str(d["artifact_path"])} for d in datasets],
        "runs": [{"condition": r["condition"], "replicate": r["replicate"], "run_id": r["run_id"], "status": r.get("status", ""), "dataset_sha256": r.get("sha256", "")} for r in run_infos],
        "copied_runs": copied,
        "tables": {
            "row_metrics": str(TABLE_DIR / f"e01_v4_crossover_row_metrics_{stamp}.csv"),
            "phase_summary": str(TABLE_DIR / f"e01_v4_crossover_phase_summary_{stamp}.csv"),
            "family_evidence": str(TABLE_DIR / f"e01_v4_crossover_family_evidence_{stamp}.csv"),
            "evidence_summary": str(TABLE_DIR / f"e01_v4_crossover_evidence_summary_{stamp}.json"),
        },
        "charts": [str(path) for path in charts],
        "report": str(report),
        "design_note": str(REPORT_DIR / "E01_v4_crossover_design_logic.md"),
    }
    e01.write_json(MANIFEST_DIR / f"E01_v4_crossover_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E01_v4_crossover_latest.json", evidence)
    return evidence


def parse_conditions(raw: str) -> list[str]:
    allowed = {"treatment", "control", "calibration"}
    parts = [part.strip() for part in str(raw or "").split(",") if part.strip()]
    if not parts:
        return ["treatment", "control", "calibration"]
    unknown = [part for part in parts if part not in allowed]
    if unknown:
        raise ValueError(f"unknown conditions: {unknown}")
    return parts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run E01 v4 crossover-probe experiment.")
    parser.add_argument("--replicates", type=int, default=2)
    parser.add_argument("--families", type=int, default=6)
    parser.add_argument("--empty-repeat", type=int, default=0)
    parser.add_argument("--profile", choices=["baseline", "context_strict_probe"], default="context_strict_probe")
    parser.add_argument("--conditions", default="treatment,control,calibration")
    parser.add_argument("--combined-family-runs", action="store_true", help="Run all families in one dataset per condition.")
    parser.add_argument("--max-ticks", type=int, default=0)
    parser.add_argument("--make-only", action="store_true")
    parser.add_argument("--analyze-existing-stamp", default="")
    parser.add_argument("--stamp", default="")
    args = parser.parse_args(argv)

    ensure_dirs()
    stamp = str(args.stamp or now_stamp())
    conditions = parse_conditions(args.conditions)
    family_count = max(1, min(int(args.families), len(family_specs())))
    replicates = max(1, int(args.replicates))
    empty_repeat = max(0, int(args.empty_repeat))
    profile = str(args.profile)
    datasets = write_datasets(
        conditions=conditions,
        replicates=replicates,
        family_count=family_count,
        profile=profile,
        empty_repeat=empty_repeat,
        separate_family_runs=not bool(args.combined_family_runs),
    )
    e01.write_json(
        MANIFEST_DIR / f"E01_v4_crossover_dataset_manifest_{stamp}.json",
        {
            "stamp": stamp,
            "curriculum_version": CURRICULUM_VERSION,
            "replicates": replicates,
            "family_count": family_count,
            "empty_repeat": empty_repeat,
            "profile": profile,
            "conditions": conditions,
            "datasets": [
                {
                    "condition": d["condition"],
                    "replicate": d["replicate"],
                    "case_id": d.get("case_id", ""),
                    "dataset_id": d["dataset_id"],
                    "dataset_name": d["dataset_name"],
                    "run_slug": d["run_slug"],
                    "sha256": d["sha256"],
                    "artifact_path": str(d["artifact_path"]),
                    "source_text_ticks": d["source_text_ticks"],
                    "total_source_ticks": d["total_source_ticks"],
                }
                for d in datasets
            ],
        },
    )
    print(f"[E01-v4] generated {len(datasets)} datasets under {DATASET_DIR}", flush=True)
    if args.make_only:
        return 0

    max_ticks = int(args.max_ticks) if int(args.max_ticks or 0) > 0 else None
    run_infos: list[dict[str, Any]] = []
    analyze_existing_stamp = str(args.analyze_existing_stamp or "").strip()
    if analyze_existing_stamp:
        stamp = analyze_existing_stamp
        for d in datasets:
            run_id = f"paper_e01_crossover_{d['run_slug']}_{stamp}"
            run_dir = resolve_run_dir(run_id)
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
            run_infos.append({**d, "run_id": run_id, "run_dir": run_dir, "manifest": manifest, "status": manifest.get("status", "")})
    else:
        for d in datasets:
            run_infos.append(run_one_dataset(d, run_stamp=stamp, max_ticks=max_ticks))

    evidence = analyze(run_infos, datasets, stamp, profile)
    print(json.dumps({"ok": True, "stamp": stamp, "support": evidence["support_level"], "report": evidence["report"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
