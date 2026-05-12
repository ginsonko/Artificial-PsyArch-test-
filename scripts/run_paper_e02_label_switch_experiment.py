# -*- coding: utf-8 -*-
"""Run paper E02 label-switch sensitivity experiment.

Current E02 claim
-----------------
Under a stable sentence shell, replacing only the label on the second sentence
should increase AP's structure-growth cost relative to exact repetition.

This experiment deliberately tests a smaller and cleaner proposition than the
older "novelty -> familiarity/deja_vu" story. In the current default runtime,
first encounter already tends to produce runtime memory projection, so the most
robust paper-facing claim is the local growth-cost effect under tightly matched
sentence shells.
"""

from __future__ import annotations

import argparse
import json
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
from observatory._app import ObservatoryApp
from observatory.experiment.io import sha256_file
from observatory.experiment.runner import RunOptions, run_dataset
from observatory.experiment.storage import DatasetFileRef, imported_datasets_dir, resolve_run_dir


E02_ROOT = ARTIFACT_ROOT / "E02_label_switch_sensitivity"
DATASET_DIR = E02_ROOT / "datasets"
RUN_DIR = E02_ROOT / "runs"
TABLE_DIR = E02_ROOT / "tables"
CHART_DIR = E02_ROOT / "charts"
REPORT_DIR = E02_ROOT / "reports"
MANIFEST_DIR = E02_ROOT / "manifests"

LABEL_KEY = "paper_e02_label_switch"
CURRICULUM_VERSION = "paper_e02_v2_label_switch"

PRIMARY_FAMILY_SPECS: list[dict[str, str]] = [
    {"case_id": "F01", "template": "请先登记代号{label}。", "label_a": "云栈", "label_b": "岚钥"},
    {"case_id": "F02", "template": "请立即核对编号{label}。", "label_a": "星阈", "label_b": "青枢"},
    {"case_id": "F03", "template": "现在标记对象{label}。", "label_a": "霜函", "label_b": "石岚"},
    {"case_id": "F04", "template": "请记录标签{label}。", "label_a": "澄桁", "label_b": "炘笺"},
    {"case_id": "F05", "template": "请更新条目{label}。", "label_a": "川钥", "label_b": "禾阈"},
    {"case_id": "F06", "template": "请确认样本{label}。", "label_a": "岚册", "label_b": "青牒"},
    {"case_id": "F07", "template": "请整理项目{label}。", "label_a": "曜签", "label_b": "芒栈"},
    {"case_id": "F08", "template": "请备注节点{label}。", "label_a": "衡岚", "label_b": "舟钥"},
    {"case_id": "F09", "template": "请核验令牌{label}。", "label_a": "辰简", "label_b": "陌钥"},
    {"case_id": "F10", "template": "现在登记项目{label}。", "label_a": "溪策", "label_b": "峤函"},
    {"case_id": "F11", "template": "请锁定样例{label}。", "label_a": "原笺", "label_b": "霁钥"},
    {"case_id": "F12", "template": "请回填标识{label}。", "label_a": "禾岚", "label_b": "镜阈"},
]
HOLDOUT_LONG_SHELL_FAMILY_SPECS: list[dict[str, str]] = [
    {"case_id": "H01", "template": "请重新登记代号{label}。", "label_a": "辰栈", "label_b": "陌钥"},
    {"case_id": "H02", "template": "请当场核对样本{label}。", "label_a": "霁函", "label_b": "岚策"},
    {"case_id": "H03", "template": "现在立即标记项目{label}。", "label_a": "衡阈", "label_b": "舟岚"},
    {"case_id": "H04", "template": "请完整登记对象{label}。", "label_a": "溪笺", "label_b": "曜牒"},
    {"case_id": "H05", "template": "现在同步核验编号{label}。", "label_a": "川函", "label_b": "镜栈"},
    {"case_id": "H06", "template": "请再次记录节点{label}。", "label_a": "原钥", "label_b": "霁岚"},
    {"case_id": "H07", "template": "现在回填项目代号{label}。", "label_a": "禾策", "label_b": "炘阈"},
    {"case_id": "H08", "template": "请优先确认条目{label}。", "label_a": "芒函", "label_b": "青钥"},
]
FAMILY_SPECS: list[dict[str, str]] = PRIMARY_FAMILY_SPECS + HOLDOUT_LONG_SHELL_FAMILY_SPECS
PROFILE_CHOICES = ("broad_v2", "long_shell_ge9", "holdout_long_shell_ge9")

CONDITIONS = ("repeat", "switch")
START_KEYS = ("A", "B")
TRACK_KEYS = [
    "induction_growth_identity_created_count",
    "hdb_structure_count",
    "hdb_residual_diff_entry_count",
    "hdb_diff_entry_with_memory_ref_count",
]


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


