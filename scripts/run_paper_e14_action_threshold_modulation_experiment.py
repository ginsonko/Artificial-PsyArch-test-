from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from _reproduction_paths import AP_ROOT, ARTIFACT_ROOT, ATTACHMENT_ROOT

if str(AP_ROOT) not in sys.path:
    sys.path.insert(0, str(AP_ROOT))

import run_paper_e01_experiment as e01
from action import ActionManager
from emotion import EmotionManager
from innate_script import InnateScriptManager


E14_ROOT = ARTIFACT_ROOT / "E14_action_threshold_modulation"
TABLE_DIR = E14_ROOT / "tables"
CHART_DIR = E14_ROOT / "charts"
REPORT_DIR = E14_ROOT / "reports"
MANIFEST_DIR = E14_ROOT / "manifests"

STAMP_DEFAULT = "e14_final_v1"


BRANCH_ORDER = (
    "baseline",
    "reward_cfs_rwd",
    "expectation_nt_only",
    "pressure_cfs_pun",
    "pressure_nt_only",
    "fixed_reward_control",
    "fixed_pressure_control",
    "local_baseline_fixed",
    "local_reward_drive",
    "local_punish_drive",
    "local_reward_disabled_control",
    "local_punish_disabled_control",
)

BRANCH_LABELS = {
    "baseline": "中性基线",
    "reward_cfs_rwd": "正确/奖励降阈",
    "expectation_nt_only": "期待递质降阈",
    "pressure_cfs_pun": "压力/惩罚升阈",
    "pressure_nt_only": "压力递质升阈",
    "fixed_reward_control": "奖励固定阈值",
    "fixed_pressure_control": "压力固定阈值",
    "local_baseline_fixed": "局部驱动基线",
    "local_reward_drive": "局部奖励增驱动",
    "local_punish_drive": "局部惩罚降驱动",
    "local_reward_disabled_control": "局部奖励禁用",
    "local_punish_disabled_control": "局部惩罚禁用",
}


@dataclass(frozen=True)
class FamilySpec:
    family: str
    target_id: str
    target_display: str
    action_gain: float
    base_threshold: float
    reward_strength: float
    expectation_strength: float
    pressure_strength: float
    global_rwd: float
    global_pun: float
    local_rwd: float
    local_pun: float


FAMILY_SPECS: list[FamilySpec] = [
    FamilySpec("F01", "st_e14_route_01", "行动目标01：查询天气前置确认", 0.310, 1.0, 0.78, 0.82, 0.80, 0.78, 0.82, 0.78, 0.84),
    FamilySpec("F02", "st_e14_route_02", "行动目标02：资料校验后写入", 0.311, 1.0, 0.79, 0.83, 0.81, 0.79, 0.83, 0.79, 0.85),
    FamilySpec("F03", "st_e14_route_03", "行动目标03：本地缓存优先", 0.312, 1.0, 0.80, 0.84, 0.82, 0.80, 0.84, 0.80, 0.86),
    FamilySpec("F04", "st_e14_route_04", "行动目标04：触发回忆核对", 0.313, 1.0, 0.81, 0.85, 0.83, 0.81, 0.85, 0.81, 0.87),
    FamilySpec("F05", "st_e14_route_05", "行动目标05：调用天气工具", 0.314, 1.0, 0.82, 0.86, 0.84, 0.82, 0.86, 0.82, 0.88),
    FamilySpec("F06", "st_e14_route_06", "行动目标06：主动提醒用户", 0.315, 1.0, 0.83, 0.87, 0.85, 0.83, 0.87, 0.83, 0.89),
    FamilySpec("F07", "st_e14_route_07", "行动目标07：继续检索证据", 0.316, 1.0, 0.84, 0.88, 0.86, 0.84, 0.88, 0.84, 0.90),
    FamilySpec("F08", "st_e14_route_08", "行动目标08：暂缓高风险输出", 0.317, 1.0, 0.85, 0.89, 0.87, 0.85, 0.89, 0.85, 0.91),
    FamilySpec("F09", "st_e14_route_09", "行动目标09：补充结构化日志", 0.310, 1.0, 0.86, 0.90, 0.88, 0.86, 0.90, 0.86, 0.92),
    FamilySpec("F10", "st_e14_route_10", "行动目标10：切换聚焦视角", 0.311, 1.0, 0.87, 0.91, 0.89, 0.87, 0.91, 0.87, 0.93),
    FamilySpec("F11", "st_e14_route_11", "行动目标11：等待教师反馈", 0.312, 1.0, 0.88, 0.92, 0.90, 0.88, 0.92, 0.88, 0.94),
    FamilySpec("F12", "st_e14_route_12", "行动目标12：执行安全确认", 0.313, 1.0, 0.89, 0.93, 0.91, 0.89, 0.93, 0.89, 0.95),
]


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dirs() -> None:
    for path in (TABLE_DIR, CHART_DIR, REPORT_DIR, MANIFEST_DIR):
        path.mkdir(parents=True, exist_ok=True)


def mean_or_zero(values: list[float]) -> float:
    clean = [float(x) for x in values if math.isfinite(float(x))]
    return round(statistics.fmean(clean), 8) if clean else 0.0


def sign_test_p_value(wins: int, losses: int) -> float:
    n = int(wins) + int(losses)
    if n <= 0:
        return 1.0
    k = min(int(wins), int(losses))
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return round(min(1.0, 2.0 * tail), 8)


def approx_equal(a: float, b: float, tol: float = 1e-7) -> bool:
    return abs(float(a) - float(b)) <= float(tol)


def first_execution_tick(ticks: list[dict[str, Any]]) -> int:
    for row in ticks:
        if bool(row.get("executed", False)):
            return int(row.get("tick", 0) or 0)
    return 999999


def execution_count(ticks: list[dict[str, Any]]) -> int:
    return sum(1 for row in ticks if bool(row.get("executed", False)))


