# -*- coding: utf-8 -*-
"""Run paper E04 punish-correction experiment.

Paper-facing E04 claim
----------------------
This experiment targets a stricter claim than E03:

After the system is punished on one weak weather target and rewarded on a
corrected weak weather target, later weak probes should show a directional
local preference transfer. In other words, the local teacher signal should not
only exist, but should be able to push the action-side bias away from the
punished target and toward the corrected target.

We intentionally avoid broad claims such as "AP is globally more cautious" or
"punishment already yields a full decision policy". The experiment is designed
to verify a minimum, auditable correction loop.
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
from observatory._app import ObservatoryApp
from observatory.experiment.io import sha256_file
from observatory.experiment.runner import RunOptions, run_dataset
from observatory.experiment.storage import DatasetFileRef, imported_datasets_dir, resolve_run_dir


E04_ROOT = ARTIFACT_ROOT / "E04_punish_correction"
DATASET_DIR = E04_ROOT / "datasets"
RUN_DIR = E04_ROOT / "runs"
TABLE_DIR = E04_ROOT / "tables"
CHART_DIR = E04_ROOT / "charts"
REPORT_DIR = E04_ROOT / "reports"
MANIFEST_DIR = E04_ROOT / "manifests"

LABEL_KEY = "paper_e04_punish_correction"
CURRICULUM_VERSION = "paper_e04_v1_punish_correction"

BRANCH_CORRECTED = "corrected_history"
BRANCH_PUNISHED = "punished_history"
BRANCH_NEUTRAL = "neutral_control"
BRANCHES = (BRANCH_CORRECTED, BRANCH_PUNISHED, BRANCH_NEUTRAL)


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
        "teacher_feedback_focus_directive_enabled": False,
        "teacher_feedback_focus_context_carrier_enabled": False,
        "teacher_feedback_context_binding_enabled": False,
        "teacher_feedback_local_alias_cache_enabled": True,
        "teacher_feedback_local_alias_cache_ttl_ticks": int(alias_ttl),
        "teacher_feedback_local_alias_cache_min_score": 0.80,
        "teacher_feedback_local_alias_cache_min_chars": 4,
        "local_drive_feedback_text_fallback_min_score": 0.80,
        "local_drive_feedback_text_fallback_min_chars": 4,
    }


FAMILY_SPECS: list[dict[str, str]] = [
    {
        "case_id": "F01",
        "city_wrong": "上海",
        "city_right": "北京",
        "event": "医院复查",
        "wrong_probe": "上海天气备忘",
        "right_probe": "北京天气提示",
        "wrong_train": "我明天要去上海医院复查，上海天气备忘。",
        "right_train": "不是上海，是北京。我明天要去北京医院复查，北京天气提示，请帮我查一下。",
        "neutral_text_a": "我先整理一下明天要带的资料。",
        "neutral_text_b": "我再确认一下复查的时间。",
    },
    {
        "case_id": "F02",
        "city_wrong": "广州",
        "city_right": "杭州",
        "event": "外出拍照",
        "wrong_probe": "广州天气备忘",
        "right_probe": "杭州天气提示",
        "wrong_train": "我周末要去广州外出拍照，广州天气备忘。",
        "right_train": "更正一下，不是广州，是杭州。我周末要去杭州外出拍照，杭州天气提示，请帮我查一下。",
        "neutral_text_a": "我先检查一下相机和电池。",
        "neutral_text_b": "我再整理一下拍摄清单。",
    },
    {
        "case_id": "F03",
        "city_wrong": "成都",
        "city_right": "武汉",
        "event": "学校办手续",
        "wrong_probe": "成都天气备忘",
        "right_probe": "武汉天气提示",
        "wrong_train": "我明天要去成都学校办手续，成都天气备忘。",
        "right_train": "刚刚说错了，不是成都，是武汉。我明天要去武汉学校办手续，武汉天气提示，请帮我查一下。",
        "neutral_text_a": "我先把证件材料整理好。",
        "neutral_text_b": "我再确认一下办理流程。",
    },
    {
        "case_id": "F04",
        "city_wrong": "西安",
        "city_right": "南京",
        "event": "参加答辩",
        "wrong_probe": "西安天气备忘",
        "right_probe": "南京天气提示",
        "wrong_train": "我后天要去西安参加答辩，西安天气备忘。",
        "right_train": "更正一下，是去南京参加答辩。南京天气提示，请帮我查一下。",
        "neutral_text_a": "我先把答辩提纲再过一遍。",
        "neutral_text_b": "我再确认一下出发时间。",
    },
    {
        "case_id": "F05",
        "city_wrong": "苏州",
        "city_right": "长沙",
        "event": "见客户",
        "wrong_probe": "苏州天气备忘",
        "right_probe": "长沙天气提示",
        "wrong_train": "我明天下午要去苏州见客户，苏州天气备忘。",
        "right_train": "修正一下，是去长沙见客户。长沙天气提示，请帮我查一下。",
        "neutral_text_a": "我先准备一下客户资料。",
        "neutral_text_b": "我再看一下会面的安排。",
    },
    {
        "case_id": "F06",
        "city_wrong": "青岛",
        "city_right": "天津",
        "event": "图书馆自习",
        "wrong_probe": "青岛天气备忘",
        "right_probe": "天津天气提示",
        "wrong_train": "我明天要去青岛图书馆自习，青岛天气备忘。",
        "right_train": "不是青岛，是天津。我明天要去天津图书馆自习，天津天气提示，请帮我查一下。",
        "neutral_text_a": "我先整理一下要带的书和电脑。",
        "neutral_text_b": "我再确认一下明天的安排。",
    },
    {
        "case_id": "F07",
        "city_wrong": "福州",
        "city_right": "郑州",
        "event": "参加培训",
        "wrong_probe": "福州天气备忘",
        "right_probe": "郑州天气提示",
        "wrong_train": "我下周要去福州参加培训，福州天气备忘。",
        "right_train": "更正一下，不是福州，是郑州。我下周要去郑州参加培训，郑州天气提示，请帮我查一下。",
        "neutral_text_a": "我先把培训资料整理好。",
        "neutral_text_b": "我再确认一下出发时间。",
    },
    {
        "case_id": "F08",
        "city_wrong": "厦门",
        "city_right": "济南",
        "event": "转机出差",
        "wrong_probe": "厦门天气备忘",
        "right_probe": "济南天气提示",
        "wrong_train": "我后天要去厦门转机出差，厦门天气备忘。",
        "right_train": "修正一下，不是厦门，是济南。我后天要去济南转机出差，济南天气提示，请帮我查一下。",
        "neutral_text_a": "我先检查一下机票和证件。",
        "neutral_text_b": "我再整理一下出差清单。",
    },
    {
        "case_id": "F09",
        "city_wrong": "昆明",
        "city_right": "合肥",
        "event": "去展会",
        "wrong_probe": "昆明天气备忘",
        "right_probe": "合肥天气提示",
        "wrong_train": "我周末要去昆明参加展会，昆明天气备忘。",
        "right_train": "刚刚说错了，不是昆明，是合肥。我周末要去合肥参加展会，合肥天气提示，请帮我查一下。",
        "neutral_text_a": "我先把展会资料准备好。",
        "neutral_text_b": "我再确认一下进场安排。",
    },
    {
        "case_id": "F10",
        "city_wrong": "宁波",
        "city_right": "南昌",
        "event": "看演出",
        "wrong_probe": "宁波天气备忘",
        "right_probe": "南昌天气提示",
        "wrong_train": "我周五晚上要去宁波看演出，宁波天气备忘。",
        "right_train": "更正一下，地点不是宁波，是南昌。南昌天气提示，请帮我查一下。",
        "neutral_text_a": "我先把门票和证件整理好。",
        "neutral_text_b": "我再确认一下入场时间。",
    },
    {
        "case_id": "F11",
        "city_wrong": "太原",
        "city_right": "海口",
        "event": "实验室开会",
        "wrong_probe": "太原天气备忘",
        "right_probe": "海口天气提示",
        "wrong_train": "我明天要去太原实验室开会，太原天气备忘。",
        "right_train": "不是太原，是海口。我明天要去海口实验室开会，海口天气提示，请帮我查一下。",
        "neutral_text_a": "我先整理一下会议提纲。",
        "neutral_text_b": "我再确认一下会场安排。",
    },
    {
        "case_id": "F12",
        "city_wrong": "兰州",
        "city_right": "大连",
        "event": "探望亲戚",
        "wrong_probe": "兰州天气备忘",
        "right_probe": "大连天气提示",
        "wrong_train": "我下周要去兰州探望亲戚，兰州天气备忘。",
        "right_train": "更正一下，这次不是兰州，是大连。大连天气提示，请帮我查一下。",
        "neutral_text_a": "我先把礼物和行李收拾好。",
        "neutral_text_b": "我再确认一下行程安排。",
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
                "feedback_text": "教师反馈：这次天气目标已经纠正并处理正确。",
                "labels": {
                    "stream": {
                        "role": "teacher",
                        "kind": "expectation_success",
                        "phase": "punish_correction",
                        "pure_text": True,
                    }
                },
            },
            "on_failure": {
                "teacher_rwd": 0.0,
                "teacher_pun": float(punish),
                "feedback_text": "教师反馈：这次天气目标仍然不对，需要把注意力从错误目标上移开。",
                "labels": {
                    "stream": {
                        "role": "teacher",
                        "kind": "expectation_failure",
                        "phase": "punish_correction",
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
            "phase": "punish_correction",
            "pure_text": True,
        },
    }
    if expectation:
        labels["expectation_contracts"] = expectation
    return {
        "text": text,
        "tags": ["paper", "E04", "punish_correction", branch, case_id, phase],
        "labels": labels,
        "meta": {
            "role": "user",
            "kind": "message",
            "phase": "punish_correction",
            "real_input_index": int(source_text_index),
        },
    }


def build_ticks(spec: dict[str, str], *, branch: str, reward_strength: float, punish_strength: float) -> list[dict[str, Any]]:
    case_id = str(spec["case_id"])
    if branch == BRANCH_CORRECTED:
        return [
            tick_doc(
                text=str(spec["wrong_train"]),
                case_id=case_id,
                branch=branch,
                phase="punish_train",
                source_text_index=0,
                expectation=expectation_contract(
                    contract_id=f"e04_{case_id}_{branch}_wrong_contract",
                    reward=reward_strength,
                    punish=punish_strength,
                    anchor_text=str(spec["wrong_probe"]),
                ),
            ),
            tick_doc(
                text=str(spec["neutral_text_a"]),
                case_id=case_id,
                branch=branch,
                phase="buffer_after_punish",
                source_text_index=1,
            ),
            tick_doc(
                text=str(spec["right_train"]),
                case_id=case_id,
                branch=branch,
                phase="reward_train",
                source_text_index=2,
                expectation=expectation_contract(
                    contract_id=f"e04_{case_id}_{branch}_right_contract",
                    reward=reward_strength,
                    punish=punish_strength,
                    anchor_text=str(spec["right_probe"]),
                ),
            ),
            tick_doc(
                text=str(spec["neutral_text_b"]),
                case_id=case_id,
                branch=branch,
                phase="buffer_after_reward",
                source_text_index=3,
            ),
            tick_doc(
                text=str(spec["wrong_probe"]),
                case_id=case_id,
                branch=branch,
                phase="probe_wrong",
                source_text_index=4,
            ),
            tick_doc(
                text=str(spec["right_probe"]),
                case_id=case_id,
                branch=branch,
                phase="probe_right",
                source_text_index=5,
            ),
        ]
    if branch == BRANCH_PUNISHED:
        return [
            tick_doc(
                text=str(spec["wrong_train"]),
                case_id=case_id,
                branch=branch,
                phase="punish_train",
                source_text_index=0,
                expectation=expectation_contract(
                    contract_id=f"e04_{case_id}_{branch}_wrong_contract",
                    reward=reward_strength,
                    punish=punish_strength,
                    anchor_text=str(spec["wrong_probe"]),
                ),
            ),
            tick_doc(
                text=str(spec["neutral_text_a"]),
                case_id=case_id,
                branch=branch,
                phase="buffer",
                source_text_index=1,
            ),
            tick_doc(
                text=str(spec["wrong_probe"]),
                case_id=case_id,
                branch=branch,
                phase="probe_wrong",
                source_text_index=2,
            ),
            tick_doc(
                text=str(spec["right_probe"]),
                case_id=case_id,
                branch=branch,
                phase="probe_right",
                source_text_index=3,
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
                text=str(spec["wrong_probe"]),
                case_id=case_id,
                branch=branch,
                phase="probe_wrong",
                source_text_index=2,
            ),
            tick_doc(
                text=str(spec["right_probe"]),
                case_id=case_id,
                branch=branch,
                phase="probe_right",
                source_text_index=3,
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
    dataset_id = f"paper_e04_{spec['case_id']}_{branch}_r{replicate}_v1"
    return {
        "dataset_id": dataset_id,
        "title": f"E04 教师惩罚纠偏 - {spec['case_id']} - {branch} - r{replicate}",
        "description": "E04 定向实验：先对错误天气目标施加惩罚，再观察纠正目标是否在弱 probe 中获得局部偏置转移。",
        "schema_version": "observatory.dataset.v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "time_basis": "tick",
        "tick_dt_ms": 3000,
        "seed": 2026051104 + int(replicate),
        "app_config_override": app_config_override(
            reward_coef=reward_coef,
            punish_coef=punish_coef,
            alias_ttl=alias_ttl,
        ),
        "meta": {
            "paper_experiment": "E04_punish_correction",
            "curriculum_version": CURRICULUM_VERSION,
            "case_id": spec["case_id"],
            "branch": branch,
            "replicate": int(replicate),
            "city_wrong": spec["city_wrong"],
            "city_right": spec["city_right"],
            "event": spec["event"],
            "reward_strength": float(reward_strength),
            "punish_strength": float(punish_strength),
            "reward_coef": float(reward_coef),
            "punish_coef": float(punish_coef),
            "alias_ttl": int(alias_ttl),
        },
        "episodes": [
            {
                "id": f"paper_e04_{spec['case_id']}_{branch}_r{replicate}",
                "title": f"E04 {spec['case_id']} {branch} r{replicate}",
                "tags": ["paper", "E04", "punish_correction", branch, str(spec["case_id"])],
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
                        "city_wrong": spec["city_wrong"],
                        "city_right": spec["city_right"],
                        "event": spec["event"],
                        "wrong_probe": spec["wrong_probe"],
                        "right_probe": spec["right_probe"],
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
            print(f"[E04] {stage}: {done}/{planned}", flush=True)


def run_one_dataset(dataset_info: dict[str, Any], *, run_stamp: str, max_ticks: int | None) -> dict[str, Any]:
    run_id = f"paper_e04_{dataset_info['case_id']}_{dataset_info['branch']}_r{dataset_info['replicate']}_{run_stamp}"
    print(f"[E04] start run_id={run_id}", flush=True)
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
        if phase not in {"punish_train", "reward_train", "baseline", "probe_wrong", "probe_right"}:
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
            "action_drive_margin_weather_stub_max": round(num(row, "action_drive_margin_weather_stub_max"), 8),
            "action_local_lookup_hit_count_weather_stub": int(num(row, "action_local_lookup_hit_count_weather_stub")),
            "action_local_lookup_text_fallback_hit_count_weather_stub": int(num(row, "action_local_lookup_text_fallback_hit_count_weather_stub")),
            "action_local_reward_drive_bonus_total_weather_stub": round(num(row, "action_local_reward_drive_bonus_total_weather_stub"), 8),
            "action_local_punish_drive_penalty_total_weather_stub": round(num(row, "action_local_punish_drive_penalty_total_weather_stub"), 8),
            "teacher_local_alias_overlay_applied_count": int(num(row, "teacher_local_alias_overlay_applied_count")),
            "teacher_local_alias_overlay_rwd": round(num(row, "teacher_local_alias_overlay_rwd"), 8),
            "teacher_local_alias_overlay_pun": round(num(row, "teacher_local_alias_overlay_pun"), 8),
            "iesm_action_trigger_weather_stub_count": int(num(row, "iesm_action_trigger_weather_stub_count")),
            "iesm_action_trigger_targeted_weather_stub_count": int(num(row, "iesm_action_trigger_targeted_weather_stub_count")),
        }
        out.append(entry)
    out.sort(key=lambda x: int(x["tick_index"]))
    return out


def build_probe_rows(run_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    probe_rows: list[dict[str, Any]] = []
    for run_info in run_infos:
        phase_rows = phase_rows_for_run(run_info)
        for phase in ("probe_wrong", "probe_right"):
            probe = next((row for row in phase_rows if str(row.get("phase", "")) == phase), None)
            if not probe:
                continue
            probe_rows.append(
                {
                    **probe,
                    "city_wrong": str(run_info.get("city_wrong", "") or ""),
                    "city_right": str(run_info.get("city_right", "") or ""),
                    "wrong_probe": str(run_info.get("wrong_probe", "") or ""),
                    "right_probe": str(run_info.get("right_probe", "") or ""),
                }
            )
    probe_rows.sort(key=lambda x: (str(x["case_id"]), int(x["replicate"]), str(x["branch"]), str(x["phase"])))
    return probe_rows


def build_pair_rows(probe_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    for row in probe_rows:
        index[(str(row["case_id"]), int(row["replicate"]), str(row["branch"]), str(row["phase"]))] = row

    pair_rows: list[dict[str, Any]] = []
    for case_id in sorted({str(row["case_id"]) for row in probe_rows}):
        for replicate in sorted({int(row["replicate"]) for row in probe_rows if str(row["case_id"]) == case_id}):
            corrected_wrong = index.get((case_id, replicate, BRANCH_CORRECTED, "probe_wrong"))
            corrected_right = index.get((case_id, replicate, BRANCH_CORRECTED, "probe_right"))
            punished_wrong = index.get((case_id, replicate, BRANCH_PUNISHED, "probe_wrong"))
            punished_right = index.get((case_id, replicate, BRANCH_PUNISHED, "probe_right"))
            neutral_wrong = index.get((case_id, replicate, BRANCH_NEUTRAL, "probe_wrong"))
            neutral_right = index.get((case_id, replicate, BRANCH_NEUTRAL, "probe_right"))
            if not all((corrected_wrong, corrected_right, punished_wrong, punished_right, neutral_wrong, neutral_right)):
                continue

            pair: dict[str, Any] = {
                "case_id": case_id,
                "replicate": replicate,
                "city_wrong": str(corrected_wrong.get("city_wrong", "") or ""),
                "city_right": str(corrected_wrong.get("city_right", "") or ""),
                "corrected_right_drive": round(num(corrected_right, "action_drive_weather_stub_max"), 8),
                "corrected_wrong_drive": round(num(corrected_wrong, "action_drive_weather_stub_max"), 8),
                "punished_right_drive": round(num(punished_right, "action_drive_weather_stub_max"), 8),
                "punished_wrong_drive": round(num(punished_wrong, "action_drive_weather_stub_max"), 8),
                "neutral_right_drive": round(num(neutral_right, "action_drive_weather_stub_max"), 8),
                "neutral_wrong_drive": round(num(neutral_wrong, "action_drive_weather_stub_max"), 8),
                "corrected_right_reward_bonus": round(num(corrected_right, "action_local_reward_drive_bonus_total_weather_stub"), 8),
                "corrected_right_punish_penalty": round(num(corrected_right, "action_local_punish_drive_penalty_total_weather_stub"), 8),
                "corrected_wrong_reward_bonus": round(num(corrected_wrong, "action_local_reward_drive_bonus_total_weather_stub"), 8),
                "corrected_wrong_punish_penalty": round(num(corrected_wrong, "action_local_punish_drive_penalty_total_weather_stub"), 8),
                "punished_wrong_reward_bonus": round(num(punished_wrong, "action_local_reward_drive_bonus_total_weather_stub"), 8),
                "punished_wrong_punish_penalty": round(num(punished_wrong, "action_local_punish_drive_penalty_total_weather_stub"), 8),
                "neutral_right_reward_bonus": round(num(neutral_right, "action_local_reward_drive_bonus_total_weather_stub"), 8),
                "neutral_wrong_punish_penalty": round(num(neutral_wrong, "action_local_punish_drive_penalty_total_weather_stub"), 8),
                "corrected_right_lookup": int(num(corrected_right, "action_local_lookup_hit_count_weather_stub")),
                "corrected_right_text_hit": int(num(corrected_right, "action_local_lookup_text_fallback_hit_count_weather_stub")),
                "corrected_right_overlay": int(num(corrected_right, "teacher_local_alias_overlay_applied_count")),
                "punished_wrong_lookup": int(num(punished_wrong, "action_local_lookup_hit_count_weather_stub")),
                "punished_wrong_text_hit": int(num(punished_wrong, "action_local_lookup_text_fallback_hit_count_weather_stub")),
                "punished_wrong_overlay": int(num(punished_wrong, "teacher_local_alias_overlay_applied_count")),
                "neutral_right_lookup": int(num(neutral_right, "action_local_lookup_hit_count_weather_stub")),
                "neutral_wrong_lookup": int(num(neutral_wrong, "action_local_lookup_hit_count_weather_stub")),
            }
            pair["rightward_shift_effect"] = round(
                (pair["corrected_right_drive"] - pair["corrected_wrong_drive"])
                - (pair["punished_right_drive"] - pair["punished_wrong_drive"]),
                8,
            )
            pair["corrected_internal_selectivity"] = round(
                pair["corrected_right_reward_bonus"] - pair["corrected_wrong_punish_penalty"],
                8,
            )
            pair["corrected_total_local_signal"] = round(
                pair["corrected_right_reward_bonus"] + pair["corrected_wrong_punish_penalty"],
                8,
            )
            pair["corrected_vs_neutral_right_effect"] = round(
                pair["corrected_right_reward_bonus"] - pair["neutral_right_reward_bonus"],
                8,
            )
            pair["punished_vs_neutral_wrong_effect"] = round(
                pair["punished_wrong_punish_penalty"] - pair["neutral_wrong_punish_penalty"],
                8,
            )
            pair["supports_corrected_right_lookup"] = int(
                pair["corrected_right_lookup"] >= 1
                and pair["corrected_right_text_hit"] >= 1
                and pair["corrected_right_overlay"] >= 1
                and pair["corrected_right_reward_bonus"] > 0.0
                and pair["corrected_right_punish_penalty"] <= 1e-9
            )
            pair["supports_punished_wrong_lookup"] = int(
                pair["punished_wrong_lookup"] >= 1
                and pair["punished_wrong_text_hit"] >= 1
                and pair["punished_wrong_overlay"] >= 1
                and pair["punished_wrong_punish_penalty"] > 0.0
                and pair["punished_wrong_reward_bonus"] <= 1e-9
            )
            pair["supports_neutral_quiet"] = int(
                pair["neutral_right_lookup"] <= 0
                and pair["neutral_wrong_lookup"] <= 0
                and pair["neutral_right_reward_bonus"] <= 1e-9
                and pair["neutral_wrong_punish_penalty"] <= 1e-9
            )
            pair["supports_shift_direction"] = int(
                pair["corrected_vs_neutral_right_effect"] > 0.0
                and pair["punished_vs_neutral_wrong_effect"] > 0.0
                and pair["corrected_right_reward_bonus"] > 0.0
                and pair["corrected_wrong_punish_penalty"] > 0.0
                and pair["corrected_internal_selectivity"] >= -1e-9
            )
            pair["supports_clean_causal_chain"] = int(
                pair["supports_corrected_right_lookup"]
                and pair["supports_punished_wrong_lookup"]
                and pair["supports_neutral_quiet"]
                and pair["supports_shift_direction"]
            )
            pair_rows.append(pair)
    pair_rows.sort(key=lambda x: (str(x["case_id"]), int(x["replicate"])))
    return pair_rows


def sign_test_p_value(wins: int, losses: int) -> float:
    n = int(wins) + int(losses)
    if n <= 0:
        return 1.0
    k = min(int(wins), int(losses))
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return round(min(1.0, 2.0 * tail), 8)


def summarize_evidence(pair_rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(pair_rows)
    shift_effects = [num(row, "rightward_shift_effect") for row in pair_rows]
    corrected_selectivities = [num(row, "corrected_internal_selectivity") for row in pair_rows]
    corrected_total_signals = [num(row, "corrected_total_local_signal") for row in pair_rows]
    corrected_effects = [num(row, "corrected_vs_neutral_right_effect") for row in pair_rows]
    punished_effects = [num(row, "punished_vs_neutral_wrong_effect") for row in pair_rows]
    corrected_lookup_count = sum(int(row.get("supports_corrected_right_lookup", 0)) for row in pair_rows)
    punished_lookup_count = sum(int(row.get("supports_punished_wrong_lookup", 0)) for row in pair_rows)
    neutral_quiet_count = sum(int(row.get("supports_neutral_quiet", 0)) for row in pair_rows)
    clean_chain_count = sum(int(row.get("supports_clean_causal_chain", 0)) for row in pair_rows)

    shift_wins = sum(1 for x in shift_effects if x > 0.0)
    shift_losses = sum(1 for x in shift_effects if x < 0.0)
    corrected_selectivity_wins = sum(1 for x in corrected_selectivities if x >= -1e-9)
    corrected_selectivity_losses = sum(1 for x in corrected_selectivities if x < -1e-9)
    corrected_total_signal_wins = sum(1 for x in corrected_total_signals if x > 0.0)
    corrected_total_signal_losses = sum(1 for x in corrected_total_signals if x < 0.0)
    corrected_wins = sum(1 for x in corrected_effects if x > 0.0)
    corrected_losses = sum(1 for x in corrected_effects if x < 0.0)
    punished_wins = sum(1 for x in punished_effects if x > 0.0)
    punished_losses = sum(1 for x in punished_effects if x < 0.0)

    summary: dict[str, Any] = {
        "pair_count": n,
        "corrected_lookup_ratio": round(safe_ratio(corrected_lookup_count, n or 1), 6),
        "punished_lookup_ratio": round(safe_ratio(punished_lookup_count, n or 1), 6),
        "neutral_quiet_ratio": round(safe_ratio(neutral_quiet_count, n or 1), 6),
        "clean_causal_chain_ratio": round(safe_ratio(clean_chain_count, n or 1), 6),
        "rightward_shift_effect_mean": round(statistics.fmean(shift_effects), 8) if shift_effects else 0.0,
        "corrected_internal_selectivity_mean": round(statistics.fmean(corrected_selectivities), 8) if corrected_selectivities else 0.0,
        "corrected_total_local_signal_mean": round(statistics.fmean(corrected_total_signals), 8) if corrected_total_signals else 0.0,
        "corrected_vs_neutral_right_effect_mean": round(statistics.fmean(corrected_effects), 8) if corrected_effects else 0.0,
        "punished_vs_neutral_wrong_effect_mean": round(statistics.fmean(punished_effects), 8) if punished_effects else 0.0,
        "shift_sign_p": sign_test_p_value(shift_wins, shift_losses),
        "corrected_selectivity_sign_p": sign_test_p_value(corrected_selectivity_wins, corrected_selectivity_losses),
        "corrected_total_signal_sign_p": sign_test_p_value(corrected_total_signal_wins, corrected_total_signal_losses),
        "corrected_effect_sign_p": sign_test_p_value(corrected_wins, corrected_losses),
        "punished_effect_sign_p": sign_test_p_value(punished_wins, punished_losses),
    }

    support_level = "not_supported"
    if (
        n >= 12
        and summary["corrected_lookup_ratio"] >= 0.95
        and summary["punished_lookup_ratio"] >= 0.95
        and summary["neutral_quiet_ratio"] >= 0.95
        and summary["clean_causal_chain_ratio"] >= 0.95
        and summary["corrected_internal_selectivity_mean"] >= -1e-9
        and summary["corrected_total_local_signal_mean"] >= 0.30
        and summary["corrected_vs_neutral_right_effect_mean"] >= 0.15
        and summary["punished_vs_neutral_wrong_effect_mean"] >= 0.15
        and summary["corrected_selectivity_sign_p"] <= 0.01
        and summary["corrected_total_signal_sign_p"] <= 0.01
        and summary["corrected_effect_sign_p"] <= 0.01
        and summary["punished_effect_sign_p"] <= 0.01
    ):
        support_level = "strong_evidence"
    elif (
        n >= 6
        and summary["corrected_lookup_ratio"] >= 0.75
        and summary["punished_lookup_ratio"] >= 0.75
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

    fig, ax = plt.subplots(figsize=(10.6, 5.2), dpi=160)
    xs = list(range(len(pair_rows)))
    ax.bar([x - 0.25 for x in xs], [num(r, "corrected_right_drive") for r in pair_rows], width=0.25, label="纠正史-正确 probe", color="#2b8a3e")
    ax.bar(xs, [num(r, "punished_wrong_drive") for r in pair_rows], width=0.25, label="惩罚史-错误 probe", color="#c92a2a")
    ax.bar([x + 0.25 for x in xs], [num(r, "neutral_right_drive") for r in pair_rows], width=0.25, label="中性-正确 probe", color="#1c7ed6")
    ax.set_xticks(xs, [f"{r['case_id']}-r{r['replicate']}" for r in pair_rows], rotation=35, ha="right")
    ax.set_title("E04 纠偏实验：关键 probe 上的局部驱动力对照")
    ax.grid(axis="y", alpha=0.22, linestyle="--")
    ax.legend(fontsize=9)
    fig.tight_layout()
    out = CHART_DIR / f"e04_punish_correction_key_drives_{stamp}.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    paths.append(out)

    fig, ax = plt.subplots(figsize=(8.6, 5.2), dpi=160)
    ax.bar([x - 0.2 for x in xs], [num(r, "corrected_vs_neutral_right_effect") for r in pair_rows], width=0.4, label="正确目标奖励效应", color="#2b8a3e")
    ax.bar([x + 0.2 for x in xs], [num(r, "punished_vs_neutral_wrong_effect") for r in pair_rows], width=0.4, label="错误目标惩罚效应", color="#c92a2a")
    ax.axhline(0.0, color="#555555", linewidth=0.9)
    ax.set_xticks(xs, [f"{r['case_id']}-r{r['replicate']}" for r in pair_rows], rotation=35, ha="right")
    ax.set_title("E04 纠偏实验：局部奖励/惩罚效应与偏置转移")
    ax.grid(axis="y", alpha=0.22, linestyle="--")
    ax.legend(fontsize=9)
    fig.tight_layout()
    out = CHART_DIR / f"e04_punish_correction_effects_{stamp}.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    paths.append(out)

    return paths


def write_design_note(path: Path) -> None:
    lines = [
        "# E04 设计说明（教师惩罚纠偏）",
        "",
        "## 论文口径",
        "- 本实验不主张“惩罚已经让 AP 获得了全局保守人格”。",
        "- 本实验只检验更严格、更局部的命题：在同一类弱天气壳中，教师惩罚能否把偏置从错误目标上移开，并在纠正目标上形成可读出的局部奖励偏置。",
        "",
        "## 因果链",
        "- 错误目标训练 tick 先触发 weather_stub，并通过 expectation contract 回弹教师惩罚。",
        "- 纠正目标训练 tick 随后触发 weather_stub，并回弹教师奖励。",
        "- 两个监督都绑定到各自的结构目标，并写入局部 alias 缓存。",
        "- 后续错误 probe 与正确 probe 分别再次出现，action 侧通过 text fallback 读取对应的局部奖惩别名。",
        "- 若局部偏置真的被纠正，则正确目标 probe 的奖励侧效应应高于中性，而错误目标 probe 的惩罚侧效应也应高于中性，且整体偏置应向正确目标转移。",
        "",
        "## 主要反混淆设计",
        "- 关闭全局 reward/punish 阈值调制、关闭行动疲劳，只保留局部 drive 调制。",
        "- 关闭 teacher feedback 的 focus directive、上下文载体聚焦与上下文镜像绑定，只保留主目标绑定和局部 alias 回放。",
        "- 错误城市与正确城市成对出现，probe 文本短但保持城市名差异，避免仅凭“天气呢”后缀串台。",
        "- 中性分支只保留同主题但不写入教师别名的上下文，用于验证局部 lookup 不会无中生有。",
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
    lines.append(f"# E04 教师惩罚纠偏报告（{stamp}）")
    lines.append("")
    lines.append("## 结果摘要")
    lines.append(f"- 支持等级：**{summary.get('support_level', 'unknown')}**")
    lines.append(f"- pair 数：{summary.get('pair_count', 0)}")
    lines.append(f"- corrected lookup 比例：{float(summary.get('corrected_lookup_ratio', 0.0)):.3f}")
    lines.append(f"- punished lookup 比例：{float(summary.get('punished_lookup_ratio', 0.0)):.3f}")
    lines.append(f"- neutral quiet 比例：{float(summary.get('neutral_quiet_ratio', 0.0)):.3f}")
    lines.append(f"- clean causal chain 比例：{float(summary.get('clean_causal_chain_ratio', 0.0)):.3f}")
    lines.append(f"- corrected 内部选择性均值：{float(summary.get('corrected_internal_selectivity_mean', 0.0)):.4f}")
    lines.append(f"- corrected 双向局部信号总量均值：{float(summary.get('corrected_total_local_signal_mean', 0.0)):.4f}")
    lines.append(f"- 正确目标奖励效应均值：{float(summary.get('corrected_vs_neutral_right_effect_mean', 0.0)):.4f}")
    lines.append(f"- 错误目标惩罚效应均值：{float(summary.get('punished_vs_neutral_wrong_effect_mean', 0.0)):.4f}")
    lines.append(f"- corrected 选择性 sign test p：{float(summary.get('corrected_selectivity_sign_p', 1.0)):.6f}")
    lines.append(f"- corrected 总信号 sign test p：{float(summary.get('corrected_total_signal_sign_p', 1.0)):.6f}")
    lines.append("")
    lines.append("## 参数")
    lines.append(f"- reward_strength：{reward_strength:.3f}")
    lines.append(f"- punish_strength：{punish_strength:.3f}")
    lines.append(f"- reward_coef：{reward_coef:.3f}")
    lines.append(f"- punish_coef：{punish_coef:.3f}")
    lines.append(f"- alias_ttl：{alias_ttl}")
    lines.append("")
    lines.append("## 图表")
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    lines.append("## Pair 明细")
    lines.append("")
    lines.append("| case | rep | wrong city | right city | corrected selectivity | corrected total signal | corrected bonus | punished penalty | clean |")
    lines.append("| --- | ---: | --- | --- | ---: | ---: | ---: | ---: |")
    for row in pair_rows:
        lines.append(
            f"| {row['case_id']} | {row['replicate']} | {row['city_wrong']} | {row['city_right']} | "
            f"{num(row, 'corrected_internal_selectivity'):.3f} | {num(row, 'corrected_total_local_signal'):.3f} | "
            f"{num(row, 'corrected_vs_neutral_right_effect'):.3f} | "
            f"{num(row, 'punished_vs_neutral_wrong_effect'):.3f} | {int(row.get('supports_clean_causal_chain', 0))} |"
        )
    lines.append("")
    lines.append("## 运行规模")
    lines.append(f"- datasets：{len(datasets)}")
    lines.append(f"- runs：{len(run_infos)}")
    path = REPORT_DIR / f"E04_punish_correction_report_{stamp}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
    probe_rows = build_probe_rows(run_infos)
    pair_rows = build_pair_rows(probe_rows)
    summary = summarize_evidence(pair_rows)
    e01.write_csv(TABLE_DIR / f"e04_punish_correction_probe_rows_{stamp}.csv", probe_rows)
    e01.write_csv(TABLE_DIR / f"e04_punish_correction_pair_rows_{stamp}.csv", pair_rows)
    e01.write_json(TABLE_DIR / f"e04_punish_correction_summary_{stamp}.json", summary)
    write_design_note(REPORT_DIR / "E04_punish_correction_design_logic.md")
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
        "experiment": "E04_punish_correction",
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
            "probe_rows": str(TABLE_DIR / f"e04_punish_correction_probe_rows_{stamp}.csv"),
            "pair_rows": str(TABLE_DIR / f"e04_punish_correction_pair_rows_{stamp}.csv"),
            "summary": str(TABLE_DIR / f"e04_punish_correction_summary_{stamp}.json"),
        },
        "charts": [str(path) for path in charts],
        "report": str(report),
        "design_note": str(REPORT_DIR / "E04_punish_correction_design_logic.md"),
    }
    e01.write_json(MANIFEST_DIR / f"E04_punish_correction_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E04_punish_correction_latest.json", evidence)
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run paper E04 punish-correction experiment.")
    parser.add_argument("--replicates", type=int, default=2)
    parser.add_argument("--families", type=int, default=6)
    parser.add_argument("--reward-strength", type=float, default=0.75)
    parser.add_argument("--punish-strength", type=float, default=0.70)
    parser.add_argument("--reward-coef", type=float, default=0.90)
    parser.add_argument("--punish-coef", type=float, default=0.90)
    parser.add_argument("--alias-ttl", type=int, default=8)
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
        MANIFEST_DIR / f"E04_punish_correction_dataset_manifest_{stamp}.json",
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
    print(f"[E04] generated {len(datasets)} datasets", flush=True)
    if args.make_only:
        return 0

    max_ticks = int(args.max_ticks) if int(args.max_ticks or 0) > 0 else None
    run_infos: list[dict[str, Any]] = []
    analyze_existing_stamp = str(args.analyze_existing_stamp or "").strip()
    if analyze_existing_stamp:
        stamp = analyze_existing_stamp
        for d in datasets:
            run_id = f"paper_e04_{d['case_id']}_{d['branch']}_r{d['replicate']}_{stamp}"
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