def family_specs(limit: int) -> list[dict[str, str]]:
    keep = max(1, min(int(limit), len(FAMILY_SPECS)))
    return FAMILY_SPECS[:keep]


def family_spec_by_case(case_id: str) -> dict[str, str]:
    for spec in FAMILY_SPECS:
        if str(spec["case_id"]) == str(case_id):
            return spec
    raise KeyError(f"unknown case_id: {case_id}")


def total_text_len(spec: dict[str, str]) -> int:
    return len(str(spec["template"]).format(label=str(spec["label_a"])))


def selected_family_specs(limit: int, *, profile: str, case_ids: list[str] | None = None) -> list[dict[str, str]]:
    if str(profile) == "holdout_long_shell_ge9":
        specs = list(HOLDOUT_LONG_SHELL_FAMILY_SPECS)
    else:
        specs = list(PRIMARY_FAMILY_SPECS)
    if case_ids:
        want = {str(x).strip() for x in case_ids if str(x).strip()}
        specs = [spec for spec in specs if str(spec["case_id"]) in want]
    elif str(profile) == "long_shell_ge9":
        specs = [spec for spec in specs if total_text_len(spec) >= 9]
    keep = max(1, min(int(limit), len(specs)))
    return specs[:keep]


def app_config_override() -> dict[str, Any]:
    return {
        "input_chunking_enabled": False,
        "action_enabled": False,
        "sensor_enable_echo": False,
        "sensor_include_echoes_in_packet": False,
    }


def build_records(spec: dict[str, str], *, condition: str, start_key: str) -> list[dict[str, Any]]:
    start_label = str(spec["label_a"] if start_key == "A" else spec["label_b"])
    alt_label = str(spec["label_b"] if start_key == "A" else spec["label_a"])
    second_label = start_label if condition == "repeat" else alt_label
    template = str(spec["template"])
    first_text = template.format(label=start_label)
    second_text = template.format(label=second_label)
    return [
        {
            "case_id": str(spec["case_id"]),
            "template": template,
            "start_key": start_key,
            "condition": condition,
            "phase": "first",
            "phase_index": 0,
            "source_text_index": 0,
            "label": start_label,
            "other_label": alt_label,
            "text": first_text,
            "text_len": len(first_text),
            "curriculum_version": CURRICULUM_VERSION,
        },
        {
            "case_id": str(spec["case_id"]),
            "template": template,
            "start_key": start_key,
            "condition": condition,
            "phase": "second",
            "phase_index": 1,
            "source_text_index": 1,
            "label": second_label,
            "other_label": start_label if condition == "switch" else alt_label,
            "text": second_text,
            "text_len": len(second_text),
            "curriculum_version": CURRICULUM_VERSION,
        },
    ]


def build_case_texts(case_id: str, *, start_key: str) -> dict[str, Any]:
    spec = family_spec_by_case(case_id)
    repeat_records = build_records(spec, condition="repeat", start_key=start_key)
    switch_records = build_records(spec, condition="switch", start_key=start_key)
    return {
        "template": str(spec["template"]),
        "label_a": str(spec["label_a"]),
        "label_b": str(spec["label_b"]),
        "repeat_first_text": str(repeat_records[0]["text"]),
        "repeat_second_text": str(repeat_records[1]["text"]),
        "switch_first_text": str(switch_records[0]["text"]),
        "switch_second_text": str(switch_records[1]["text"]),
        "repeat_first_label": str(repeat_records[0]["label"]),
        "repeat_second_label": str(repeat_records[1]["label"]),
        "switch_first_label": str(switch_records[0]["label"]),
        "switch_second_label": str(switch_records[1]["label"]),
    }


def analyze_label_slot(template: str, repeat_label: str, switch_label: str) -> dict[str, Any]:
    prefix, suffix = template.split("{label}")
    repeat_text = template.format(label=repeat_label)
    switch_text = template.format(label=switch_label)
    slot_start = len(prefix)
    slot_end = len(repeat_text) - len(suffix)
    diff_positions = [idx for idx, (a, b) in enumerate(zip(repeat_text, switch_text)) if a != b]
    outside_slot_diffs = [idx for idx in diff_positions if not (slot_start <= idx < slot_end)]
    return {
        "repeat_text": repeat_text,
        "switch_text": switch_text,
        "label_len_equal": int(len(repeat_label) == len(switch_label)),
        "second_text_len_equal": int(len(repeat_text) == len(switch_text)),
        "changed_char_count": int(len(diff_positions)),
        "nonlabel_char_diff_count": int(len(outside_slot_diffs)),
        "only_label_changed": int(bool(diff_positions) and not outside_slot_diffs),
        "slot_start": int(slot_start),
        "slot_end": int(slot_end),
    }