def make_cfs_signal(spec: FamilySpec, kind: str, strength: float) -> dict[str, Any]:
    return {
        "kind": str(kind),
        "strength": float(strength),
        "scope": "object",
        "target": {
            "target_ref_object_id": spec.target_id,
            "target_ref_object_type": "st",
            "target_item_id": f"item_{spec.target_id}",
            "target_display": spec.target_display,
        },
        "reasons": [f"e14_family:{spec.family}", f"e14_kind:{kind}"],
    }


def branch_setup(spec: FamilySpec, branch: str) -> dict[str, Any]:
    setup: dict[str, Any] = {
        "cfs_signals": [],
        "rwd": 0.0,
        "pun": 0.0,
        "disable_threshold_modulation": False,
        "disable_local_modulation": True,
        "local_map": {},
        "ticks": 8,
        "threshold_branch": True,
    }
    if branch == "reward_cfs_rwd":
        setup["cfs_signals"] = [make_cfs_signal(spec, "correct_event", spec.reward_strength)]
        setup["rwd"] = spec.global_rwd
    elif branch == "expectation_nt_only":
        setup["cfs_signals"] = [make_cfs_signal(spec, "expectation", spec.expectation_strength)]
    elif branch == "pressure_cfs_pun":
        setup["cfs_signals"] = [make_cfs_signal(spec, "pressure", spec.pressure_strength)]
        setup["pun"] = spec.global_pun
    elif branch == "pressure_nt_only":
        setup["cfs_signals"] = [make_cfs_signal(spec, "pressure", spec.pressure_strength)]
    elif branch == "fixed_reward_control":
        setup["cfs_signals"] = [make_cfs_signal(spec, "correct_event", spec.reward_strength)]
        setup["rwd"] = spec.global_rwd
        setup["disable_threshold_modulation"] = True
    elif branch == "fixed_pressure_control":
        setup["cfs_signals"] = [make_cfs_signal(spec, "pressure", spec.pressure_strength)]
        setup["pun"] = spec.global_pun
        setup["disable_threshold_modulation"] = True
    elif branch in {
        "local_baseline_fixed",
        "local_reward_drive",
        "local_punish_drive",
        "local_reward_disabled_control",
        "local_punish_disabled_control",
    }:
        setup["threshold_branch"] = False
        setup["disable_threshold_modulation"] = True
        setup["disable_local_modulation"] = False
        if branch == "local_reward_drive":
            setup["local_map"] = {
                "by_ref": {
                    spec.target_id: {
                        "rwd": spec.local_rwd,
                        "pun": 0.0,
                        "display": spec.target_display,
                        "detail": {"source": "E14_local_reward_drive", "family": spec.family},
                    }
                }
            }
        elif branch == "local_punish_drive":
            setup["local_map"] = {
                "by_ref": {
                    spec.target_id: {
                        "rwd": 0.0,
                        "pun": spec.local_pun,
                        "display": spec.target_display,
                        "detail": {"source": "E14_local_punish_drive", "family": spec.family},
                    }
                }
            }
        elif branch == "local_reward_disabled_control":
            setup["disable_local_modulation"] = True
            setup["local_map"] = {
                "by_ref": {
                    spec.target_id: {
                        "rwd": spec.local_rwd,
                        "pun": 0.0,
                        "display": spec.target_display,
                        "detail": {"source": "E14_local_reward_disabled_control", "family": spec.family},
                    }
                }
            }
        elif branch == "local_punish_disabled_control":
            setup["disable_local_modulation"] = True
            setup["local_map"] = {
                "by_ref": {
                    spec.target_id: {
                        "rwd": 0.0,
                        "pun": spec.local_pun,
                        "display": spec.target_display,
                        "detail": {"source": "E14_local_punish_disabled_control", "family": spec.family},
                    }
                }
            }
    return setup


def run_iesm(cfs_signals: list[dict[str, Any]], *, trace_id: str, tick_id: str) -> dict[str, Any]:
    manager = InnateScriptManager()
    try:
        result = manager.run_tick_rules(
            trace_id=trace_id,
            tick_id=tick_id,
            tick_index=1,
            cfs_signals=cfs_signals,
            state_windows=[],
            context={},
            dry_run=True,
            allowed_phases=["directives"],
        )
        return result.get("data", {}) or {}
    finally:
        manager.close()


def run_emotion(
    *,
    cfs_signals: list[dict[str, Any]],
    emotion_updates: dict[str, float],
    rwd: float,
    pun: float,
    trace_id: str,
    tick_id: str,
) -> dict[str, Any]:
    manager = EmotionManager(
        config_override={
            "cfs_to_nt_source_mode": "iesm_rules",
            "rwd_pun_to_nt_source_mode": "iesm_rules",
        }
    )
    try:
        result = manager.update_emotion_state(
            {
                "cfs_signals": list(cfs_signals or []),
                "emotion_updates": dict(emotion_updates or {}),
                "rwd_pun_override": {
                    "rwd": float(rwd),
                    "pun": float(pun),
                    "source": "E14_controlled_pool_override",
                    "detail": {"purpose": "global reward/punish threshold modulation"},
                },
            },
            trace_id=trace_id,
            tick_id=tick_id,
        )
        return result.get("data", {}) or {}
    finally:
        manager.close()


def make_action_trigger(spec: FamilySpec, branch: str, setup: dict[str, Any]) -> dict[str, Any]:
    params = {
        "target_ref_object_id": spec.target_id,
        "target_ref_object_type": "st",
        "target_item_id": f"item_{spec.target_id}",
        "target_display": spec.target_display,
        "strength": 1.0,
        "focus_boost": 0.9,
        "ttl_ticks": 2,
        "source_kind": "e14_controlled_action_probe",
        "mutex_key": f"e14_mutex_{spec.family}_{branch}",
    }
    if bool(setup.get("disable_threshold_modulation", False)):
        params["disable_threshold_modulation"] = True
    if bool(setup.get("disable_local_modulation", False)):
        params["disable_local_reward_punish_drive_modulation"] = True
    return {
        "action_id": f"e14_{branch}_{spec.family}",
        "action_kind": "attention_focus",
        "gain": float(spec.action_gain),
        "threshold": float(spec.base_threshold),
        "cooldown_ticks": 0,
        "params": params,
        "rule_id": f"e14_controlled_trigger_{branch}",
        "rule_title": "E14 controlled action probe",
        "rule_priority": 80,
    }


