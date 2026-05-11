# -*- coding: utf-8 -*-
"""Run paper E03 reward shaping experiment.

Paper-facing E03 claim
----------------------
After a controlled weather-action success/failure receives teacher reward or
punishment, a later matched weak weather probe should show a directional local
action-bias change.  We intentionally test a narrow causal claim:

1. supervision arrives through expectation-contract synthetic teacher ticks;
2. teacher signals are bound to the matched context and cached as local aliases;
3. a later weak matched probe reads that local signal and changes weather_stub
   drive / drive margin / execution tendency.

This script focuses on minimum-scale, logically clean evidence instead of broad
"reward makes the whole system smarter" claims.
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

ROOT = Path(__file__).resolve().parent
AP_ROOT = ROOT / "Artificial-PsyArch"
if str(AP_ROOT) not in sys.path:
    sys.path.insert(0, str(AP_ROOT))

import run_paper_e01_experiment as e01
from observatory._app import ObservatoryApp
from observatory.experiment.io import sha256_file
from observatory.experiment.runner import RunOptions, run_dataset
from observatory.experiment.storage import DatasetFileRef, imported_datasets_dir, resolve_run_dir


ARTIFACT_ROOT = ROOT / "docs" / "paper_artifacts_2026-05-11"
E03_ROOT = ARTIFACT_ROOT / "E03_reward_shaping"
DATASET_DIR = E03_ROOT / "datasets"
RUN_DIR = E03_ROOT / "runs"
TABLE_DIR = E03_ROOT / "tables"
CHART_DIR = E03_ROOT / "charts"
REPORT_DIR = E03_ROOT / "reports"
MANIFEST_DIR = E03_ROOT / "manifests"

LABEL_KEY = "paper_e03_reward_shaping"
CURRICULUM_VERSION = "paper_e03_v1_reward_shaping"

BRANCH_REWARD = "reward_history"
BRANCH_PUNISH = "punish_history"
BRANCH_NEUTRAL = "neutral_control"
BRANCHES = (BRANCH_REWARD, BRANCH_PUNISH, BRANCH_NEUTRAL)


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


def app_config_override(*, reward_coef: float, punish_coef: float, alias_ttl: int) -> dict[str, Any]:
    return {
        "input_chunking_enabled": False,
        "sensor_enable_echo": False,
        "sensor_include_echoes_in_packet": False,
        "threshold_scale_by_rwd_pun_enabled": False,
        "action_fatigue_enabled": False,
        "drive_decay_ratio": 0.0,
        "local_drive_modulation_by_rwd_pun_enabled": True,
        "local_drive_reward_bonus_coef": float(reward_coef),
        "local_drive_punish_penalty_coef": float(punish_coef),
        "teacher_feedback_local_alias_cache_enabled": True,
        "teacher_feedback_local_alias_cache_ttl_ticks": int(alias_ttl),
        "teacher_feedback_local_alias_cache_min_score": 0.55,
        "teacher_feedback_local_alias_cache_min_chars": 4,
        "local_drive_feedback_text_fallback_min_chars": 4,
    }


FAMILY_SPECS: list[dict[str, str]] = [
    {
        "case_id": "F01",
        "city": "上海",
        "event": "图书馆自习",
        "weak_probe": "上海天气呢",
        "explicit_train": "我明天要去上海图书馆自习，上海天气呢？请帮我查一下。",
        "buffer_text": "我先整理一下出门清单。",
        "neutral_text_a": "我先确认一下明天的安排。",
        "neutral_text_b": "我再整理一下随身物品。",
    },
    {
        "case_id": "F02",
        "city": "北京",
        "event": "去医院复查",
        "weak_probe": "北京天气呢",
        "explicit_train": "我明天要去北京医院复查，北京天气呢？请帮我查一下。",
        "buffer_text": "我先把复查资料整理好。",
        "neutral_text_a": "我先确认一下出门时间。",
        "neutral_text_b": "我再整理一下需要带的材料。",
    },
    {
        "case_id": "F03",
        "city": "广州",
        "event": "参加答辩",
        "weak_probe": "广州天气呢",
        "explicit_train": "我后天要去广州参加答辩，广州天气呢？请帮我查一下。",
        "buffer_text": "我先把答辩提纲再看一遍。",
        "neutral_text_a": "我先确认一下答辩时间。",
        "neutral_text_b": "我再整理一下需要携带的文件。",
    },
    {
        "case_id": "F04",
        "city": "杭州",
        "event": "外出拍照",
        "weak_probe": "杭州天气呢",
        "explicit_train": "我周末要去杭州外出拍照，杭州天气呢？请帮我查一下。",
        "buffer_text": "我先检查一下相机电量。",
        "neutral_text_a": "我先确认一下周末安排。",
        "neutral_text_b": "我再整理一下拍照设备。",
    },
    {
        "case_id": "F05",
        "city": "成都",
        "event": "见客户",
        "weak_probe": "成都天气呢",
        "explicit_train": "我明天下午要去成都见客户，成都天气呢？请帮我查一下。",
        "buffer_text": "我先把客户资料准备好。",
        "neutral_text_a": "我先确认一下明天下午的时间。",
        "neutral_text_b": "我再整理一下会面材料。",
    },
    {
        "case_id": "F06",
        "city": "武汉",
        "event": "去学校办手续",
        "weak_probe": "武汉天气呢",
        "explicit_train": "我明天要去武汉学校办手续，武汉天气呢？请帮我查一下。",
        "buffer_text": "我先把证件材料收拾好。",
        "neutral_text_a": "我先确认一下办理流程。",
        "neutral_text_b": "我再整理一下要带的文件。",
    },
]


def family_specs(limit: int) -> list[dict[str, str]]:
    keep = max(1, min(int(limit), len(FAMILY_SPECS)))
    return FAMILY_SPECS[:keep]


def expectation_contract(*, contract_id: str, reward: float, punish: float, anchor_text: str) -> list[dict[str, Any]]:
    return [
        {
            "id": contract_id,
            "within_ticks": 2,
            "success_conditions": {
                "all": [
                    {
                        "kind": "action_executed_kind_min",
                        "action_kind": "weather_stub",
                        "min_count": 1,
                    }
                ]
            },
            "failure_conditions": {
                "all": [
                    {
                        "kind": "metric_eq",
                        "metric": "action_executed_weather_stub_source_visible",
                        "value": 0,
                    }
                ]
            },
            "anchor_policy": {
                "mode": "contains_text",
                "contains_text": str(anchor_text),
                "ref_object_types": ["st"],
            },
            "on_success": {
                "teacher_rwd": float(reward),
                "teacher_pun": 0.0,
                "feedback_text": "教师反馈：刚才这次天气行动是合适的。",
                "labels": {
                    "stream": {
                        "role": "teacher",
                        "kind": "expectation_success",
                        "phase": "reward_shaping",
                        "pure_text": True,
                    }
                },
            },
            "on_failure": {
                "teacher_rwd": 0.0,
                "teacher_pun": float(punish),
                "feedback_text": "教师反馈：刚才这次天气相关处理并不合适。",
                "labels": {
                    "stream": {
                        "role": "teacher",
                        "kind": "expectation_failure",
                        "phase": "reward_shaping",
                        "pure_text": True,
                    }
                },
            },
        }
    ]


def tick_doc(
    *,
    text: str,
    case_id: str,
    branch: str,
    phase: str,
    source_text_index: int,
    expectation: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    labels: dict[str, Any] = {
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
            "phase": "reward_shaping",
            "pure_text": True,
        },
    }
    if expectation:
        labels["expectation_contracts"] = expectation
    return {
        "text": text,
        "tags": ["paper", "E03", "reward_shaping", branch, case_id, phase],
        "labels": labels,
        "meta": {
            "role": "user",
            "kind": "message",
            "phase": "reward_shaping",
            "real_input_index": int(source_text_index),
        },
    }


def build_ticks(spec: dict[str, str], *, branch: str, reward_strength: float, punish_strength: float) -> list[dict[str, Any]]:
    case_id = str(spec["case_id"])
    if branch == BRANCH_REWARD:
        return [
            tick_doc(
                text=str(spec["explicit_train"]),
                case_id=case_id,
                branch=branch,
                phase="train",
                source_text_index=0,
                expectation=expectation_contract(
                    contract_id=f"e03_{case_id}_{branch}_contract",
                    reward=reward_strength,
                    punish=punish_strength,
                    anchor_text=str(spec["weak_probe"]),
                ),
            ),
            tick_doc(
                text=str(spec["buffer_text"]),
                case_id=case_id,
                branch=branch,
                phase="buffer",
                source_text_index=1,
            ),
            tick_doc(
                text=str(spec["weak_probe"]),
                case_id=case_id,
                branch=branch,
                phase="probe",
                source_text_index=2,
            ),
        ]
    if branch == BRANCH_PUNISH:
        return [
            tick_doc(
                text=str(spec["weak_probe"]),
                case_id=case_id,
                branch=branch,
                phase="train",
                source_text_index=0,
                expectation=expectation_contract(
                    contract_id=f"e03_{case_id}_{branch}_contract",
                    reward=reward_strength,
                    punish=punish_strength,
                    anchor_text=str(spec["weak_probe"]),
                ),
            ),
            tick_doc(
                text=str(spec["buffer_text"]),
                case_id=case_id,
                branch=branch,
                phase="buffer",
                source_text_index=1,
            ),
            tick_doc(
                text=str(spec["weak_probe"]),
                case_id=case_id,
                branch=branch,
                phase="probe",
                source_text_index=2,
            ),
        ]
    if branch == BRANCH_NEUTRAL:
        return [
            tick_doc(
                text=str(spec["neutral_text_a"]),
                case_id=case_id,
                branch=branch,
                phase="baseline",
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
                text=str(spec["weak_probe"]),
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
    reward_strength: float,
    punish_strength: float,
    reward_coef: float,
    punish_coef: float,
    alias_ttl: int,
) -> dict[str, Any]:
    ticks = build_ticks(spec, branch=branch, reward_strength=reward_strength, punish_strength=punish_strength)
    dataset_id = f"paper_e03_{spec['case_id']}_{branch}_r{replicate}_v1"
    return {
        "dataset_id": dataset_id,
        "title": f"E03 教师局部塑形 - {spec['case_id']} - {branch} - r{replicate}",
        "description": "E03 定向实验：控制教师奖励/惩罚历史，观察后续弱天气 probe 的局部行动偏置变化。",
        "schema_version": "observatory.dataset.v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "time_basis": "tick",
        "tick_dt_ms": 3000,
        "seed": 2026051103 + int(replicate),
        "app_config_override": app_config_override(
            reward_coef=reward_coef,
            punish_coef=punish_coef,
            alias_ttl=alias_ttl,
        ),
        "meta": {
            "paper_experiment": "E03_reward_shaping",
            "curriculum_version": CURRICULUM_VERSION,
            "case_id": spec["case_id"],
            "branch": branch,
            "replicate": int(replicate),
            "city": spec["city"],
            "event": spec["event"],
            "reward_strength": float(reward_strength),
            "punish_strength": float(punish_strength),
            "reward_coef": float(reward_coef),
            "punish_coef": float(punish_coef),
            "alias_ttl": int(alias_ttl),
        },
        "episodes": [
            {
                "id": f"paper_e03_{spec['case_id']}_{branch}_r{replicate}",
                "title": f"E03 {spec['case_id']} {branch} r{replicate}",
                "tags": ["paper", "E03", "reward_shaping", branch, str(spec["case_id"])],
                "repeat": 1,
                "ticks": ticks,
            }
        ],
    }


def write_datasets(
    *,
    replicates: int,
    family_limit: int,
    reward_strength: float,
    punish_strength: float,
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
                    reward_strength=reward_strength,
                    punish_strength=punish_strength,
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
                        "city": spec["city"],
                        "event": spec["event"],
                        "explicit_train": spec["explicit_train"],
                        "weak_probe": spec["weak_probe"],
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
            print(f"[E03] {stage}: {done}/{planned}", flush=True)


def run_one_dataset(dataset_info: dict[str, Any], *, run_stamp: str, max_ticks: int | None) -> dict[str, Any]:
    run_id = f"paper_e03_{dataset_info['case_id']}_{dataset_info['branch']}_r{dataset_info['replicate']}_{run_stamp}"
    print(f"[E03] start run_id={run_id}", flush=True)
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
        if phase not in {"train", "baseline", "probe"}:
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
            "teacher_rwd": round(num(row, "teacher_rwd"), 8),
            "teacher_pun": round(num(row, "teacher_pun"), 8),
            "teacher_applied_count": int(num(row, "teacher_applied_count")),
            "teacher_attempted_count": int(num(row, "teacher_attempted_count")),
            "action_attempted_weather_stub": int(num(row, "action_attempted_weather_stub")),
            "action_executed_weather_stub": int(num(row, "action_executed_weather_stub")),
            "action_drive_weather_stub_max": round(num(row, "action_drive_weather_stub_max"), 8),
            "action_drive_weather_stub_mean": round(num(row, "action_drive_weather_stub_mean"), 8),
            "action_effective_threshold_weather_stub_mean": round(num(row, "action_effective_threshold_weather_stub_mean"), 8),
            "action_drive_margin_weather_stub_max": round(num(row, "action_drive_margin_weather_stub_max"), 8),
            "action_drive_margin_weather_stub_mean": round(num(row, "action_drive_margin_weather_stub_mean"), 8),
            "action_local_lookup_hit_count_weather_stub": int(num(row, "action_local_lookup_hit_count_weather_stub")),
            "action_local_lookup_text_fallback_hit_count_weather_stub": int(num(row, "action_local_lookup_text_fallback_hit_count_weather_stub")),
            "action_local_lookup_miss_count_weather_stub": int(num(row, "action_local_lookup_miss_count_weather_stub")),
            "action_local_reward_drive_bonus_total_weather_stub": round(num(row, "action_local_reward_drive_bonus_total_weather_stub"), 8),
            "action_local_punish_drive_penalty_total_weather_stub": round(num(row, "action_local_punish_drive_penalty_total_weather_stub"), 8),
            "action_local_reward_signal_total_weather_stub": round(num(row, "action_local_reward_signal_total_weather_stub"), 8),
            "action_local_punish_signal_total_weather_stub": round(num(row, "action_local_punish_signal_total_weather_stub"), 8),
            "teacher_local_alias_active_count": int(num(row, "teacher_local_alias_active_count")),
            "teacher_local_alias_overlay_applied_count": int(num(row, "teacher_local_alias_overlay_applied_count")),
            "teacher_local_alias_overlay_rwd": round(num(row, "teacher_local_alias_overlay_rwd"), 8),
            "teacher_local_alias_overlay_pun": round(num(row, "teacher_local_alias_overlay_pun"), 8),
            "iesm_action_trigger_weather_stub_count": int(num(row, "iesm_action_trigger_weather_stub_count")),
            "iesm_action_trigger_targeted_weather_stub_count": int(num(row, "iesm_action_trigger_targeted_weather_stub_count")),
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


def build_probe_rows(run_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    probe_rows: list[dict[str, Any]] = []
    for run_info in run_infos:
        phase_rows = phase_rows_for_run(run_info)
        probe = next((row for row in phase_rows if str(row.get("phase", "")) == "probe"), None)
        if not probe:
            continue
        probe_rows.append(
            {
                **probe,
                "city": str(run_info.get("city", "") or ""),
                "event": str(run_info.get("event", "") or ""),
                "weak_probe": str(run_info.get("weak_probe", "") or ""),
                "explicit_train": str(run_info.get("explicit_train", "") or ""),
            }
        )
    probe_rows.sort(key=lambda x: (str(x["case_id"]), int(x["replicate"]), str(x["branch"])))
    return probe_rows


def build_pair_rows(probe_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index: dict[tuple[str, int, str], dict[str, Any]] = {}
    for row in probe_rows:
        index[(str(row["case_id"]), int(row["replicate"]), str(row["branch"]))] = row

    pair_rows: list[dict[str, Any]] = []
    for case_id in sorted({str(row["case_id"]) for row in probe_rows}):
        for replicate in sorted({int(row["replicate"]) for row in probe_rows if str(row["case_id"]) == case_id}):
            reward_row = index.get((case_id, replicate, BRANCH_REWARD))
            punish_row = index.get((case_id, replicate, BRANCH_PUNISH))
            neutral_row = index.get((case_id, replicate, BRANCH_NEUTRAL))
            if not reward_row or not punish_row or not neutral_row:
                continue
            pair: dict[str, Any] = {
                "case_id": case_id,
                "replicate": replicate,
                "city": str(reward_row.get("city", "") or ""),
                "probe_text": str(reward_row.get("weak_probe", "") or ""),
                "reward_probe_drive": round(num(reward_row, "action_drive_weather_stub_max"), 8),
                "neutral_probe_drive": round(num(neutral_row, "action_drive_weather_stub_max"), 8),
                "punish_probe_drive": round(num(punish_row, "action_drive_weather_stub_max"), 8),
                "reward_probe_margin": round(num(reward_row, "action_drive_margin_weather_stub_max"), 8),
                "neutral_probe_margin": round(num(neutral_row, "action_drive_margin_weather_stub_max"), 8),
                "punish_probe_margin": round(num(punish_row, "action_drive_margin_weather_stub_max"), 8),
                "reward_probe_execute": int(num(reward_row, "action_executed_weather_stub")),
                "neutral_probe_execute": int(num(neutral_row, "action_executed_weather_stub")),
                "punish_probe_execute": int(num(punish_row, "action_executed_weather_stub")),
                "reward_probe_local_hit": int(num(reward_row, "action_local_lookup_hit_count_weather_stub")),
                "neutral_probe_local_hit": int(num(neutral_row, "action_local_lookup_hit_count_weather_stub")),
                "punish_probe_local_hit": int(num(punish_row, "action_local_lookup_hit_count_weather_stub")),
                "reward_probe_text_hit": int(num(reward_row, "action_local_lookup_text_fallback_hit_count_weather_stub")),
                "neutral_probe_text_hit": int(num(neutral_row, "action_local_lookup_text_fallback_hit_count_weather_stub")),
                "punish_probe_text_hit": int(num(punish_row, "action_local_lookup_text_fallback_hit_count_weather_stub")),
                "reward_probe_reward_bonus": round(num(reward_row, "action_local_reward_drive_bonus_total_weather_stub"), 8),
                "neutral_probe_reward_bonus": round(num(neutral_row, "action_local_reward_drive_bonus_total_weather_stub"), 8),
                "punish_probe_reward_bonus": round(num(punish_row, "action_local_reward_drive_bonus_total_weather_stub"), 8),
                "reward_probe_punish_penalty": round(num(reward_row, "action_local_punish_drive_penalty_total_weather_stub"), 8),
                "neutral_probe_punish_penalty": round(num(neutral_row, "action_local_punish_drive_penalty_total_weather_stub"), 8),
                "punish_probe_punish_penalty": round(num(punish_row, "action_local_punish_drive_penalty_total_weather_stub"), 8),
                "reward_probe_overlay": int(num(reward_row, "teacher_local_alias_overlay_applied_count")),
                "neutral_probe_overlay": int(num(neutral_row, "teacher_local_alias_overlay_applied_count")),
                "punish_probe_overlay": int(num(punish_row, "teacher_local_alias_overlay_applied_count")),
            }
            pair["diff_reward_minus_neutral_drive"] = round(pair["reward_probe_drive"] - pair["neutral_probe_drive"], 8)
            pair["diff_neutral_minus_punish_drive"] = round(pair["neutral_probe_drive"] - pair["punish_probe_drive"], 8)
            pair["diff_reward_minus_punish_drive"] = round(pair["reward_probe_drive"] - pair["punish_probe_drive"], 8)
            pair["diff_reward_minus_neutral_margin"] = round(pair["reward_probe_margin"] - pair["neutral_probe_margin"], 8)
            pair["diff_neutral_minus_punish_margin"] = round(pair["neutral_probe_margin"] - pair["punish_probe_margin"], 8)
            pair["diff_reward_minus_punish_margin"] = round(pair["reward_probe_margin"] - pair["punish_probe_margin"], 8)
            pair["reward_bonus_effect"] = round(
                pair["reward_probe_reward_bonus"] - max(pair["neutral_probe_reward_bonus"], pair["punish_probe_reward_bonus"]),
                8,
            )
            pair["punish_penalty_effect"] = round(
                pair["punish_probe_punish_penalty"] - max(pair["neutral_probe_punish_penalty"], pair["reward_probe_punish_penalty"]),
                8,
            )
            pair["supports_reward_direction_drive"] = int(pair["diff_reward_minus_neutral_drive"] > 0.0)
            pair["supports_punish_direction_drive"] = int(pair["diff_neutral_minus_punish_drive"] > 0.0)
            pair["supports_ordered_drive"] = int(
                pair["reward_probe_drive"] > pair["neutral_probe_drive"] > pair["punish_probe_drive"]
            )
            pair["supports_ordered_margin"] = int(
                pair["reward_probe_margin"] > pair["neutral_probe_margin"] > pair["punish_probe_margin"]
            )
            pair["supports_reward_lookup"] = int(
                pair["reward_probe_local_hit"] >= 1
                and pair["reward_probe_text_hit"] >= 1
                and pair["reward_probe_overlay"] >= 1
                and pair["reward_probe_reward_bonus"] > 0.0
                and pair["reward_probe_punish_penalty"] <= 1e-9
            )
            pair["supports_punish_lookup"] = int(
                pair["punish_probe_local_hit"] >= 1
                and pair["punish_probe_text_hit"] >= 1
                and pair["punish_probe_overlay"] >= 1
                and pair["punish_probe_punish_penalty"] > 0.0
                and pair["punish_probe_reward_bonus"] <= 1e-9
            )
            pair["supports_neutral_quiet"] = int(
                pair["neutral_probe_local_hit"] <= 0
                and pair["neutral_probe_text_hit"] <= 0
                and pair["neutral_probe_overlay"] <= 0
                and pair["neutral_probe_reward_bonus"] <= 1e-9
                and pair["neutral_probe_punish_penalty"] <= 1e-9
            )
            pair["supports_clean_causal_chain"] = int(
                pair["supports_reward_lookup"]
                and pair["supports_punish_lookup"]
                and pair["supports_neutral_quiet"]
                and pair["reward_bonus_effect"] > 0.0
                and pair["punish_penalty_effect"] > 0.0
            )
            pair_rows.append(pair)
    pair_rows.sort(key=lambda x: (str(x["case_id"]), int(x["replicate"])))
    return pair_rows


def sign_test_p_value(wins: int, losses: int) -> float:
    n = int(wins) + int(losses)
    if n <= 0:
        return 1.0
    k = min(int(wins), int(losses))
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return round(min(1.0, 2.0 * tail), 8)


def summarize_evidence(pair_rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(pair_rows)
    reward_drive_diffs = [num(row, "diff_reward_minus_neutral_drive") for row in pair_rows]
    punish_drive_diffs = [num(row, "diff_neutral_minus_punish_drive") for row in pair_rows]
    reward_bonus_effects = [num(row, "reward_bonus_effect") for row in pair_rows]
    punish_penalty_effects = [num(row, "punish_penalty_effect") for row in pair_rows]
    ordered_drive_count = sum(int(row.get("supports_ordered_drive", 0)) for row in pair_rows)
    ordered_margin_count = sum(int(row.get("supports_ordered_margin", 0)) for row in pair_rows)
    clean_chain_count = sum(int(row.get("supports_clean_causal_chain", 0)) for row in pair_rows)
    reward_lookup_count = sum(int(row.get("supports_reward_lookup", 0)) for row in pair_rows)
    punish_lookup_count = sum(int(row.get("supports_punish_lookup", 0)) for row in pair_rows)
    neutral_quiet_count = sum(int(row.get("supports_neutral_quiet", 0)) for row in pair_rows)

    reward_wins = sum(1 for x in reward_drive_diffs if x > 0.0)
    reward_losses = sum(1 for x in reward_drive_diffs if x < 0.0)
    punish_wins = sum(1 for x in punish_drive_diffs if x > 0.0)
    punish_losses = sum(1 for x in punish_drive_diffs if x < 0.0)
    reward_bonus_wins = sum(1 for x in reward_bonus_effects if x > 0.0)
    reward_bonus_losses = sum(1 for x in reward_bonus_effects if x < 0.0)
    punish_penalty_wins = sum(1 for x in punish_penalty_effects if x > 0.0)
    punish_penalty_losses = sum(1 for x in punish_penalty_effects if x < 0.0)

    summary: dict[str, Any] = {
        "pair_count": n,
        "ordered_drive_ratio": round(safe_ratio(ordered_drive_count, n or 1), 6),
        "ordered_margin_ratio": round(safe_ratio(ordered_margin_count, n or 1), 6),
        "reward_lookup_ratio": round(safe_ratio(reward_lookup_count, n or 1), 6),
        "punish_lookup_ratio": round(safe_ratio(punish_lookup_count, n or 1), 6),
        "neutral_quiet_ratio": round(safe_ratio(neutral_quiet_count, n or 1), 6),
        "clean_causal_chain_ratio": round(safe_ratio(clean_chain_count, n or 1), 6),
        "reward_drive_mean_diff": round(statistics.fmean(reward_drive_diffs), 8) if reward_drive_diffs else 0.0,
        "punish_drive_mean_diff": round(statistics.fmean(punish_drive_diffs), 8) if punish_drive_diffs else 0.0,
        "reward_bonus_effect_mean": round(statistics.fmean(reward_bonus_effects), 8) if reward_bonus_effects else 0.0,
        "punish_penalty_effect_mean": round(statistics.fmean(punish_penalty_effects), 8) if punish_penalty_effects else 0.0,
        "reward_drive_win_ratio": round(safe_ratio(reward_wins, reward_wins + reward_losses or 1), 6),
        "punish_drive_win_ratio": round(safe_ratio(punish_wins, punish_wins + punish_losses or 1), 6),
        "reward_drive_sign_p": sign_test_p_value(reward_wins, reward_losses),
        "punish_drive_sign_p": sign_test_p_value(punish_wins, punish_losses),
        "reward_bonus_sign_p": sign_test_p_value(reward_bonus_wins, reward_bonus_losses),
        "punish_penalty_sign_p": sign_test_p_value(punish_penalty_wins, punish_penalty_losses),
    }

    support_level = "not_supported"
    if (
        n >= 12
        and summary["reward_lookup_ratio"] >= 0.95
        and summary["punish_lookup_ratio"] >= 0.95
        and summary["neutral_quiet_ratio"] >= 0.95
        and summary["clean_causal_chain_ratio"] >= 0.95
        and summary["reward_bonus_effect_mean"] >= 0.25
        and summary["punish_penalty_effect_mean"] >= 0.25
        and summary["reward_bonus_sign_p"] <= 0.01
        and summary["punish_penalty_sign_p"] <= 0.01
    ):
        support_level = "strong_evidence"
    elif (
        n >= 6
        and summary["reward_lookup_ratio"] >= 0.75
        and summary["punish_lookup_ratio"] >= 0.75
        and summary["clean_causal_chain_ratio"] >= 0.75
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
        for name in (
            "manifest.json",
            "dataset.normalized.yaml",
            "dataset.source.yaml",
            "metrics.jsonl",
            "runner_timing.jsonl",
            "expectation_contract_events.jsonl",
        ):
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
    drive_ax, margin_ax = axes
    xs = [1, 2, 3]
    for row in pair_rows:
        drive_ax.plot(
            xs,
            [
                num(row, "reward_probe_drive"),
                num(row, "neutral_probe_drive"),
                num(row, "punish_probe_drive"),
            ],
            marker="o",
            alpha=0.60,
            linewidth=1.1,
        )
        margin_ax.plot(
            xs,
            [
                num(row, "reward_probe_margin"),
                num(row, "neutral_probe_margin"),
                num(row, "punish_probe_margin"),
            ],
            marker="o",
            alpha=0.60,
            linewidth=1.1,
        )
    drive_ax.set_xticks(xs, ["奖励历史", "中性对照", "惩罚历史"])
    drive_ax.set_title("E03 弱天气 Probe 驱动力排序")
    drive_ax.grid(alpha=0.22, linestyle="--")
    margin_ax.set_xticks(xs, ["奖励历史", "中性对照", "惩罚历史"])
    margin_ax.set_title("E03 弱天气 Probe 驱动力裕量排序")
    margin_ax.grid(alpha=0.22, linestyle="--")
    fig.tight_layout()
    out = CHART_DIR / f"e03_reward_shaping_ordered_probe_{stamp}.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    paths.append(out)

    fig, ax = plt.subplots(figsize=(8.2, 5.2), dpi=160)
    reward_diffs = [num(row, "diff_reward_minus_neutral_drive") for row in pair_rows]
    punish_diffs = [num(row, "diff_neutral_minus_punish_drive") for row in pair_rows]
    pos = list(range(len(pair_rows)))
    ax.bar([x - 0.18 for x in pos], reward_diffs, width=0.36, label="奖励 - 中性", color="#2b8a3e")
    ax.bar([x + 0.18 for x in pos], punish_diffs, width=0.36, label="中性 - 惩罚", color="#c92a2a")
    ax.axhline(0.0, color="#555555", linewidth=0.9)
    ax.set_xticks(pos, [f"{row['case_id']}-r{row['replicate']}" for row in pair_rows], rotation=35, ha="right")
    ax.set_title("E03 定向差值：局部塑形对弱 Probe 的方向性影响")
    ax.grid(axis="y", alpha=0.22, linestyle="--")
    ax.legend(fontsize=9)
    fig.tight_layout()
    out = CHART_DIR / f"e03_reward_shaping_differences_{stamp}.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    paths.append(out)

    return paths


def write_design_note(path: Path) -> None:
    lines = [
        "# E03 设计说明（教师奖励塑形）",
        "",
        "## 论文口径",
        "- 本实验不主张“奖励已经让 AP 学会了完整天气决策”。",
        "- 本实验只检验更窄、更可复现的命题：在受控监督后，后续相同弱天气壳 probe 的局部行动偏置是否发生方向性变化。",
        "",
        "## 因果链",
        "- 训练 tick 触发 weather_stub 或刻意不触发。",
        "- expectation contract 在后续 tick 结算，并生成 synthetic 教师反馈 tick。",
        "- synthetic tick 将 teacher_reward_signal / teacher_punish_signal 绑定到冻结锚点，并写入局部 alias 缓存。",
        "- probe tick 再次出现高度相似的天气壳，action 侧通过 text fallback 读取局部信号，调制 weather_stub 的 drive。",
        "",
        "## 为什么使用弱天气 probe",
        "- 弱天气壳本身接近执行边界，中性条件通常不过阈值或刚好在边界附近。",
        "- 因此奖励局部增益更容易把它推高，惩罚局部减益更容易把它压低，三组方向性更清晰。",
        "",
        "## 主要反混淆设计",
        "- 关闭全局 reward/punish 阈值调制，只保留局部 drive 调制。",
        "- 关闭行动疲劳，避免 fatigue 额外抬高阈值。",
        "- 将 drive_decay_ratio 设为 0，确保训练分支执行后旧节点 drive 在 probe 前衰减为 0，避免把残留驱动力误判为教师塑形。",
        "- 观察 action_local_lookup_hit / text_fallback_hit 与 reward_bonus / punish_penalty 是否同时出现，确保不是只有表面相关。",
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
    reward_strength: float,
    punish_strength: float,
    reward_coef: float,
    punish_coef: float,
    alias_ttl: int,
) -> Path:
    lines: list[str] = []
    lines.append(f"# E03 ???????????{stamp}?")
    lines.append("")
    lines.append("## ??")
    lines.append(f"- ?????**{summary.get('support_level', 'unknown')}**")
    lines.append(f"- pair ??{summary.get('pair_count', 0)}")
    lines.append(f"- reward lookup ?????{float(summary.get('reward_lookup_ratio', 0.0)):.3f}")
    lines.append(f"- punish lookup ?????{float(summary.get('punish_lookup_ratio', 0.0)):.3f}")
    lines.append(f"- neutral ???????{float(summary.get('neutral_quiet_ratio', 0.0)):.3f}")
    lines.append(f"- ????????{float(summary.get('clean_causal_chain_ratio', 0.0)):.3f}")
    lines.append(f"- ???????????{float(summary.get('reward_bonus_effect_mean', 0.0)):.4f}")
    lines.append(f"- ???????????{float(summary.get('punish_penalty_effect_mean', 0.0)):.4f}")
    lines.append(f"- ?????? sign test p?{float(summary.get('reward_bonus_sign_p', 1.0)):.6f}")
    lines.append(f"- ?????? sign test p?{float(summary.get('punish_penalty_sign_p', 1.0)):.6f}")
    lines.append("")
    lines.append("## ????")
    lines.append(f"- ?????{reward_strength:.3f}")
    lines.append(f"- ?????{punish_strength:.3f}")
    lines.append(f"- ???????{reward_coef:.3f}")
    lines.append(f"- ???????{punish_coef:.3f}")
    lines.append(f"- ?? alias TTL?{alias_ttl}")
    lines.append("- ?? contains_text ?????????????st????????????????em????????")
    lines.append("- ? teacher alias ??????? action text fallback ?????????? 4?????????????? probe?")
    lines.append("- ???? reward/punish ?????????? drive ???")
    lines.append("- ???? fatigue???? drive_decay_ratio=0??????????? drive ????")
    lines.append("")
    lines.append("## ????")
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    lines.append("## Pair ??")
    lines.append("")
    lines.append("| case | rep | city | reward_bonus | punish_penalty | reward_hit | punish_hit | neutral_quiet | clean | reward_drive | neutral_drive | punish_drive |")
    lines.append("| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in pair_rows:
        lines.append(
            f"| {row['case_id']} | {row['replicate']} | {row['city']} | "
            f"{num(row, 'reward_bonus_effect'):.3f} | {num(row, 'punish_penalty_effect'):.3f} | "
            f"{int(row.get('supports_reward_lookup', 0))} | {int(row.get('supports_punish_lookup', 0))} | "
            f"{int(row.get('supports_neutral_quiet', 0))} | {int(row.get('supports_clean_causal_chain', 0))} | "
            f"{num(row, 'reward_probe_drive'):.3f} | {num(row, 'neutral_probe_drive'):.3f} | {num(row, 'punish_probe_drive'):.3f} |"
        )
    lines.append("")
    lines.append("## ????")
    lines.append(f"- datasets: {len(datasets)}")
    lines.append(f"- runs: {len(run_infos)}")
    path = REPORT_DIR / f"E03_reward_shaping_report_{stamp}.md"
    path.write_text("\n".join(lines) + "\n", encoding='utf-8')
    return path
def analyze(
    run_infos: list[dict[str, Any]],
    datasets: list[dict[str, Any]],
    stamp: str,
    *,
    reward_strength: float,
    punish_strength: float,
    reward_coef: float,
    punish_coef: float,
    alias_ttl: int,
) -> dict[str, Any]:
    row_metrics = build_row_metrics(run_infos)
    probe_rows = build_probe_rows(run_infos)
    pair_rows = build_pair_rows(probe_rows)
    summary = summarize_evidence(pair_rows)
    e01.write_csv(TABLE_DIR / f"e03_reward_shaping_row_metrics_{stamp}.csv", row_metrics)
    e01.write_csv(TABLE_DIR / f"e03_reward_shaping_probe_rows_{stamp}.csv", probe_rows)
    e01.write_csv(TABLE_DIR / f"e03_reward_shaping_pair_rows_{stamp}.csv", pair_rows)
    e01.write_json(TABLE_DIR / f"e03_reward_shaping_summary_{stamp}.json", summary)
    write_design_note(REPORT_DIR / "E03_reward_shaping_design_logic.md")
    charts = make_charts(pair_rows, stamp)
    copied = copy_run_artifacts(run_infos)
    report = write_report(
        pair_rows=pair_rows,
        summary=summary,
        charts=charts,
        datasets=datasets,
        run_infos=run_infos,
        stamp=stamp,
        reward_strength=reward_strength,
        punish_strength=punish_strength,
        reward_coef=reward_coef,
        punish_coef=punish_coef,
        alias_ttl=alias_ttl,
    )
    evidence = {
        "experiment": "E03_reward_shaping",
        "stamp": stamp,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "support_level": summary.get("support_level", ""),
        "summary": summary,
        "params": {
            "reward_strength": float(reward_strength),
            "punish_strength": float(punish_strength),
            "reward_coef": float(reward_coef),
            "punish_coef": float(punish_coef),
            "alias_ttl": int(alias_ttl),
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
            "row_metrics": str(TABLE_DIR / f"e03_reward_shaping_row_metrics_{stamp}.csv"),
            "probe_rows": str(TABLE_DIR / f"e03_reward_shaping_probe_rows_{stamp}.csv"),
            "pair_rows": str(TABLE_DIR / f"e03_reward_shaping_pair_rows_{stamp}.csv"),
            "summary": str(TABLE_DIR / f"e03_reward_shaping_summary_{stamp}.json"),
        },
        "charts": [str(path) for path in charts],
        "report": str(report),
        "design_note": str(REPORT_DIR / "E03_reward_shaping_design_logic.md"),
    }
    e01.write_json(MANIFEST_DIR / f"E03_reward_shaping_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E03_reward_shaping_latest.json", evidence)
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run paper E03 reward shaping experiment.")
    parser.add_argument("--replicates", type=int, default=2)
    parser.add_argument("--families", type=int, default=6)
    parser.add_argument("--reward-strength", type=float, default=0.75)
    parser.add_argument("--punish-strength", type=float, default=0.70)
    parser.add_argument("--reward-coef", type=float, default=0.90)
    parser.add_argument("--punish-coef", type=float, default=0.90)
    parser.add_argument("--alias-ttl", type=int, default=6)
    parser.add_argument("--max-ticks", type=int, default=0)
    parser.add_argument("--make-only", action="store_true")
    parser.add_argument("--analyze-existing-stamp", default="")
    parser.add_argument("--stamp", default="")
    args = parser.parse_args(argv)

    ensure_dirs()
    stamp = str(args.stamp or now_stamp())
    replicates = max(1, int(args.replicates))
    family_limit = max(1, int(args.families))
    reward_strength = max(0.0, min(1.0, float(args.reward_strength)))
    punish_strength = max(0.0, min(1.0, float(args.punish_strength)))
    reward_coef = max(0.0, float(args.reward_coef))
    punish_coef = max(0.0, float(args.punish_coef))
    alias_ttl = max(1, int(args.alias_ttl))

    datasets = write_datasets(
        replicates=replicates,
        family_limit=family_limit,
        reward_strength=reward_strength,
        punish_strength=punish_strength,
        reward_coef=reward_coef,
        punish_coef=punish_coef,
        alias_ttl=alias_ttl,
    )
    e01.write_json(
        MANIFEST_DIR / f"E03_reward_shaping_dataset_manifest_{stamp}.json",
        {
            "stamp": stamp,
            "curriculum_version": CURRICULUM_VERSION,
            "replicates": replicates,
            "family_limit": family_limit,
            "reward_strength": reward_strength,
            "punish_strength": punish_strength,
            "reward_coef": reward_coef,
            "punish_coef": punish_coef,
            "alias_ttl": alias_ttl,
            "datasets": [
                {
                    "case_id": d["case_id"],
                    "branch": d["branch"],
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
    print(f"[E03] generated {len(datasets)} datasets", flush=True)
    if args.make_only:
        return 0

    max_ticks = int(args.max_ticks) if int(args.max_ticks or 0) > 0 else None
    run_infos: list[dict[str, Any]] = []
    analyze_existing_stamp = str(args.analyze_existing_stamp or "").strip()
    if analyze_existing_stamp:
        stamp = analyze_existing_stamp
        for d in datasets:
            run_id = f"paper_e03_{d['case_id']}_{d['branch']}_r{d['replicate']}_{stamp}"
            run_dir = resolve_run_dir(run_id)
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
            run_infos.append({**d, "run_id": run_id, "run_dir": run_dir, "manifest": manifest, "status": manifest.get("status", "")})
    else:
        for dataset_info in datasets:
            run_infos.append(run_one_dataset(dataset_info, run_stamp=stamp, max_ticks=max_ticks))

    evidence = analyze(
        run_infos,
        datasets,
        stamp,
        reward_strength=reward_strength,
        punish_strength=punish_strength,
        reward_coef=reward_coef,
        punish_coef=punish_coef,
        alias_ttl=alias_ttl,
    )
    print(json.dumps({"ok": True, "stamp": stamp, "support": evidence["support_level"], "report": evidence["report"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