def dataset_doc(spec: dict[str, str], *, condition: str, start_key: str, replicate: int) -> dict[str, Any]:
    records = build_records(spec, condition=condition, start_key=start_key)
    ticks: list[dict[str, Any]] = []
    for record in records:
        ticks.append(
            {
                "text": record["text"],
                "tags": [LABEL_KEY, "E02", "label_switch", condition, str(spec["case_id"]), start_key, record["phase"]],
                "labels": {
                    LABEL_KEY: {k: v for k, v in record.items() if k != "text"},
                },
                "meta": {
                    "role": "user",
                    "kind": "message",
                    "phase": "e02_label_switch",
                    "pure_text": True,
                    "real_input_index": int(record["source_text_index"]),
                },
            }
        )
    dataset_id = f"paper_e02_switch_{spec['case_id']}_{condition}_{start_key}_r{replicate}_v2"
    return {
        "dataset_id": dataset_id,
        "title": f"E02 标签替换敏感性 - {spec['case_id']} - {condition} - {start_key} - r{replicate}",
        "description": "E02 定向实验：固定句壳，仅替换标签，比较 exact repeat 与 label switch 的 grasp / familiarity / 结构生长成本。",
        "schema_version": "observatory.dataset.v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "time_basis": "tick",
        "tick_dt_ms": 3000,
        "seed": 2026051112 + int(replicate),
        "app_config_override": app_config_override(),
        "meta": {
            "paper_experiment": "E02_label_switch_sensitivity",
            "curriculum_version": CURRICULUM_VERSION,
            "case_id": spec["case_id"],
            "condition": condition,
            "start_key": start_key,
            "replicate": int(replicate),
            "template": spec["template"],
            "label_a": spec["label_a"],
            "label_b": spec["label_b"],
        },
        "episodes": [
            {
                "id": f"paper_e02_switch_{spec['case_id']}_{condition}_{start_key}_r{replicate}",
                "title": f"E02 switch {spec['case_id']} {condition} {start_key} r{replicate}",
                "tags": [LABEL_KEY, "E02", "label_switch", condition, str(spec["case_id"]), start_key],
                "repeat": 1,
                "ticks": ticks,
            }
        ],
    }