def run_action_series(
    *,
    spec: FamilySpec,
    branch: str,
    setup: dict[str, Any],
    emotion_state: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manager = ActionManager(
        config_override={
            "drive_decay_ratio": 1.0,
            "action_fatigue_enabled": False,
            "local_drive_feedback_text_fallback_enabled": False,
            "threshold_scale_by_rwd_pun_enabled": True,
            "local_drive_modulation_by_rwd_pun_enabled": True,
            "max_total_actions_per_tick": 8,
        }
    )
    rows: list[dict[str, Any]] = []
    try:
        for tick in range(1, int(setup.get("ticks", 8)) + 1):
            trigger = make_action_trigger(spec, branch, setup)
            result = manager.run_action_cycle(
                trace_id=f"trace_e14_{spec.family}_{branch}_{tick}",
                tick_id=f"cycle_e14_{spec.family}_{branch}_{tick:04d}",
                tick_index=tick,
                cfs_signals=list(setup.get("cfs_signals", []) or []),
                emotion_state=emotion_state,
                innate_focus_directives=[],
                innate_action_triggers=[trigger],
                memory_activation_snapshot={},
                local_reward_punish_map=dict(setup.get("local_map", {}) or {}),
            )
            data = result.get("data", {}) or {}
            nodes = data.get("nodes", []) or []
            node = nodes[0] if nodes else {}
            executed_rows = [
                row
                for row in (data.get("executed_actions", []) or [])
                if row.get("action_id") == trigger["action_id"] and bool(row.get("success", False))
            ]
            local_mod = node.get("local_drive_modulation", {}) if isinstance(node.get("local_drive_modulation", {}), dict) else {}
            comps = node.get("threshold_components", {}) if isinstance(node.get("threshold_components", {}), dict) else {}
            rows.append(
                {
                    "tick": int(tick),
                    "drive": round(float(node.get("drive", 0.0) or 0.0), 8),
                    "base_threshold": round(float(node.get("base_threshold", 0.0) or 0.0), 8),
                    "threshold_scale": round(float(node.get("threshold_scale", 0.0) or 0.0), 8),
                    "effective_threshold": round(float(node.get("effective_threshold", 0.0) or 0.0), 8),
                    "threshold_delta": round(float(comps.get("threshold_delta", 0.0) or 0.0), 8),
                    "nt_scale_clamped": round(float(comps.get("nt_scale_clamped", 1.0) or 1.0), 8),
                    "rwd_pun_scale_clamped": round(float(comps.get("rwd_pun_scale_clamped", 1.0) or 1.0), 8),
                    "rwd_pun_enabled": bool(comps.get("rwd_pun_enabled", False)),
                    "local_lookup_status": str(local_mod.get("lookup_status", "") or ""),
                    "local_lookup_hit": bool(local_mod.get("lookup_hit", False)),
                    "local_applied": bool(local_mod.get("applied", False)),
                    "local_scale_clamped": round(float(local_mod.get("scale_clamped", 1.0) or 1.0), 8),
                    "local_gain_after": round(float(local_mod.get("gain_after", spec.action_gain) or spec.action_gain), 8),
                    "local_reward_bonus_gain": round(float(local_mod.get("reward_bonus_gain", 0.0) or 0.0), 8),
                    "local_punish_penalty_gain": round(float(local_mod.get("punish_penalty_gain", 0.0) or 0.0), 8),
                    "executed": bool(executed_rows),
                    "executed_count_this_tick": len(executed_rows),
                }
            )
        snapshot = manager.get_runtime_snapshot(trace_id=f"e14_snapshot_{spec.family}_{branch}").get("data", {}) or {}
        return rows, snapshot
    finally:
        manager.close()


def run_case(spec: FamilySpec, branch: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    setup = branch_setup(spec, branch)
    cfs_signals = list(setup.get("cfs_signals", []) or [])
    trace_id = f"trace_e14_{spec.family}_{branch}"
    tick_id = f"cycle_e14_{spec.family}_{branch}_emotion"
    iesm_data = run_iesm(cfs_signals, trace_id=trace_id, tick_id=tick_id)
    directives = iesm_data.get("directives", {}) if isinstance(iesm_data.get("directives", {}), dict) else {}
    emotion_updates = directives.get("emotion_updates", {}) if isinstance(directives.get("emotion_updates", {}), dict) else {}
    iesm_action_triggers = directives.get("action_triggers", []) if isinstance(directives.get("action_triggers", []), list) else []
    emotion_data = run_emotion(
        cfs_signals=cfs_signals,
        emotion_updates=emotion_updates,
        rwd=float(setup.get("rwd", 0.0) or 0.0),
        pun=float(setup.get("pun", 0.0) or 0.0),
        trace_id=trace_id,
        tick_id=tick_id,
    )
    tick_rows, action_snapshot = run_action_series(spec=spec, branch=branch, setup=setup, emotion_state=emotion_data)
    first_tick = first_execution_tick(tick_rows)
    exec_count = execution_count(tick_rows)
    tick1 = tick_rows[0] if tick_rows else {}
    nt_before = emotion_data.get("nt_state_before", {}) if isinstance(emotion_data.get("nt_state_before", {}), dict) else {}
    nt_after = emotion_data.get("nt_state_after", {}) if isinstance(emotion_data.get("nt_state_after", {}), dict) else {}
    deltas = emotion_data.get("deltas", {}) if isinstance(emotion_data.get("deltas", {}), dict) else {}
    triggered_rule_ids = [str(row.get("rule_id", "") or "") for row in (iesm_data.get("triggered_rules", []) or []) if isinstance(row, dict)]

    case_row = {
        "family": spec.family,
        "branch": branch,
        "branch_label": BRANCH_LABELS[branch],
        "target_id": spec.target_id,
        "target_display": spec.target_display,
        "action_gain": float(spec.action_gain),
        "base_threshold": float(spec.base_threshold),
        "cfs_kinds": ",".join(str(sig.get("kind", "")) for sig in cfs_signals),
        "cfs_strength_sum": round(sum(float(sig.get("strength", 0.0) or 0.0) for sig in cfs_signals), 8),
        "global_rwd": round(float(setup.get("rwd", 0.0) or 0.0), 8),
        "global_pun": round(float(setup.get("pun", 0.0) or 0.0), 8),
        "disable_threshold_modulation": bool(setup.get("disable_threshold_modulation", False)),
        "disable_local_modulation": bool(setup.get("disable_local_modulation", False)),
        "iesm_emotion_update_count": len(emotion_updates),
        "iesm_emotion_update_abs_total": round(sum(abs(float(v or 0.0)) for v in emotion_updates.values()), 8),
        "iesm_action_trigger_count": len(iesm_action_triggers),
        "iesm_triggered_rule_ids": ";".join(triggered_rule_ids),
        "nt_before_DA": round(float(nt_before.get("DA", 0.0) or 0.0), 8),
        "nt_after_DA": round(float(nt_after.get("DA", 0.0) or 0.0), 8),
        "nt_before_COR": round(float(nt_before.get("COR", 0.0) or 0.0), 8),
        "nt_after_COR": round(float(nt_after.get("COR", 0.0) or 0.0), 8),
        "nt_before_FOC": round(float(nt_before.get("FOC", 0.0) or 0.0), 8),
        "nt_after_FOC": round(float(nt_after.get("FOC", 0.0) or 0.0), 8),
        "nt_delta_script_json": json.dumps(deltas.get("from_script", {}) or {}, ensure_ascii=False, sort_keys=True),
        "rwd_pun_snapshot_json": json.dumps(emotion_data.get("rwd_pun_snapshot", {}) or {}, ensure_ascii=False, sort_keys=True),
        "tick1_drive": tick1.get("drive", 0.0),
        "tick1_effective_threshold": tick1.get("effective_threshold", 0.0),
        "tick1_threshold_scale": tick1.get("threshold_scale", 0.0),
        "tick1_threshold_delta": tick1.get("threshold_delta", 0.0),
        "tick1_nt_scale_clamped": tick1.get("nt_scale_clamped", 1.0),
        "tick1_rwd_pun_scale_clamped": tick1.get("rwd_pun_scale_clamped", 1.0),
        "tick1_local_lookup_status": tick1.get("local_lookup_status", ""),
        "tick1_local_lookup_hit": int(bool(tick1.get("local_lookup_hit", False))),
        "tick1_local_applied": int(bool(tick1.get("local_applied", False))),
        "tick1_local_scale_clamped": tick1.get("local_scale_clamped", 1.0),
        "tick1_local_gain_after": tick1.get("local_gain_after", spec.action_gain),
        "tick1_local_reward_bonus_gain": tick1.get("local_reward_bonus_gain", 0.0),
        "tick1_local_punish_penalty_gain": tick1.get("local_punish_penalty_gain", 0.0),
        "first_execution_tick": int(first_tick),
        "execution_count": int(exec_count),
        "tick_series_json": json.dumps(tick_rows, ensure_ascii=False),
        "action_snapshot_node_count": int(((action_snapshot.get("stats", {}) or {}).get("node_count", 0) or 0)),
    }
    return case_row, [
        {
            "family": spec.family,
            "branch": branch,
            "tick": row["tick"],
            "drive": row["drive"],
            "effective_threshold": row["effective_threshold"],
            "threshold_scale": row["threshold_scale"],
            "local_gain_after": row["local_gain_after"],
            "local_scale_clamped": row["local_scale_clamped"],
            "executed": int(bool(row["executed"])),
        }
        for row in tick_rows
    ]


def build_family_rows(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_family: dict[str, dict[str, dict[str, Any]]] = {}
    for row in case_rows:
        by_family.setdefault(str(row["family"]), {})[str(row["branch"])] = row

    family_rows: list[dict[str, Any]] = []
    for family, rows in sorted(by_family.items()):
        b = rows["baseline"]
        reward = rows["reward_cfs_rwd"]
        expect = rows["expectation_nt_only"]
        pressure = rows["pressure_cfs_pun"]
        pressure_nt = rows["pressure_nt_only"]
        fixed_reward = rows["fixed_reward_control"]
        fixed_pressure = rows["fixed_pressure_control"]
        local_base = rows["local_baseline_fixed"]
        local_reward = rows["local_reward_drive"]
        local_punish = rows["local_punish_drive"]
        local_reward_disabled = rows["local_reward_disabled_control"]
        local_punish_disabled = rows["local_punish_disabled_control"]

        baseline_threshold = float(b["tick1_effective_threshold"])
        baseline_first = int(b["first_execution_tick"])
        local_base_drive = float(local_base["tick1_drive"])
        local_base_first = int(local_base["first_execution_tick"])
        base_threshold = float(b["base_threshold"])

        reward_threshold_pass = (
            float(reward["tick1_effective_threshold"]) < baseline_threshold - 0.12
            and int(reward["first_execution_tick"]) < baseline_first
            and int(reward["execution_count"]) > int(b["execution_count"])
            and float(reward["iesm_emotion_update_abs_total"]) > 0.0
            and int(reward["iesm_action_trigger_count"]) >= 1
            and float(reward["nt_after_DA"]) > float(reward["nt_before_DA"])
            and float(reward["tick1_rwd_pun_scale_clamped"]) < 1.0
        )
        expectation_nt_pass = (
            float(expect["tick1_effective_threshold"]) < baseline_threshold - 0.02
            and int(expect["first_execution_tick"]) <= baseline_first
            and float(expect["global_rwd"]) == 0.0
            and float(expect["global_pun"]) == 0.0
            and float(expect["iesm_emotion_update_abs_total"]) > 0.0
            and int(expect["iesm_action_trigger_count"]) >= 1
            and float(expect["nt_after_DA"]) > float(expect["nt_before_DA"])
            and approx_equal(float(expect["tick1_rwd_pun_scale_clamped"]), 1.0, 1e-7)
        )
        pressure_threshold_pass = (
            float(pressure["tick1_effective_threshold"]) > baseline_threshold + 0.20
            and int(pressure["first_execution_tick"]) > baseline_first
            and int(pressure["execution_count"]) <= int(b["execution_count"])
            and float(pressure["iesm_emotion_update_abs_total"]) > 0.0
            and int(pressure["iesm_action_trigger_count"]) >= 1
            and float(pressure["nt_after_COR"]) > float(pressure["nt_before_COR"])
            and float(pressure["tick1_rwd_pun_scale_clamped"]) > 1.0
        )
        pressure_nt_pass = (
            float(pressure_nt["tick1_effective_threshold"]) > baseline_threshold + 0.02
            and float(pressure_nt["global_rwd"]) == 0.0
            and float(pressure_nt["global_pun"]) == 0.0
            and float(pressure_nt["iesm_emotion_update_abs_total"]) > 0.0
            and int(pressure_nt["iesm_action_trigger_count"]) >= 1
            and float(pressure_nt["nt_after_COR"]) > float(pressure_nt["nt_before_COR"])
            and approx_equal(float(pressure_nt["tick1_rwd_pun_scale_clamped"]), 1.0, 1e-7)
        )
        fixed_reward_pass = (
            bool(fixed_reward["disable_threshold_modulation"])
            and approx_equal(float(fixed_reward["tick1_effective_threshold"]), base_threshold, 1e-7)
            and float(fixed_reward["tick1_effective_threshold"]) > float(reward["tick1_effective_threshold"]) + 0.12
        )
        fixed_pressure_pass = (
            bool(fixed_pressure["disable_threshold_modulation"])
            and approx_equal(float(fixed_pressure["tick1_effective_threshold"]), base_threshold, 1e-7)
            and float(fixed_pressure["tick1_effective_threshold"]) < float(pressure["tick1_effective_threshold"]) - 0.20
        )
        local_reward_pass = (
            approx_equal(float(local_reward["tick1_effective_threshold"]), base_threshold, 1e-7)
            and int(local_reward["tick1_local_lookup_hit"]) == 1
            and int(local_reward["tick1_local_applied"]) == 1
            and float(local_reward["tick1_local_scale_clamped"]) > 1.0
            and float(local_reward["tick1_drive"]) > local_base_drive + 0.08
            and int(local_reward["first_execution_tick"]) < local_base_first
            and int(local_reward["execution_count"]) > int(local_base["execution_count"])
        )
        local_punish_pass = (
            approx_equal(float(local_punish["tick1_effective_threshold"]), base_threshold, 1e-7)
            and int(local_punish["tick1_local_lookup_hit"]) == 1
            and int(local_punish["tick1_local_applied"]) == 1
            and float(local_punish["tick1_local_scale_clamped"]) < 1.0
            and float(local_punish["tick1_drive"]) < local_base_drive - 0.08
            and int(local_punish["first_execution_tick"]) > local_base_first
            and int(local_punish["execution_count"]) < int(local_base["execution_count"])
        )
        local_disabled_pass = (
            approx_equal(float(local_reward_disabled["tick1_effective_threshold"]), base_threshold, 1e-7)
            and approx_equal(float(local_punish_disabled["tick1_effective_threshold"]), base_threshold, 1e-7)
            and int(local_reward_disabled["tick1_local_applied"]) == 0
            and int(local_punish_disabled["tick1_local_applied"]) == 0
            and approx_equal(float(local_reward_disabled["tick1_drive"]), local_base_drive, 1e-7)
            and approx_equal(float(local_punish_disabled["tick1_drive"]), local_base_drive, 1e-7)
        )
        all_ok = all(
            [
                reward_threshold_pass,
                expectation_nt_pass,
                pressure_threshold_pass,
                pressure_nt_pass,
                fixed_reward_pass,
                fixed_pressure_pass,
                local_reward_pass,
                local_punish_pass,
                local_disabled_pass,
            ]
        )
        family_rows.append(
            {
                "family": family,
                "baseline_threshold": round(baseline_threshold, 8),
                "baseline_first_execution_tick": baseline_first,
                "reward_threshold": reward["tick1_effective_threshold"],
                "reward_first_execution_tick": reward["first_execution_tick"],
                "expectation_threshold": expect["tick1_effective_threshold"],
                "pressure_threshold": pressure["tick1_effective_threshold"],
                "pressure_first_execution_tick": pressure["first_execution_tick"],
                "pressure_nt_threshold": pressure_nt["tick1_effective_threshold"],
                "local_base_drive": local_base["tick1_drive"],
                "local_reward_drive": local_reward["tick1_drive"],
                "local_punish_drive": local_punish["tick1_drive"],
                "local_reward_first_execution_tick": local_reward["first_execution_tick"],
                "local_punish_first_execution_tick": local_punish["first_execution_tick"],
                "reward_threshold_pass": int(reward_threshold_pass),
                "expectation_nt_pass": int(expectation_nt_pass),
                "pressure_threshold_pass": int(pressure_threshold_pass),
                "pressure_nt_pass": int(pressure_nt_pass),
                "fixed_reward_pass": int(fixed_reward_pass),
                "fixed_pressure_pass": int(fixed_pressure_pass),
                "local_reward_pass": int(local_reward_pass),
                "local_punish_pass": int(local_punish_pass),
                "local_disabled_pass": int(local_disabled_pass),
                "all_ok": int(all_ok),
            }
        )
    return family_rows


def summarize(case_rows: list[dict[str, Any]], family_rows: list[dict[str, Any]]) -> dict[str, Any]:
    def ratio(field: str) -> float:
        return round(sum(int(row.get(field, 0) or 0) for row in family_rows) / max(1, len(family_rows)), 8)

    all_ok_count = sum(int(row.get("all_ok", 0) or 0) for row in family_rows)
    family_count = len(family_rows)
    summary = {
        "experiment_id": "E14",
        "stamp": "",
        "family_count": int(family_count),
        "case_count": int(len(case_rows)),
        "all_ok_family_count": int(all_ok_count),
        "all_ok_ratio": ratio("all_ok"),
        "all_ok_sign_p": sign_test_p_value(all_ok_count, family_count - all_ok_count),
        "reward_threshold_pass_ratio": ratio("reward_threshold_pass"),
        "expectation_nt_pass_ratio": ratio("expectation_nt_pass"),
        "pressure_threshold_pass_ratio": ratio("pressure_threshold_pass"),
        "pressure_nt_pass_ratio": ratio("pressure_nt_pass"),
        "fixed_reward_pass_ratio": ratio("fixed_reward_pass"),
        "fixed_pressure_pass_ratio": ratio("fixed_pressure_pass"),
        "local_reward_pass_ratio": ratio("local_reward_pass"),
        "local_punish_pass_ratio": ratio("local_punish_pass"),
        "local_disabled_pass_ratio": ratio("local_disabled_pass"),
        "baseline_threshold_mean": mean_or_zero([float(row["baseline_threshold"]) for row in family_rows]),
        "reward_threshold_mean": mean_or_zero([float(row["reward_threshold"]) for row in family_rows]),
        "expectation_threshold_mean": mean_or_zero([float(row["expectation_threshold"]) for row in family_rows]),
        "pressure_threshold_mean": mean_or_zero([float(row["pressure_threshold"]) for row in family_rows]),
        "pressure_nt_threshold_mean": mean_or_zero([float(row["pressure_nt_threshold"]) for row in family_rows]),
        "local_base_drive_mean": mean_or_zero([float(row["local_base_drive"]) for row in family_rows]),
        "local_reward_drive_mean": mean_or_zero([float(row["local_reward_drive"]) for row in family_rows]),
        "local_punish_drive_mean": mean_or_zero([float(row["local_punish_drive"]) for row in family_rows]),
        "baseline_first_execution_tick_mean": mean_or_zero([float(row["baseline_first_execution_tick"]) for row in family_rows]),
        "reward_first_execution_tick_mean": mean_or_zero([float(row["reward_first_execution_tick"]) for row in family_rows]),
        "pressure_first_execution_tick_mean": mean_or_zero([float(row["pressure_first_execution_tick"]) for row in family_rows]),
        "local_reward_first_execution_tick_mean": mean_or_zero([float(row["local_reward_first_execution_tick"]) for row in family_rows]),
        "local_punish_first_execution_tick_mean": mean_or_zero([float(row["local_punish_first_execution_tick"]) for row in family_rows]),
    }
    summary["reward_threshold_delta_vs_baseline_mean"] = round(
        float(summary["reward_threshold_mean"]) - float(summary["baseline_threshold_mean"]), 8
    )
    summary["pressure_threshold_delta_vs_baseline_mean"] = round(
        float(summary["pressure_threshold_mean"]) - float(summary["baseline_threshold_mean"]), 8
    )
    summary["local_reward_drive_delta_vs_baseline_mean"] = round(
        float(summary["local_reward_drive_mean"]) - float(summary["local_base_drive_mean"]), 8
    )
    summary["local_punish_drive_delta_vs_baseline_mean"] = round(
        float(summary["local_punish_drive_mean"]) - float(summary["local_base_drive_mean"]), 8
    )
    summary["support_level"] = (
        "strong_evidence"
        if family_count >= 12
        and summary["all_ok_ratio"] >= 1.0
        and summary["all_ok_sign_p"] <= 0.001
        else "insufficient"
    )
    return summary


def make_charts(case_rows: list[dict[str, Any]], family_rows: list[dict[str, Any]], tick_rows: list[dict[str, Any]], summary: dict[str, Any], stamp: str) -> list[Path]:
    plt = e01.setup_matplotlib()
    charts: list[Path] = []

    threshold_path = CHART_DIR / f"e14_threshold_modulation_{stamp}.png"
    fig, ax = plt.subplots(figsize=(10.8, 5.6), dpi=160)
    labels = ["中性基线", "正确/奖励", "期待NT", "压力/惩罚", "压力NT", "奖励固定", "压力固定"]
    values = [
        float(summary.get("baseline_threshold_mean", 0.0)),
        float(summary.get("reward_threshold_mean", 0.0)),
        float(summary.get("expectation_threshold_mean", 0.0)),
        float(summary.get("pressure_threshold_mean", 0.0)),
        float(summary.get("pressure_nt_threshold_mean", 0.0)),
        1.0,
        1.0,
    ]
    colors = ["#64748b", "#2563eb", "#0891b2", "#dc2626", "#f97316", "#94a3b8", "#94a3b8"]
    ax.bar(labels, values, color=colors, alpha=0.86)
    ax.axhline(float(summary.get("baseline_threshold_mean", 0.0)), color="#0f172a", linewidth=1.2, linestyle="--", alpha=0.55)
    ax.set_ylabel("第1 tick 实时行动阈值")
    ax.set_title("E14 CFS/NT 与奖惩状态对行动阈值的方向性调制")
    ax.tick_params(axis="x", rotation=18)
    for idx, value in enumerate(values):
        ax.text(idx, value + 0.025, f"{value:.3f}", ha="center", va="bottom", fontsize=9)
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    fig.savefig(threshold_path, bbox_inches="tight")
    plt.close(fig)
    charts.append(threshold_path)

    timing_path = CHART_DIR / f"e14_execution_timing_{stamp}.png"
    fig, ax = plt.subplots(figsize=(10.6, 5.2), dpi=160)
    labels = ["中性基线", "正确/奖励", "压力/惩罚", "局部奖励", "局部惩罚"]
    values = [
        float(summary.get("baseline_first_execution_tick_mean", 0.0)),
        float(summary.get("reward_first_execution_tick_mean", 0.0)),
        float(summary.get("pressure_first_execution_tick_mean", 0.0)),
        float(summary.get("local_reward_first_execution_tick_mean", 0.0)),
        float(summary.get("local_punish_first_execution_tick_mean", 0.0)),
    ]
    ax.bar(labels, values, color=["#64748b", "#2563eb", "#dc2626", "#16a34a", "#f97316"], alpha=0.84)
    ax.set_ylabel("首次执行 tick（越小越早）")
    ax.set_title("E14 行动触发时机随阈值与局部驱动改变")
    for idx, value in enumerate(values):
        ax.text(idx, value + 0.08, f"{value:.2f}", ha="center", va="bottom", fontsize=9)
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    fig.savefig(timing_path, bbox_inches="tight")
    plt.close(fig)
    charts.append(timing_path)

    drive_path = CHART_DIR / f"e14_local_drive_{stamp}.png"
    fig, ax = plt.subplots(figsize=(9.8, 5.0), dpi=160)
    labels = ["局部基线", "局部奖励", "局部惩罚"]
    values = [
        float(summary.get("local_base_drive_mean", 0.0)),
        float(summary.get("local_reward_drive_mean", 0.0)),
        float(summary.get("local_punish_drive_mean", 0.0)),
    ]
    ax.bar(labels, values, color=["#64748b", "#16a34a", "#f97316"], alpha=0.86)
    ax.set_ylabel("第1 tick 行动驱动力")
    ax.set_title("E14 同目标局部奖惩对本轮驱动增益的调制")
    for idx, value in enumerate(values):
        ax.text(idx, value + 0.012, f"{value:.3f}", ha="center", va="bottom", fontsize=9)
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    fig.savefig(drive_path, bbox_inches="tight")
    plt.close(fig)
    charts.append(drive_path)

    family_path = CHART_DIR / f"e14_family_pass_matrix_{stamp}.png"
    fig, ax = plt.subplots(figsize=(11.4, 5.2), dpi=160)
    fields = [
        "reward_threshold_pass",
        "expectation_nt_pass",
        "pressure_threshold_pass",
        "pressure_nt_pass",
        "fixed_reward_pass",
        "fixed_pressure_pass",
        "local_reward_pass",
        "local_punish_pass",
        "local_disabled_pass",
    ]
    matrix = [[int(row.get(field, 0) or 0) for field in fields] for row in family_rows]
    ax.imshow(matrix, vmin=0, vmax=1, cmap="YlGnBu", aspect="auto")
    ax.set_yticks(list(range(len(family_rows))))
    ax.set_yticklabels([row["family"] for row in family_rows])
    ax.set_xticks(list(range(len(fields))))
    ax.set_xticklabels(["奖励阈", "期待NT", "压力阈", "压力NT", "奖固", "压固", "局奖", "局惩", "禁用"], rotation=25, ha="right")
    ax.set_title("E14 family 级强证据判据矩阵")
    for y, row in enumerate(matrix):
        for x, value in enumerate(row):
            ax.text(x, y, str(value), ha="center", va="center", fontsize=8, color="#0f172a")
    fig.tight_layout()
    fig.savefig(family_path, bbox_inches="tight")
    plt.close(fig)
    charts.append(family_path)

    curve_path = CHART_DIR / f"e14_drive_threshold_curves_{stamp}.png"
    fig, ax = plt.subplots(figsize=(11.2, 5.8), dpi=160)
    sample_family = "F01"
    plot_branches = ["baseline", "reward_cfs_rwd", "pressure_cfs_pun", "local_reward_drive", "local_punish_drive"]
    branch_colors = {
        "baseline": "#64748b",
        "reward_cfs_rwd": "#2563eb",
        "pressure_cfs_pun": "#dc2626",
        "local_reward_drive": "#16a34a",
        "local_punish_drive": "#f97316",
    }
    for branch in plot_branches:
        rows = [row for row in tick_rows if row.get("family") == sample_family and row.get("branch") == branch]
        rows.sort(key=lambda row: int(row.get("tick", 0) or 0))
        xs = [int(row["tick"]) for row in rows]
        drive = [float(row["drive"]) for row in rows]
        threshold = [float(row["effective_threshold"]) for row in rows]
        ax.plot(xs, drive, marker="o", linewidth=2.0, color=branch_colors[branch], label=f"{BRANCH_LABELS[branch]} drive")
        ax.plot(xs, threshold, linewidth=1.2, color=branch_colors[branch], linestyle="--", alpha=0.70)
    ax.set_xlabel("tick")
    ax.set_ylabel("drive / effective threshold")
    ax.set_title("E14 F01 样例：驱动力曲线与实时阈值")
    ax.legend(ncol=2, fontsize=8)
    ax.grid(alpha=0.22)
    fig.tight_layout()
    fig.savefig(curve_path, bbox_inches="tight")
    plt.close(fig)
    charts.append(curve_path)

    return charts


def write_design_note(path: Path) -> None:
    lines = [
        "# E14 CFS/NT 对行动阈值调制实验设计说明",
        "",
        "## 最小命题",
        "",
        "当前 AP 原型中的认知感受、情绪递质和奖惩状态能够通过可审计字段改变行动管理器中的实时阈值、局部驱动增益和行动触发时机。",
        "",
        "## 收窄边界",
        "",
        "- 本实验不证明系统已经形成完整的自主规划能力。",
        "- 本实验不以自然语言解释评分为判据。",
        "- 本实验只验证 CFS -> IESM -> EMgr/NT -> ActionManager 的白箱链路，以及局部奖惩 -> drive 的同目标塑形链路。",
        "",
        "## 数据集构造",
        "",
        "每个 family 使用同一行动目标、同一基准阈值和近似一致的弱行动增益。分支只改变认知感受、全局奖惩、阈值开关或局部奖惩映射。这样可以排除文本差异、行动器差异和目标差异造成的混淆。",
        "",
        "## 强证据判据",
        "",
        "奖励/正确事件必须降低阈值并提前执行；期待必须在没有全局奖惩的情况下通过 NT 单独降低阈值；压力/惩罚必须提高阈值并延后执行；压力 NT 单独也必须提高阈值；固定阈值分支必须把同样的 CFS/奖惩影响压回基准阈值；局部奖励必须提高同目标 drive，局部惩罚必须降低同目标 drive，禁用局部调制时必须回到局部基线。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    *,
    case_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    tick_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    charts: list[Path],
    whitebox: dict[str, Any],
    stamp: str,
) -> Path:
    lines = [
        f"# E14 CFS/NT 对行动阈值调制实验报告（{stamp}）",
        "",
        "## 核心结论",
        "",
        f"- 支持等级：**{summary.get('support_level', 'unknown')}**",
        f"- family 数：{int(summary.get('family_count', 0))}",
        f"- case 数：{int(summary.get('case_count', 0))}",
        f"- family 级整体通过比例：{summary.get('all_ok_ratio', 0.0):.3f}",
        f"- family 级符号检验 p 值：{summary.get('all_ok_sign_p', 1.0):.8f}",
        f"- 阈值均值：基线 {summary.get('baseline_threshold_mean', 0.0):.3f}，奖励 {summary.get('reward_threshold_mean', 0.0):.3f}，期待 NT {summary.get('expectation_threshold_mean', 0.0):.3f}，压力 {summary.get('pressure_threshold_mean', 0.0):.3f}，压力 NT {summary.get('pressure_nt_threshold_mean', 0.0):.3f}",
        f"- 局部驱动均值：基线 {summary.get('local_base_drive_mean', 0.0):.3f}，奖励 {summary.get('local_reward_drive_mean', 0.0):.3f}，惩罚 {summary.get('local_punish_drive_mean', 0.0):.3f}",
        "",
        "## 正文可使用的最小命题",
        "",
        "在当前 AP 原型中，认知感受可以经由先天规则转化为情绪递质更新，递质状态与全局奖惩状态共同改变行动节点的实时阈值；同一目标对象上的局部奖励或惩罚信号则改变该行动节点本轮获得的驱动力。两条链路都能进一步改变首次执行时机。",
        "",
        "## family 级通过情况",
        "",
        "| family | 奖励阈值 | 期待NT | 压力阈值 | 压力NT | 奖励固定 | 压力固定 | 局部奖 | 局部惩 | 禁用 | all_ok |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in family_rows:
        lines.append(
            f"| {row['family']} | {int(row['reward_threshold_pass'])} | {int(row['expectation_nt_pass'])} | "
            f"{int(row['pressure_threshold_pass'])} | {int(row['pressure_nt_pass'])} | {int(row['fixed_reward_pass'])} | "
            f"{int(row['fixed_pressure_pass'])} | {int(row['local_reward_pass'])} | {int(row['local_punish_pass'])} | "
            f"{int(row['local_disabled_pass'])} | {int(row['all_ok'])} |"
        )
    lines.extend(["", "## 白箱样例", ""])
    for key in ["baseline", "reward_cfs_rwd", "pressure_cfs_pun", "local_reward_drive", "local_punish_drive"]:
        row = whitebox.get(key, {}) or {}
        lines.append(
            f"- {BRANCH_LABELS[key]}：family `{row.get('family', '')}`，第1 tick 阈值={float(row.get('tick1_effective_threshold', 0.0)):.6f}，"
            f"第1 tick drive={float(row.get('tick1_drive', 0.0)):.6f}，首次执行 tick={row.get('first_execution_tick', '')}，"
            f"IESM emotion_update_abs_total={float(row.get('iesm_emotion_update_abs_total', 0.0)):.6f}，"
            f"local_scale={float(row.get('tick1_local_scale_clamped', 1.0)):.6f}。"
        )
    lines.extend(["", "## 图表", ""])
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    report = REPORT_DIR / f"E14_action_threshold_modulation_report_{stamp}.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def run_experiment(*, stamp: str, family_count: int) -> dict[str, Any]:
    ensure_dirs()
    specs = FAMILY_SPECS[: max(1, min(int(family_count), len(FAMILY_SPECS)))]
    case_rows: list[dict[str, Any]] = []
    tick_rows: list[dict[str, Any]] = []
    for spec in specs:
        for branch in BRANCH_ORDER:
            case_row, branch_tick_rows = run_case(spec, branch)
            case_rows.append(case_row)
            tick_rows.extend(branch_tick_rows)
    case_rows.sort(key=lambda row: (str(row["family"]), BRANCH_ORDER.index(str(row["branch"]))))
    tick_rows.sort(key=lambda row: (str(row["family"]), BRANCH_ORDER.index(str(row["branch"])), int(row["tick"])))
    family_rows = build_family_rows(case_rows)
    summary = summarize(case_rows, family_rows)
    summary["stamp"] = stamp
    charts = make_charts(case_rows=case_rows, family_rows=family_rows, tick_rows=tick_rows, summary=summary, stamp=stamp)
    design_note = REPORT_DIR / "E14_action_threshold_modulation_design_logic.md"
    write_design_note(design_note)
    whitebox = {
        branch: next((row for row in case_rows if str(row.get("family", "")) == "F01" and str(row.get("branch", "")) == branch), {})
        for branch in BRANCH_ORDER
    }
    report = write_report(
        case_rows=case_rows,
        family_rows=family_rows,
        tick_rows=tick_rows,
        summary=summary,
        charts=charts,
        whitebox=whitebox,
        stamp=stamp,
    )
    case_csv = TABLE_DIR / f"e14_action_threshold_modulation_case_rows_{stamp}.csv"
    tick_csv = TABLE_DIR / f"e14_action_threshold_modulation_tick_rows_{stamp}.csv"
    family_csv = TABLE_DIR / f"e14_action_threshold_modulation_family_rows_{stamp}.csv"
    summary_json = TABLE_DIR / f"e14_action_threshold_modulation_summary_{stamp}.json"
    whitebox_json = TABLE_DIR / f"e14_action_threshold_modulation_whitebox_{stamp}.json"
    e01.write_csv(case_csv, case_rows)
    e01.write_csv(tick_csv, tick_rows)
    e01.write_csv(family_csv, family_rows)
    e01.write_json(summary_json, summary)
    e01.write_json(whitebox_json, whitebox)
    evidence = {
        "experiment_id": "E14",
        "stamp": stamp,
        "support_level": summary.get("support_level", "unknown"),
        "summary": summary,
        "artifacts": {
            "case_rows": str(case_csv),
            "tick_rows": str(tick_csv),
            "family_rows": str(family_csv),
            "summary": str(summary_json),
            "whitebox": str(whitebox_json),
            "report": str(report),
            "design_note": str(design_note),
            "charts": [str(path) for path in charts],
        },
    }
    e01.write_json(MANIFEST_DIR / f"E14_action_threshold_modulation_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E14_action_threshold_modulation_latest.json", evidence)
    return evidence


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper E14 CFS/NT action threshold modulation experiment.")
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
                "summary": evidence["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