def write_datasets(*, replicates: int, family_limit: int, profile: str, case_ids: list[str] | None = None) -> list[dict[str, Any]]:
    datasets: list[dict[str, Any]] = []
    for spec in selected_family_specs(family_limit, profile=profile, case_ids=case_ids):
        for replicate in range(1, replicates + 1):
            for start_key in START_KEYS:
                for condition in CONDITIONS:
                    doc = dataset_doc(spec, condition=condition, start_key=start_key, replicate=replicate)
                    name = f"{doc['dataset_id']}.yaml"
                    text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
                    artifact_path = DATASET_DIR / name
                    imported_path = imported_datasets_dir() / name
                    artifact_path.write_text(text, encoding="utf-8")
                    imported_path.write_text(text, encoding="utf-8")
                    datasets.append(
                        {
                            "case_id": spec["case_id"],
                            "template": spec["template"],
                            "label_a": spec["label_a"],
                            "label_b": spec["label_b"],
                            "total_text_len": total_text_len(spec),
                            "condition": condition,
                            "start_key": start_key,
                            "replicate": replicate,
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
            print(f"[E02-switch] {stage}: {done}/{planned}", flush=True)


def run_one_dataset(dataset_info: dict[str, Any], *, run_stamp: str, max_ticks: int | None) -> dict[str, Any]:
    run_id = f"paper_e02_switch_{dataset_info['case_id']}_{dataset_info['condition']}_{dataset_info['start_key']}_r{dataset_info['replicate']}_{run_stamp}"
    print(f"[E02-switch] start run_id={run_id}", flush=True)
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
        if bool(row.get("synthetic_tick", False)) or bool(row.get("input_is_empty", False)):
            continue
        label_block = ((row.get("labels") or {}).get(LABEL_KEY) or {}) if isinstance(row.get("labels"), dict) else {}
        if not isinstance(label_block, dict):
            continue
        phase = str(label_block.get("phase", "") or "")
        if phase not in {"first", "second"}:
            continue
        entry = {
            "case_id": str(run_info["case_id"]),
            "replicate": int(run_info["replicate"]),
            "condition": str(run_info["condition"]),
            "start_key": str(run_info["start_key"]),
            "run_id": str(run_info["run_id"]),
            "phase": phase,
            "phase_index": int(label_block.get("phase_index", 0) or 0),
            "label": str(label_block.get("label", "") or ""),
            "template": str(run_info.get("template", "") or ""),
            "text_len": int(label_block.get("text_len", 0) or 0),
            "input_text_preview": str(row.get("input_text_preview", "") or ""),
        }
        for key in TRACK_KEYS:
            entry[key] = round(num(row, key), 8)
        out.append(entry)
    out.sort(key=lambda x: int(x["phase_index"]))
    return out


def build_row_metrics(run_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run_info in run_infos:
        rows.extend(phase_rows_for_run(run_info))
    rows.sort(key=lambda x: (str(x["case_id"]), int(x["replicate"]), str(x["start_key"]), str(x["condition"]), int(x["phase_index"])))
    return rows


def build_pair_rows(row_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    first_rows: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    second_rows: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    for row in row_metrics:
        key = (str(row["case_id"]), int(row["replicate"]), str(row["start_key"]), str(row["condition"]))
        if str(row["phase"]) == "first":
            first_rows[key] = row
        elif str(row["phase"]) == "second":
            second_rows[key] = row

    pair_rows: list[dict[str, Any]] = []
    pair_metrics_switch_higher = [
        "induction_growth_identity_created_count",
        "hdb_structure_count",
        "hdb_residual_diff_entry_count",
        "hdb_diff_entry_with_memory_ref_count",
    ]
    for case_id in sorted({str(row["case_id"]) for row in row_metrics}):
        for replicate in sorted({int(row["replicate"]) for row in row_metrics if str(row["case_id"]) == case_id}):
            for start_key in START_KEYS:
                repeat_first = first_rows.get((case_id, replicate, start_key, "repeat"))
                switch_first = first_rows.get((case_id, replicate, start_key, "switch"))
                repeat_row = second_rows.get((case_id, replicate, start_key, "repeat"))
                switch_row = second_rows.get((case_id, replicate, start_key, "switch"))
                if not repeat_first or not switch_first or not repeat_row or not switch_row:
                    continue
                texts = build_case_texts(case_id, start_key=start_key)
                slot = analyze_label_slot(str(texts["template"]), str(repeat_row["label"]), str(switch_row["label"]))
                pair: dict[str, Any] = {
                    "case_id": case_id,
                    "replicate": replicate,
                    "start_key": start_key,
                    "repeat_label": str(repeat_row["label"]),
                    "switch_label": str(switch_row["label"]),
                    "template": str(texts["template"]),
                    "repeat_first_text": str(texts["repeat_first_text"]),
                    "switch_first_text": str(texts["switch_first_text"]),
                    "repeat_second_text": str(texts["repeat_second_text"]),
                    "switch_second_text": str(texts["switch_second_text"]),
                    "repeat_run_id": str(repeat_row["run_id"]),
                    "switch_run_id": str(switch_row["run_id"]),
                    "first_text_identical_by_design": int(str(texts["repeat_first_text"]) == str(texts["switch_first_text"])),
                    "same_template_by_design": int(str(repeat_row.get("template", "")) == str(switch_row.get("template", "")) == str(texts["template"])),
                    "label_len_equal": int(slot["label_len_equal"]),
                    "second_text_len_equal": int(slot["second_text_len_equal"]),
                    "changed_char_count": int(slot["changed_char_count"]),
                    "nonlabel_char_diff_count": int(slot["nonlabel_char_diff_count"]),
                    "only_label_changed": int(slot["only_label_changed"]),
                    "repeat_first_text_len": len(str(texts["repeat_first_text"])),
                    "repeat_second_text_len": len(str(texts["repeat_second_text"])),
                    "switch_second_text_len": len(str(texts["switch_second_text"])),
                }
                for key in pair_metrics_switch_higher:
                    repeat_value = num(repeat_row, key)
                    switch_value = num(switch_row, key)
                    diff = round(switch_value - repeat_value, 8)
                    pair[f"repeat_{key}"] = round(repeat_value, 8)
                    pair[f"switch_{key}"] = round(switch_value, 8)
                    pair[f"diff_switch_minus_repeat__{key}"] = diff
                    pair[f"supports__{key}"] = int(diff > 0.0)
                pair["supports_design_control"] = int(
                    pair["first_text_identical_by_design"]
                    and pair["same_template_by_design"]
                    and pair["label_len_equal"]
                    and pair["second_text_len_equal"]
                    and pair["only_label_changed"]
                    and pair["nonlabel_char_diff_count"] == 0
                    and pair["changed_char_count"] == len(str(repeat_row["label"]))
                )
                pair["supports_growth_core"] = int(
                    pair["supports__induction_growth_identity_created_count"]
                    and pair["supports__hdb_structure_count"]
                )
                pair["supports_growth_strict"] = int(
                    pair["supports_growth_core"]
                    and pair["supports__hdb_residual_diff_entry_count"]
                    and pair["supports__hdb_diff_entry_with_memory_ref_count"]
                )
                pair["supports_core_pattern"] = int(pair["supports_design_control"] and pair["supports_growth_core"])
                pair["supports_strict_pattern"] = int(pair["supports_design_control"] and pair["supports_growth_strict"])
                pair_rows.append(pair)
    pair_rows.sort(key=lambda x: (str(x["case_id"]), int(x["replicate"]), str(x["start_key"])))
    return pair_rows


def summarize_evidence(pair_rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(pair_rows)
    unique_design_keys = sorted({(str(row["case_id"]), str(row["start_key"])) for row in pair_rows})
    design_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in pair_rows:
        design_groups.setdefault((str(row["case_id"]), str(row["start_key"])), []).append(row)
    summary: dict[str, Any] = {
        "pair_count": n,
        "unique_design_pair_count": len(unique_design_keys),
        "replicate_count_mean": round(statistics.fmean([len(rows) for rows in design_groups.values()]), 4) if design_groups else 0.0,
        "design_control_count": sum(int(row.get("supports_design_control", 0)) for row in pair_rows),
        "design_control_ratio": round(safe_ratio(sum(int(row.get("supports_design_control", 0)) for row in pair_rows), n or 1), 6),
        "growth_core_count": sum(int(row.get("supports_growth_core", 0)) for row in pair_rows),
        "growth_core_ratio": round(safe_ratio(sum(int(row.get("supports_growth_core", 0)) for row in pair_rows), n or 1), 6),
        "growth_strict_count": sum(int(row.get("supports_growth_strict", 0)) for row in pair_rows),
        "growth_strict_ratio": round(safe_ratio(sum(int(row.get("supports_growth_strict", 0)) for row in pair_rows), n or 1), 6),
        "core_pattern_count": sum(int(row.get("supports_core_pattern", 0)) for row in pair_rows),
        "strict_pattern_count": sum(int(row.get("supports_strict_pattern", 0)) for row in pair_rows),
        "core_pattern_ratio": round(safe_ratio(sum(int(row.get("supports_core_pattern", 0)) for row in pair_rows), n or 1), 6),
        "strict_pattern_ratio": round(safe_ratio(sum(int(row.get("supports_strict_pattern", 0)) for row in pair_rows), n or 1), 6),
    }

    switch_higher = [
        "induction_growth_identity_created_count",
        "hdb_structure_count",
        "hdb_residual_diff_entry_count",
        "hdb_diff_entry_with_memory_ref_count",
    ]
    metric_summary: dict[str, Any] = {}
    for key in switch_higher:
        diffs = [num(row, f"diff_switch_minus_repeat__{key}") for row in pair_rows]
        wins = sum(1 for d in diffs if d > 0.0)
        metric_summary[key] = {
            "direction": "switch_higher",
            "win_ratio": round(safe_ratio(wins, len(diffs) or 1), 6),
            "mean_diff": round(statistics.fmean(diffs), 8) if diffs else 0.0,
            "min_diff": round(min(diffs), 8) if diffs else 0.0,
            "max_diff": round(max(diffs), 8) if diffs else 0.0,
        }

    replicate_consistency: dict[str, Any] = {}
    for key in switch_higher:
        pass_groups = 0
        for rows in design_groups.values():
            if rows and all(num(row, f"diff_switch_minus_repeat__{key}") > 0.0 for row in rows):
                pass_groups += 1
        replicate_consistency[key] = {
            "all_replicates_pass_rate": round(safe_ratio(pass_groups, len(design_groups) or 1), 6),
        }
    strict_design_pass = 0
    for rows in design_groups.values():
        if rows and all(int(row.get("supports_strict_pattern", 0) or 0) == 1 for row in rows):
            strict_design_pass += 1
    metric_summary["design_reproducibility"] = {
        "strict_all_replicates_pass_rate": round(safe_ratio(strict_design_pass, len(design_groups) or 1), 6),
        "unique_design_pair_count": len(design_groups),
    }
    metric_summary["replicate_consistency"] = replicate_consistency
    summary["metrics"] = metric_summary

    support_level = "not_supported"
    if (
        summary["unique_design_pair_count"] >= 16
        and summary["design_control_ratio"] >= 1.0
        and summary["growth_core_ratio"] >= 0.95
        and summary["growth_strict_ratio"] >= 0.95
        and metric_summary["induction_growth_identity_created_count"]["win_ratio"] >= 0.95
        and metric_summary["hdb_structure_count"]["win_ratio"] >= 0.95
        and metric_summary["hdb_residual_diff_entry_count"]["win_ratio"] >= 0.95
        and metric_summary["hdb_diff_entry_with_memory_ref_count"]["win_ratio"] >= 0.95
        and metric_summary["induction_growth_identity_created_count"]["mean_diff"] >= 0.5
        and metric_summary["hdb_structure_count"]["mean_diff"] >= 2.0
        and metric_summary["hdb_residual_diff_entry_count"]["mean_diff"] >= 1.0
        and metric_summary["hdb_diff_entry_with_memory_ref_count"]["mean_diff"] >= 0.5
        and metric_summary["design_reproducibility"]["strict_all_replicates_pass_rate"] >= 0.95
    ):
        support_level = "strong_evidence"
    elif summary["unique_design_pair_count"] >= 8 and summary["growth_core_ratio"] >= 0.8 and summary["design_control_ratio"] >= 1.0:
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

    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.4), dpi=160)
    create_ax, struct_ax = axes
    xs = [1, 2]
    for row in pair_rows:
        create_ax.plot(xs, [num(row, "repeat_induction_growth_identity_created_count"), num(row, "switch_induction_growth_identity_created_count")], marker="o", alpha=0.55, linewidth=1.0)
        struct_ax.plot(xs, [num(row, "repeat_hdb_structure_count"), num(row, "switch_hdb_structure_count")], marker="o", alpha=0.55, linewidth=1.0)
    create_ax.set_xticks(xs, ["完全重复", "换标签"])
    create_ax.set_title("新 identity 创建数：完全重复 vs 换标签")
    create_ax.grid(alpha=0.22, linestyle="--")
    struct_ax.set_xticks(xs, ["完全重复", "换标签"])
    struct_ax.set_title("HDB 结构数：完全重复 vs 换标签")
    struct_ax.grid(alpha=0.22, linestyle="--")
    fig.tight_layout()
    out = CHART_DIR / f"e02_label_switch_growth_core_{stamp}.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    paths.append(out)

    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.4), dpi=160)
    residual_ax, memory_ax = axes
    for row in pair_rows:
        residual_ax.plot(xs, [num(row, "repeat_hdb_residual_diff_entry_count"), num(row, "switch_hdb_residual_diff_entry_count")], marker="o", alpha=0.55, linewidth=1.0)
        memory_ax.plot(xs, [num(row, "repeat_hdb_diff_entry_with_memory_ref_count"), num(row, "switch_hdb_diff_entry_with_memory_ref_count")], marker="o", alpha=0.55, linewidth=1.0)
    residual_ax.set_xticks(xs, ["完全重复", "换标签"])
    residual_ax.set_title("残差写入条目数：完全重复 vs 换标签")
    residual_ax.grid(alpha=0.22, linestyle="--")
    memory_ax.set_xticks(xs, ["完全重复", "换标签"])
    memory_ax.set_title("带记忆引用的差异条目数：完全重复 vs 换标签")
    memory_ax.grid(alpha=0.22, linestyle="--")
    fig.tight_layout()
    out = CHART_DIR / f"e02_label_switch_growth_extended_{stamp}.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    paths.append(out)

    return paths


def write_design_note(path: Path, *, profile: str) -> None:
    lines = [
        "# E02 设计说明（标签替换敏感性）",
        "",
        "## 实验档位",
        f"- 当前档位：`{profile}`。",
        "- `broad_v2`：使用 12 个句壳家族做参数勘界，用于观察边界与失效区。",
        "- `long_shell_ge9`：只保留总文本长度大于等于 9 的句壳家族，作为最小确认性批次。",
        "- `holdout_long_shell_ge9`：使用未参与参数勘界的新句壳家族做外推确认，检验长度门槛外推后是否仍成立。",
        "",
        "## 命题",
        "- 在稳定句壳中，仅替换第二句中的局部标签时，AP 应表现出更高的结构生长代价。",
        "",
        "## 控制思路",
        "- 两组都使用相同句壳与相同第一句。",
        "- `repeat`：第二句完全重复第一句。",
        "- `switch`：第二句只替换标签，其余保持不变。",
        "- A/B 标签长度完全相同，且不共享字符，避免“只改了一半”这种弱替换。",
        "- 通过 A/B 起始标签交叉，消去单个标签本身的难易度差异。",
        "- 同一家族重复运行只作为复现检查，不把重复运行误当作新的设计样本。",
        "",
        "## 主要证据",
        "- `induction_growth_identity_created_count`：换标签后新增 identity 数应更高。",
        "- `hdb_structure_count`：换标签后结构总数应更高。",
        "- `hdb_residual_diff_entry_count`：换标签后残差写入条目应更多。",
        "- `hdb_diff_entry_with_memory_ref_count`：换标签后带记忆引用的差异条目应更多。",
        "",
        "## 判据",
        "- 强证据要求：设计控制全部满足；四个结构生长指标方向高度一致；独立设计样本数足够；跨复现运行仍保持稳定。",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(*, pair_rows: list[dict[str, Any]], summary: dict[str, Any], charts: list[Path], datasets: list[dict[str, Any]], run_infos: list[dict[str, Any]], stamp: str, profile: str) -> Path:
    lines: list[str] = []
    lines.append(f"# E02 标签替换敏感性报告（{stamp}）")
    lines.append("")
    lines.append("## 结论")
    lines.append(f"- 实验档位：`{profile}`")
    lines.append(f"- 支持等级：**{summary.get('support_level', 'unknown')}**")
    lines.append(f"- 运行 pair 数：{summary.get('pair_count', 0)}")
    lines.append(f"- 独立设计 pair 数：{summary.get('unique_design_pair_count', 0)}")
    lines.append(f"- 平均每个独立设计的复现次数：{summary.get('replicate_count_mean', 0.0):.3f}")
    lines.append(f"- 设计控制通过率：{summary.get('design_control_ratio', 0.0):.3f}")
    lines.append(f"- 核心结构生长通过率：{summary.get('growth_core_ratio', 0.0):.3f}")
    lines.append(f"- 严格结构生长通过率：{summary.get('growth_strict_ratio', 0.0):.3f}")
    lines.append("")
    lines.append("## 设计说明")
    lines.append("- 本实验不再把熟悉感、既视感或运行时顺序对齐分数作为验收主判据，而是只检验一个更小、更干净的命题：第二句只换标签时，是否稳定带来更高的结构生长成本。")
    lines.append("- 对照关系不依赖运行结果反推，而是由数据集构造直接保证：相同第一句、相同句壳、等长标签、第二句只改标签槽位。")
    if profile == "long_shell_ge9":
        lines.append("- 当前确认批次额外要求总文本长度大于等于 9，用于固定句壳支撑强度，避免把浅句壳的边界效应混入确认性证据。")
    elif profile == "holdout_long_shell_ge9":
        lines.append("- 当前确认批次使用未参与参数勘界的新句壳家族，并要求总文本长度大于等于 9，用于检验前述边界条件是否能外推到新样本。")
    lines.append("")
    lines.append("## 关键指标")
    metrics = summary.get("metrics", {}) if isinstance(summary.get("metrics"), dict) else {}
    for key in (
        "induction_growth_identity_created_count",
        "hdb_structure_count",
        "hdb_residual_diff_entry_count",
        "hdb_diff_entry_with_memory_ref_count",
    ):
        item = metrics.get(key, {}) if isinstance(metrics.get(key), dict) else {}
        lines.append(f"- {key}: win_ratio={float(item.get('win_ratio', 0.0)):.3f}, mean_diff={float(item.get('mean_diff', 0.0)):.4f}, direction={item.get('direction', '')}")
    repro = metrics.get("design_reproducibility", {}) if isinstance(metrics.get("design_reproducibility"), dict) else {}
    lines.append(f"- design_reproducibility: strict_all_replicates_pass_rate={float(repro.get('strict_all_replicates_pass_rate', 0.0)):.3f}")
    lines.append("")
    lines.append("## 图表")
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    lines.append("## 数据规模")
    lines.append(f"- datasets: {len(datasets)}")
    lines.append(f"- runs: {len(run_infos)}")
    lines.append("")
    lines.append("## pair 逐项")
    lines.append("")
    lines.append("| case | rep | start | text_len | design_ctrl | repeat_created | switch_created | repeat_struct | switch_struct | repeat_residual | switch_residual | strict |")
    lines.append("| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in pair_rows:
        lines.append(
            f"| {row['case_id']} | {row['replicate']} | {row['start_key']} | "
            f"{int(row.get('repeat_second_text_len', 0) or 0)} | "
            f"{int(row.get('supports_design_control', 0))} | "
            f"{num(row, 'repeat_induction_growth_identity_created_count'):.0f} | {num(row, 'switch_induction_growth_identity_created_count'):.0f} | "
            f"{num(row, 'repeat_hdb_structure_count'):.0f} | {num(row, 'switch_hdb_structure_count'):.0f} | "
            f"{num(row, 'repeat_hdb_residual_diff_entry_count'):.0f} | {num(row, 'switch_hdb_residual_diff_entry_count'):.0f} | "
            f"{int(row.get('supports_strict_pattern', 0))} |"
        )
    path = REPORT_DIR / f"E02_label_switch_report_{stamp}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def analyze(run_infos: list[dict[str, Any]], datasets: list[dict[str, Any]], stamp: str, *, profile: str) -> dict[str, Any]:
    row_metrics = build_row_metrics(run_infos)
    pair_rows = build_pair_rows(row_metrics)
    summary = summarize_evidence(pair_rows)
    e01.write_csv(TABLE_DIR / f"e02_label_switch_row_metrics_{stamp}.csv", row_metrics)
    e01.write_csv(TABLE_DIR / f"e02_label_switch_pair_rows_{stamp}.csv", pair_rows)
    e01.write_json(TABLE_DIR / f"e02_label_switch_summary_{stamp}.json", summary)
    write_design_note(REPORT_DIR / "E02_label_switch_design_logic.md", profile=profile)
    charts = make_charts(pair_rows, stamp)
    copied = copy_run_artifacts(run_infos)
    report = write_report(pair_rows=pair_rows, summary=summary, charts=charts, datasets=datasets, run_infos=run_infos, stamp=stamp, profile=profile)
    evidence = {
        "experiment": "E02_label_switch_sensitivity",
        "profile": profile,
        "stamp": stamp,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "support_level": summary.get("support_level", ""),
        "summary": summary,
        "datasets": [
            {
                **d,
                "artifact_path": str(d.get("artifact_path", "")),
                "imported_path": str(d.get("imported_path", "")),
            }
            for d in datasets
        ],
        "runs": [{"run_id": r["run_id"], "case_id": r["case_id"], "condition": r["condition"], "start_key": r["start_key"], "replicate": r["replicate"], "status": r.get("status", "")} for r in run_infos],
        "copied_runs": copied,
        "tables": {
            "row_metrics": str(TABLE_DIR / f"e02_label_switch_row_metrics_{stamp}.csv"),
            "pair_rows": str(TABLE_DIR / f"e02_label_switch_pair_rows_{stamp}.csv"),
            "summary": str(TABLE_DIR / f"e02_label_switch_summary_{stamp}.json"),
        },
        "charts": [str(path) for path in charts],
        "report": str(report),
        "design_note": str(REPORT_DIR / "E02_label_switch_design_logic.md"),
    }
    e01.write_json(MANIFEST_DIR / f"E02_label_switch_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E02_label_switch_latest.json", evidence)
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run paper E02 label-switch sensitivity experiment.")
    parser.add_argument("--replicates", type=int, default=2)
    parser.add_argument("--families", type=int, default=12)
    parser.add_argument("--profile", choices=PROFILE_CHOICES, default="broad_v2")
    parser.add_argument("--case-ids", default="")
    parser.add_argument("--max-ticks", type=int, default=0)
    parser.add_argument("--make-only", action="store_true")
    parser.add_argument("--analyze-existing-stamp", default="")
    parser.add_argument("--stamp", default="")
    args = parser.parse_args(argv)

    ensure_dirs()
    stamp = str(args.stamp or now_stamp())
    replicates = max(1, int(args.replicates))
    family_limit = max(1, int(args.families))
    profile = str(args.profile or "broad_v2")
    case_ids = [part.strip() for part in str(args.case_ids or "").split(",") if part.strip()]
    datasets = write_datasets(replicates=replicates, family_limit=family_limit, profile=profile, case_ids=case_ids or None)
    e01.write_json(
        MANIFEST_DIR / f"E02_label_switch_dataset_manifest_{stamp}.json",
        {
            "stamp": stamp,
            "profile": profile,
            "curriculum_version": CURRICULUM_VERSION,
            "replicates": replicates,
            "family_limit": family_limit,
            "case_ids": case_ids,
            "datasets": [
                {
                    "case_id": d["case_id"],
                    "condition": d["condition"],
                    "start_key": d["start_key"],
                    "replicate": d["replicate"],
                    "dataset_id": d["dataset_id"],
                    "dataset_name": d["dataset_name"],
                    "sha256": d["sha256"],
                    "artifact_path": str(d["artifact_path"]),
                }
                for d in datasets
            ],
        },
    )
    print(f"[E02-switch] generated {len(datasets)} datasets", flush=True)
    if args.make_only:
        return 0

    max_ticks = int(args.max_ticks) if int(args.max_ticks or 0) > 0 else None
    run_infos: list[dict[str, Any]] = []
    analyze_existing_stamp = str(args.analyze_existing_stamp or "").strip()
    if analyze_existing_stamp:
        stamp = analyze_existing_stamp
        for d in datasets:
            run_id = f"paper_e02_switch_{d['case_id']}_{d['condition']}_{d['start_key']}_r{d['replicate']}_{stamp}"
            run_dir = resolve_run_dir(run_id)
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
            run_infos.append({**d, "run_id": run_id, "run_dir": run_dir, "manifest": manifest, "status": manifest.get("status", "")})
    else:
        for dataset_info in datasets:
            run_infos.append(run_one_dataset(dataset_info, run_stamp=stamp, max_ticks=max_ticks))

    evidence = analyze(run_infos, datasets, stamp, profile=profile)
    print(json.dumps({"ok": True, "stamp": stamp, "support": evidence["support_level"], "report": evidence["report"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
