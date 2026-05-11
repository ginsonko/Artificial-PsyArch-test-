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

ROOT = Path(__file__).resolve().parent
AP_ROOT = ROOT / "Artificial-PsyArch"
if str(AP_ROOT) not in sys.path:
    sys.path.insert(0, str(AP_ROOT))

import run_paper_e01_experiment as e01
from observatory.experiment import auto_tuner


ARTIFACT_ROOT = ROOT / "docs" / "paper_artifacts_2026-05-11"
E15_ROOT = ARTIFACT_ROOT / "E15_auto_tuner_stability"
TABLE_DIR = E15_ROOT / "tables"
CHART_DIR = E15_ROOT / "charts"
REPORT_DIR = E15_ROOT / "reports"
MANIFEST_DIR = E15_ROOT / "manifests"

STAMP_DEFAULT = "e15_final_v1"

WINDOW_TICKS = 5

BRANCH_ORDER = (
    "healthy_control",
    "endogenous_silent",
    "attention_overheat",
    "ev_propagation_thin",
    "ev_induction_thin",
    "ev_retention_thin",
    "ev_saturated_retention",
    "disabled_control",
)

BRANCH_LABELS = {
    "healthy_control": "健康对照",
    "endogenous_silent": "沉寂保活",
    "attention_overheat": "注意力过热",
    "ev_propagation_thin": "EV传播偏薄",
    "ev_induction_thin": "ER诱发偏薄",
    "ev_retention_thin": "EV保留偏薄",
    "ev_saturated_retention": "传播饱和转保留",
    "disabled_control": "关闭调参",
}


@dataclass(frozen=True)
class FamilySpec:
    family: str
    internal_low: float
    external_ref: float
    pool_items: float
    cam_hot: float
    ev_ratio_low: float
    er_total: float
    ev_total: float


FAMILY_SPECS: list[FamilySpec] = [
    FamilySpec("F01", 20.0, 60.0, 70.0, 22.0, 0.55, 120.0, 66.0),
    FamilySpec("F02", 21.0, 61.0, 72.0, 23.0, 0.56, 121.0, 67.8),
    FamilySpec("F03", 22.0, 62.0, 74.0, 24.0, 0.57, 122.0, 69.5),
    FamilySpec("F04", 23.0, 63.0, 76.0, 25.0, 0.58, 123.0, 71.3),
    FamilySpec("F05", 24.0, 64.0, 78.0, 22.5, 0.59, 124.0, 73.2),
    FamilySpec("F06", 25.0, 65.0, 80.0, 23.5, 0.60, 125.0, 75.0),
    FamilySpec("F07", 20.5, 66.0, 82.0, 24.5, 0.55, 126.0, 69.3),
    FamilySpec("F08", 21.5, 67.0, 84.0, 25.5, 0.56, 127.0, 71.1),
    FamilySpec("F09", 22.5, 68.0, 86.0, 22.2, 0.57, 128.0, 73.0),
    FamilySpec("F10", 23.5, 69.0, 88.0, 23.2, 0.58, 129.0, 74.8),
    FamilySpec("F11", 24.5, 70.0, 90.0, 24.2, 0.59, 130.0, 76.7),
    FamilySpec("F12", 25.5, 71.0, 92.0, 25.2, 0.60, 131.0, 78.6),
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


def make_tuner(*, enabled: bool, ev_balance_enabled: bool = True) -> auto_tuner.AutoTuner:
    tuner = auto_tuner.AutoTuner.__new__(auto_tuner.AutoTuner)
    tuner.enabled = bool(enabled)
    tuner.enable_short_term = bool(enabled)
    tuner.enable_long_term = False
    tuner.cfg = auto_tuner.AutoTunerConfig(
        enabled=bool(enabled),
        enable_short_term=bool(enabled),
        enable_long_term=False,
        enable_ev_er_ratio_tuning=bool(ev_balance_enabled),
        enable_memory_feedback_tuning=False,
        short_window_ticks=WINDOW_TICKS,
        decision_cooldown_ticks=0,
        max_param_updates_per_tick=10,
        persist_overrides=False,
        param_backoff_enabled=False,
    )
    tuner.history = []
    tuner.last_decision_tick = -100000
    tuner.last_param_tick = {}
    tuner.param_backoff = {}
    tuner.disabled_rule_ids = set()
    tuner.protected_rule_ids = set()
    tuner.spec_by_id = {}
    tuner.catalog_specs = []
    tuner.custom_rules = []
    tuner.rule_health = {}
    tuner.active_trials = []
    tuner.trial_history = []
    tuner.last_applied_updates = []
    tuner.rule_observations = []
    tuner.observation_history = []
    tuner.observation_review_history = []
    tuner.last_observation_review = {}
    tuner.last_short_term_snapshots = {}
    tuner.last_long_term_snapshots = {}
    tuner.persisted_params = {}
    tuner.runtime_params = {
        "state_pool.default_er_decay_ratio": 0.960,
        "state_pool.default_ev_decay_ratio": 0.965,
        "state_pool.soft_capacity_start_items": 160.0,
        "state_pool.soft_capacity_full_items": 360.0,
        "hdb.internal_resolution_max_structures_per_tick": 4.0,
        "hdb.structure_level_max_rounds": 5.0,
        "hdb.ev_propagation_ratio": 0.55,
        "hdb.er_induction_ratio": 0.55,
        "hdb.ev_propagation_threshold": 0.16,
        "attention.max_cam_items": 24.0,
        "attention.min_cam_items": 4.0,
        "attention.attention_energy_budget_base": 40.0,
        "attention.attention_filter_gain_floor": 0.12,
    }
    tuner.param_bounds = {
        "state_pool.default_er_decay_ratio": auto_tuner.ParamBound(0.93, 0.99, 0.005, quantum=0.001),
        "state_pool.default_ev_decay_ratio": auto_tuner.ParamBound(0.94, 0.995, 0.005, quantum=0.001),
        "state_pool.soft_capacity_start_items": auto_tuner.ParamBound(80.0, 1200.0, 10.0, quantum=1.0),
        "state_pool.soft_capacity_full_items": auto_tuner.ParamBound(160.0, 2400.0, 10.0, quantum=1.0),
        "hdb.internal_resolution_max_structures_per_tick": auto_tuner.ParamBound(3.0, 12.0, 1.0, quantum=1.0),
        "hdb.structure_level_max_rounds": auto_tuner.ParamBound(3.0, 10.0, 1.0, quantum=1.0),
        "hdb.ev_propagation_ratio": auto_tuner.ParamBound(0.15, 1.00, 0.05, quantum=0.01),
        "hdb.er_induction_ratio": auto_tuner.ParamBound(0.40, 1.00, 0.04, quantum=0.01),
        "hdb.ev_propagation_threshold": auto_tuner.ParamBound(0.03, 0.40, 0.03, quantum=0.005),
        "attention.max_cam_items": auto_tuner.ParamBound(4.0, 32.0, 2.0, quantum=1.0),
        "attention.min_cam_items": auto_tuner.ParamBound(1.0, 12.0, 1.0, quantum=1.0),
        "attention.attention_energy_budget_base": auto_tuner.ParamBound(8.0, 96.0, 4.0, quantum=0.5),
        "attention.attention_filter_gain_floor": auto_tuner.ParamBound(0.04, 0.40, 0.02, quantum=0.01),
    }
    tuner.metric_targets = {
        "internal_sa_count": auto_tuner.MetricTarget("internal_sa_count", 64.0, 260.0, 140.0, min_std=8.0),
        "internal_to_external_sa_ratio": auto_tuner.MetricTarget("internal_to_external_sa_ratio", 1.25, 6.0, 2.2, min_std=0.08),
        "internal_resolution_structure_count_selected": auto_tuner.MetricTarget("internal_resolution_structure_count_selected", 3.0, 12.0, 5.0, min_std=0.4),
        "internal_resolution_raw_unit_count": auto_tuner.MetricTarget("internal_resolution_raw_unit_count", 0.0, 500.0, 160.0, min_std=4.0),
        "timing_total_logic_ms": auto_tuner.MetricTarget("timing_total_logic_ms", 0.0, 8000.0, 2800.0, min_std=80.0),
        "pool_total_er": auto_tuner.MetricTarget("pool_total_er", 60.0, 260.0, 130.0, min_std=3.0, weight=0.7),
        "pool_total_ev": auto_tuner.MetricTarget("pool_total_ev", 60.0, 320.0, 150.0, min_std=3.0, weight=0.95),
        "pool_ev_to_er_ratio": auto_tuner.MetricTarget("pool_ev_to_er_ratio", 1.02, 1.30, 1.10, min_std=0.04, weight=0.9),
        "cfs_dissonance_max": auto_tuner.MetricTarget("cfs_dissonance_max", 0.0, 0.55, 0.20, min_std=0.03, high_band_threshold=0.50, high_band_max_ratio=0.20, high_band_soft_p95=0.70, high_band_max_run=3),
        "cfs_pressure_max": auto_tuner.MetricTarget("cfs_pressure_max", 0.0, 0.55, 0.20, min_std=0.03, high_band_threshold=0.50, high_band_max_ratio=0.20, high_band_soft_p95=0.70, high_band_max_run=3),
        "cfs_expectation_max": auto_tuner.MetricTarget("cfs_expectation_max", 0.0, 0.55, 0.20, min_std=0.03, high_band_threshold=0.50, high_band_max_ratio=0.20, high_band_soft_p95=0.70, high_band_max_run=3),
    }
    tuner.audit_path = E15_ROOT / "auto_tuner_runtime_probe.audit.jsonl"
    tuner._save_state = lambda: None
    tuner._audit = lambda event: None
    tuner._apply_overrides_to_runtime = lambda trace_id, touched_modules=None: None
    return tuner


def base_metrics(spec: FamilySpec) -> dict[str, Any]:
    return {
        "external_sa_count": spec.external_ref,
        "internal_sa_count": 120.0,
        "internal_to_external_sa_ratio": 2.0,
        "internal_resolution_structure_count_selected": 5.0,
        "internal_resolution_raw_unit_count": 14.0,
        "internal_resolution_selected_unit_count": 14.0,
        "internal_resolution_detail_budget": 80.0,
        "cam_item_count": 4.0,
        "pool_active_item_count": spec.pool_items,
        "pool_runtime_resolution_degraded_item_count": 0.0,
        "pool_runtime_resolution_active_component_count": 6.0,
        "pool_runtime_resolution_dropped_component_count": 1.0,
        "hdb_residual_diff_entry_ratio": 0.24,
        "hdb_same_content_multi_context_ratio": 0.08,
        "cfs_dissonance_max": 0.10,
        "cfs_pressure_max": 0.10,
        "cfs_expectation_max": 0.10,
        "pool_total_er": 100.0,
        "pool_total_ev": 125.0,
        "pool_ev_to_er_ratio": 1.25,
        "induction_total_delta_ev": 5.0,
        "induction_total_ev_consumed": 4.0,
        "induction_propagated_ev_total": 2.4,
        "induction_ev_from_er_total": 1.4,
        "induction_propagated_target_ratio": 0.55,
        "induction_ev_from_er_ratio": 0.32,
        "induction_source_item_count": 5.0,
        "induction_target_count": 8.0,
        "induction_structure_target_count": 8.0,
        "induction_memory_target_count": 0.0,
        "induction_propagated_target_count": 5.0,
        "induction_induced_target_count": 3.0,
        "induction_targets_per_source_mean": 1.6,
        "hdb_requested_ev_propagation_ratio": 0.55,
        "hdb_effective_ev_propagation_ratio": 0.55,
        "hdb_ev_propagation_ratio_clamped": 0.0,
        "hdb_requested_er_induction_ratio": 0.55,
        "hdb_effective_er_induction_ratio": 0.55,
        "hdb_er_induction_ratio_clamped": 0.0,
        "timing_total_logic_ms": 100.0,
    }


def branch_metrics(spec: FamilySpec, branch: str) -> dict[str, Any]:
    metrics = base_metrics(spec)
    if branch == "healthy_control":
        return metrics
    if branch == "disabled_control":
        metrics.update(
            {
                "internal_sa_count": spec.internal_low,
                "internal_to_external_sa_ratio": round(spec.internal_low / max(1.0, spec.external_ref), 6),
                "internal_resolution_structure_count_selected": 1.0,
                "pool_runtime_resolution_degraded_item_count": 0.0,
                "pool_runtime_resolution_active_component_count": 1.0,
                "pool_runtime_resolution_dropped_component_count": 8.0,
                "hdb_residual_diff_entry_ratio": 0.08,
            }
        )
        return metrics
    if branch == "endogenous_silent":
        metrics.update(
            {
                "internal_sa_count": spec.internal_low,
                "internal_to_external_sa_ratio": round(spec.internal_low / max(1.0, spec.external_ref), 6),
                "internal_resolution_structure_count_selected": 1.0,
                "pool_runtime_resolution_degraded_item_count": 0.0,
                "pool_runtime_resolution_active_component_count": 1.0,
                "pool_runtime_resolution_dropped_component_count": 8.0,
                "hdb_residual_diff_entry_ratio": 0.08,
            }
        )
    elif branch == "attention_overheat":
        metrics.update({"cam_item_count": spec.cam_hot})
    elif branch == "ev_propagation_thin":
        metrics.update(
            {
                "pool_total_er": spec.er_total,
                "pool_total_ev": spec.ev_total,
                "pool_ev_to_er_ratio": spec.ev_ratio_low,
                "induction_total_delta_ev": 5.0,
                "induction_total_ev_consumed": 4.0,
                "induction_propagated_ev_total": 0.40,
                "induction_ev_from_er_total": 4.60,
                "induction_propagated_target_ratio": 0.10,
                "induction_ev_from_er_ratio": 0.92,
                "induction_source_item_count": 4.0,
                "induction_target_count": 8.0,
                "induction_propagated_target_count": 1.0,
                "induction_induced_target_count": 7.0,
                "induction_targets_per_source_mean": 2.0,
            }
        )
    elif branch == "ev_induction_thin":
        metrics.update(
            {
                "pool_total_er": spec.er_total + 10.0,
                "pool_total_ev": (spec.er_total + 10.0) * 0.60,
                "pool_ev_to_er_ratio": 0.60,
                "induction_total_delta_ev": 4.0,
                "induction_total_ev_consumed": 3.4,
                "induction_propagated_ev_total": 3.2,
                "induction_ev_from_er_total": 0.20,
                "induction_propagated_target_ratio": 0.78,
                "induction_ev_from_er_ratio": 0.05,
                "induction_source_item_count": 5.0,
                "induction_target_count": 10.0,
                "induction_propagated_target_count": 8.0,
                "induction_induced_target_count": 2.0,
                "induction_targets_per_source_mean": 2.0,
            }
        )
    elif branch == "ev_retention_thin":
        metrics.update(
            {
                "pool_total_er": spec.er_total - 2.0,
                "pool_total_ev": (spec.er_total - 2.0) * 0.90,
                "pool_ev_to_er_ratio": 0.90,
                "induction_total_delta_ev": 6.0,
                "induction_total_ev_consumed": 4.2,
                "induction_propagated_ev_total": 4.0,
                "induction_ev_from_er_total": 2.0,
                "induction_propagated_target_ratio": 0.68,
                "induction_ev_from_er_ratio": 0.33,
                "induction_source_item_count": 5.0,
                "induction_target_count": 9.0,
                "induction_propagated_target_count": 6.0,
                "induction_induced_target_count": 3.0,
                "induction_targets_per_source_mean": 1.8,
            }
        )
    elif branch == "ev_saturated_retention":
        metrics.update(
            {
                "pool_total_er": spec.er_total,
                "pool_total_ev": spec.er_total * 0.15,
                "pool_ev_to_er_ratio": 0.15,
                "induction_total_delta_ev": 5.0,
                "induction_total_ev_consumed": 4.0,
                "induction_propagated_ev_total": 0.40,
                "induction_ev_from_er_total": 4.60,
                "induction_propagated_target_ratio": 0.10,
                "induction_ev_from_er_ratio": 0.92,
                "induction_source_item_count": 4.0,
                "induction_target_count": 8.0,
                "induction_propagated_target_count": 1.0,
                "induction_induced_target_count": 7.0,
                "induction_targets_per_source_mean": 2.0,
                "hdb_requested_ev_propagation_ratio": 1.40,
                "hdb_effective_ev_propagation_ratio": 1.00,
                "hdb_ev_propagation_ratio_clamped": 1.00,
            }
        )
    return metrics


def flatten_updates(updates: list[dict[str, Any]]) -> tuple[str, str, str]:
    params = ";".join(str(row.get("param", "")) for row in updates if row.get("param"))
    rules = ";".join(str(row.get("rule_id", "")) for row in updates if row.get("rule_id"))
    deltas = ";".join(f"{row.get('param', '')}:{float(row.get('delta', 0.0) or 0.0):.6f}" for row in updates)
    return params, rules, deltas


def run_case(spec: FamilySpec, branch: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    enabled = branch != "disabled_control"
    tuner = make_tuner(enabled=enabled, ev_balance_enabled=True)
    before = dict(tuner.runtime_params)
    tick_rows: list[dict[str, Any]] = []
    result: dict[str, Any] = {}
    for tick in range(1, WINDOW_TICKS + 1):
        metrics = branch_metrics(spec, branch)
        metrics["tick_index"] = tick
        result = tuner.on_tick(metrics=metrics)
        tick_rows.append(
            {
                "family": spec.family,
                "branch": branch,
                "branch_label": BRANCH_LABELS[branch],
                "tick": tick,
                "enabled": int(enabled),
                "applied": int(bool(result.get("applied", False))),
                "applied_count": int(result.get("applied_count", 0) or 0),
                "internal_sa_count": metrics.get("internal_sa_count", 0.0),
                "internal_to_external_sa_ratio": metrics.get("internal_to_external_sa_ratio", 0.0),
                "internal_resolution_structure_count_selected": metrics.get("internal_resolution_structure_count_selected", 0.0),
                "cam_item_count": metrics.get("cam_item_count", 0.0),
                "pool_ev_to_er_ratio": metrics.get("pool_ev_to_er_ratio", 0.0),
            }
        )

    after = dict(tuner.runtime_params)
    updates = list(result.get("applied_updates", []) or []) if isinstance(result, dict) else []
    params, rules, deltas = flatten_updates(updates)
    snapshots = result.get("snapshots", {}) if isinstance(result, dict) else {}
    endogenous = snapshots.get("endogenous_balance", {}) if isinstance(snapshots, dict) else {}
    ev_balance = snapshots.get("ev_balance", {}) if isinstance(snapshots, dict) else {}

    def changed(param: str) -> float:
        return round(float(after.get(param, 0.0)) - float(before.get(param, 0.0)), 8)

    case = {
        "family": spec.family,
        "branch": branch,
        "branch_label": BRANCH_LABELS[branch],
        "enabled": int(enabled),
        "applied": int(bool(result.get("applied", False))) if isinstance(result, dict) else 0,
        "applied_count": int(result.get("applied_count", 0) or 0) if isinstance(result, dict) else 0,
        "reason": str(result.get("reason", "") or "") if isinstance(result, dict) else "",
        "applied_params": params,
        "applied_rules": rules,
        "applied_deltas": deltas,
        "state_pool_er_decay_delta": changed("state_pool.default_er_decay_ratio"),
        "state_pool_ev_decay_delta": changed("state_pool.default_ev_decay_ratio"),
        "state_pool_soft_start_delta": changed("state_pool.soft_capacity_start_items"),
        "state_pool_soft_full_delta": changed("state_pool.soft_capacity_full_items"),
        "attention_max_cam_delta": changed("attention.max_cam_items"),
        "hdb_ev_propagation_ratio_delta": changed("hdb.ev_propagation_ratio"),
        "hdb_er_induction_ratio_delta": changed("hdb.er_induction_ratio"),
        "hdb_ev_propagation_threshold_delta": changed("hdb.ev_propagation_threshold"),
        "endogenous_needs_recovery": int(bool(endogenous.get("needs_recovery", False))),
        "endogenous_severity": float(endogenous.get("severity", 0.0) or 0.0),
        "source_supply_thin": int(bool(endogenous.get("source_supply_thin", False))),
        "ev_starved": int(bool(ev_balance.get("ev_starved", False))),
        "propagation_chain_weak": int(bool(ev_balance.get("propagation_chain_weak", False))),
        "induction_chain_weak": int(bool(ev_balance.get("induction_chain_weak", False))),
        "retention_chain_weak": int(bool(ev_balance.get("retention_chain_weak", False))),
        "propagation_ratio_saturated": int(bool(ev_balance.get("propagation_ratio_saturated", False))),
        "mean_ev_to_er_ratio": float(ev_balance.get("mean_ev_to_er_ratio", 0.0) or 0.0),
        "mean_cam_items": float(endogenous.get("mean_cam_items", 0.0) or 0.0),
        "json_result": json.dumps(result, ensure_ascii=False),
    }
    case.update(judge_case(case))
    return case, tick_rows


def judge_case(case: dict[str, Any]) -> dict[str, int]:
    branch = str(case.get("branch", ""))
    params = set(str(case.get("applied_params", "") or "").split(";"))
    applied = int(case.get("applied", 0) or 0) == 1
    if branch == "healthy_control":
        ok = (not applied) and not any(
            abs(float(case.get(key, 0.0) or 0.0)) > 1e-12
            for key in [
                "state_pool_er_decay_delta",
                "state_pool_ev_decay_delta",
                "attention_max_cam_delta",
                "hdb_ev_propagation_ratio_delta",
                "hdb_er_induction_ratio_delta",
            ]
        )
    elif branch == "disabled_control":
        ok = (not applied) and str(case.get("reason", "")) == ""
    elif branch == "endogenous_silent":
        ok = (
            applied
            and int(case.get("endogenous_needs_recovery", 0) or 0) == 1
            and int(case.get("source_supply_thin", 0) or 0) == 1
            and float(case.get("state_pool_er_decay_delta", 0.0) or 0.0) > 0.0
            and float(case.get("state_pool_ev_decay_delta", 0.0) or 0.0) > 0.0
            and "hdb.internal_resolution_max_structures_per_tick" not in params
        )
    elif branch == "attention_overheat":
        ok = (
            applied
            and float(case.get("mean_cam_items", 0.0) or 0.0) > 16.0
            and float(case.get("attention_max_cam_delta", 0.0) or 0.0) < 0.0
        )
    elif branch == "ev_propagation_thin":
        ok = (
            applied
            and int(case.get("ev_starved", 0) or 0) == 1
            and int(case.get("propagation_chain_weak", 0) or 0) == 1
            and float(case.get("hdb_ev_propagation_ratio_delta", 0.0) or 0.0) > 0.0
            and abs(float(case.get("hdb_er_induction_ratio_delta", 0.0) or 0.0)) <= 1e-12
        )
    elif branch == "ev_induction_thin":
        ok = (
            applied
            and int(case.get("ev_starved", 0) or 0) == 1
            and int(case.get("induction_chain_weak", 0) or 0) == 1
            and float(case.get("hdb_er_induction_ratio_delta", 0.0) or 0.0) > 0.0
            and abs(float(case.get("hdb_ev_propagation_ratio_delta", 0.0) or 0.0)) <= 1e-12
        )
    elif branch == "ev_retention_thin":
        ok = (
            applied
            and int(case.get("ev_starved", 0) or 0) == 1
            and int(case.get("retention_chain_weak", 0) or 0) == 1
            and float(case.get("state_pool_ev_decay_delta", 0.0) or 0.0) > 0.0
            and abs(float(case.get("hdb_ev_propagation_ratio_delta", 0.0) or 0.0)) <= 1e-12
            and abs(float(case.get("hdb_er_induction_ratio_delta", 0.0) or 0.0)) <= 1e-12
        )
    elif branch == "ev_saturated_retention":
        ok = (
            applied
            and int(case.get("ev_starved", 0) or 0) == 1
            and int(case.get("propagation_chain_weak", 0) or 0) == 1
            and int(case.get("propagation_ratio_saturated", 0) or 0) == 1
            and float(case.get("state_pool_ev_decay_delta", 0.0) or 0.0) > 0.0
            and abs(float(case.get("hdb_ev_propagation_ratio_delta", 0.0) or 0.0)) <= 1e-12
        )
    else:
        ok = False
    return {"case_ok": int(bool(ok))}


def build_family_rows(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_family: dict[str, dict[str, dict[str, Any]]] = {}
    for row in case_rows:
        by_family.setdefault(str(row["family"]), {})[str(row["branch"])] = row
    for family in sorted(by_family):
        branches = by_family[family]
        family_row = {
            "family": family,
            "healthy_quiet_pass": int(branches.get("healthy_control", {}).get("case_ok", 0) or 0),
            "endogenous_recovery_pass": int(branches.get("endogenous_silent", {}).get("case_ok", 0) or 0),
            "attention_overheat_pass": int(branches.get("attention_overheat", {}).get("case_ok", 0) or 0),
            "ev_propagation_pass": int(branches.get("ev_propagation_thin", {}).get("case_ok", 0) or 0),
            "ev_induction_pass": int(branches.get("ev_induction_thin", {}).get("case_ok", 0) or 0),
            "ev_retention_pass": int(branches.get("ev_retention_thin", {}).get("case_ok", 0) or 0),
            "ev_saturated_pass": int(branches.get("ev_saturated_retention", {}).get("case_ok", 0) or 0),
            "disabled_quiet_pass": int(branches.get("disabled_control", {}).get("case_ok", 0) or 0),
        }
        family_row["all_ok"] = int(all(int(family_row[key]) == 1 for key in family_row if key.endswith("_pass")))
        family_row["er_decay_delta"] = float(branches.get("endogenous_silent", {}).get("state_pool_er_decay_delta", 0.0) or 0.0)
        family_row["ev_decay_delta_silent"] = float(branches.get("endogenous_silent", {}).get("state_pool_ev_decay_delta", 0.0) or 0.0)
        family_row["cam_delta_overheat"] = float(branches.get("attention_overheat", {}).get("attention_max_cam_delta", 0.0) or 0.0)
        family_row["ev_prop_delta"] = float(branches.get("ev_propagation_thin", {}).get("hdb_ev_propagation_ratio_delta", 0.0) or 0.0)
        family_row["er_induction_delta"] = float(branches.get("ev_induction_thin", {}).get("hdb_er_induction_ratio_delta", 0.0) or 0.0)
        family_row["ev_decay_delta_retention"] = float(branches.get("ev_retention_thin", {}).get("state_pool_ev_decay_delta", 0.0) or 0.0)
        family_row["ev_decay_delta_saturated"] = float(branches.get("ev_saturated_retention", {}).get("state_pool_ev_decay_delta", 0.0) or 0.0)
        rows.append(family_row)
    return rows


def summarize(case_rows: list[dict[str, Any]], family_rows: list[dict[str, Any]]) -> dict[str, Any]:
    family_count = len(family_rows)
    all_ok = sum(int(row.get("all_ok", 0) or 0) for row in family_rows)
    summary: dict[str, Any] = {
        "experiment_id": "E15",
        "family_count": family_count,
        "case_count": len(case_rows),
        "all_ok_family_count": all_ok,
        "all_ok_ratio": round(all_ok / max(1, family_count), 8),
        "all_ok_sign_p": sign_test_p_value(all_ok, family_count - all_ok),
        "case_ok_ratio": round(sum(int(row.get("case_ok", 0) or 0) for row in case_rows) / max(1, len(case_rows)), 8),
    }
    for key in [
        "healthy_quiet_pass",
        "endogenous_recovery_pass",
        "attention_overheat_pass",
        "ev_propagation_pass",
        "ev_induction_pass",
        "ev_retention_pass",
        "ev_saturated_pass",
        "disabled_quiet_pass",
    ]:
        summary[f"{key}_ratio"] = round(sum(int(row.get(key, 0) or 0) for row in family_rows) / max(1, family_count), 8)
    for key in [
        "er_decay_delta",
        "ev_decay_delta_silent",
        "cam_delta_overheat",
        "ev_prop_delta",
        "er_induction_delta",
        "ev_decay_delta_retention",
        "ev_decay_delta_saturated",
    ]:
        summary[f"{key}_mean"] = mean_or_zero([float(row.get(key, 0.0) or 0.0) for row in family_rows])
    summary["support_level"] = (
        "strong_evidence"
        if family_count >= 12
        and summary["all_ok_ratio"] >= 1.0
        and summary["all_ok_sign_p"] <= 0.001
        else "insufficient"
    )
    return summary


def make_charts(case_rows: list[dict[str, Any]], family_rows: list[dict[str, Any]], summary: dict[str, Any], stamp: str) -> list[Path]:
    plt = e01.setup_matplotlib()
    charts: list[Path] = []

    pass_path = CHART_DIR / f"e15_branch_pass_rates_{stamp}.png"
    fig, ax = plt.subplots(figsize=(11.2, 5.4), dpi=160)
    labels = ["健康静默", "沉寂保活", "注意过热", "EV传播", "ER诱发", "EV保留", "饱和转保留", "关闭静默"]
    keys = [
        "healthy_quiet_pass_ratio",
        "endogenous_recovery_pass_ratio",
        "attention_overheat_pass_ratio",
        "ev_propagation_pass_ratio",
        "ev_induction_pass_ratio",
        "ev_retention_pass_ratio",
        "ev_saturated_pass_ratio",
        "disabled_quiet_pass_ratio",
    ]
    values = [float(summary.get(key, 0.0)) for key in keys]
    ax.bar(labels, values, color=["#64748b", "#2563eb", "#dc2626", "#0891b2", "#0d9488", "#16a34a", "#7c3aed", "#94a3b8"], alpha=0.86)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("family 级通过比例")
    ax.set_title("E15 自适应调参器受控异常分支通过比例")
    ax.tick_params(axis="x", rotation=18)
    for idx, value in enumerate(values):
        ax.text(idx, value + 0.025, f"{value:.3f}", ha="center", va="bottom", fontsize=9)
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    fig.savefig(pass_path, bbox_inches="tight")
    plt.close(fig)
    charts.append(pass_path)

    delta_path = CHART_DIR / f"e15_param_delta_directions_{stamp}.png"
    fig, ax = plt.subplots(figsize=(11.4, 5.6), dpi=160)
    labels = ["沉寂 ER保留", "沉寂 EV保留", "过热 CAM上限", "EV传播比例", "ER诱发比例", "保留 EV衰减", "饱和 EV衰减"]
    values = [
        float(summary.get("er_decay_delta_mean", 0.0)),
        float(summary.get("ev_decay_delta_silent_mean", 0.0)),
        float(summary.get("cam_delta_overheat_mean", 0.0)),
        float(summary.get("ev_prop_delta_mean", 0.0)),
        float(summary.get("er_induction_delta_mean", 0.0)),
        float(summary.get("ev_decay_delta_retention_mean", 0.0)),
        float(summary.get("ev_decay_delta_saturated_mean", 0.0)),
    ]
    colors = ["#2563eb" if v > 0 else "#dc2626" if v < 0 else "#94a3b8" for v in values]
    ax.bar(labels, values, color=colors, alpha=0.86)
    ax.axhline(0.0, color="#0f172a", linewidth=1.0)
    ax.set_ylabel("参数变化均值")
    ax.set_title("E15 不同异常状态对应的稳定化参数方向")
    ax.tick_params(axis="x", rotation=18)
    for idx, value in enumerate(values):
        ax.text(idx, value + (0.002 if value >= 0 else -0.002), f"{value:.4f}", ha="center", va=("bottom" if value >= 0 else "top"), fontsize=9)
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    fig.savefig(delta_path, bbox_inches="tight")
    plt.close(fig)
    charts.append(delta_path)

    matrix_path = CHART_DIR / f"e15_family_pass_matrix_{stamp}.png"
    fig, ax = plt.subplots(figsize=(11.4, 5.2), dpi=160)
    fields = [
        "healthy_quiet_pass",
        "endogenous_recovery_pass",
        "attention_overheat_pass",
        "ev_propagation_pass",
        "ev_induction_pass",
        "ev_retention_pass",
        "ev_saturated_pass",
        "disabled_quiet_pass",
    ]
    matrix = [[int(row.get(field, 0) or 0) for field in fields] for row in family_rows]
    ax.imshow(matrix, vmin=0, vmax=1, cmap="YlGnBu", aspect="auto")
    ax.set_yticks(list(range(len(family_rows))))
    ax.set_yticklabels([row["family"] for row in family_rows])
    ax.set_xticks(list(range(len(fields))))
    ax.set_xticklabels(["健康", "沉寂", "过热", "EV传", "ER诱", "EV保", "饱和", "关闭"], rotation=25, ha="right")
    ax.set_title("E15 family 级强证据判据矩阵")
    for y, row in enumerate(matrix):
        for x, value in enumerate(row):
            ax.text(x, y, str(value), ha="center", va="center", fontsize=8, color="#0f172a")
    fig.tight_layout()
    fig.savefig(matrix_path, bbox_inches="tight")
    plt.close(fig)
    charts.append(matrix_path)

    heat_path = CHART_DIR / f"e15_branch_param_heatmap_{stamp}.png"
    branch_rows = [row for row in case_rows if row["family"] == "F01"]
    params = [
        "state_pool_er_decay_delta",
        "state_pool_ev_decay_delta",
        "attention_max_cam_delta",
        "hdb_ev_propagation_ratio_delta",
        "hdb_er_induction_ratio_delta",
        "hdb_ev_propagation_threshold_delta",
    ]
    data = [[float(row.get(param, 0.0) or 0.0) for param in params] for row in branch_rows]
    fig, ax = plt.subplots(figsize=(11.6, 5.4), dpi=160)
    vmax = max(0.01, max(abs(v) for row in data for v in row))
    im = ax.imshow(data, cmap="coolwarm", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_yticks(list(range(len(branch_rows))))
    ax.set_yticklabels([BRANCH_LABELS[str(row["branch"])] for row in branch_rows])
    ax.set_xticks(list(range(len(params))))
    ax.set_xticklabels(["ER保留", "EV保留", "CAM", "EV传播", "ER诱发", "EV阈值"], rotation=25, ha="right")
    ax.set_title("E15 F01 各分支参数更新方向热力图")
    fig.colorbar(im, ax=ax, shrink=0.88)
    fig.tight_layout()
    fig.savefig(heat_path, bbox_inches="tight")
    plt.close(fig)
    charts.append(heat_path)

    return charts


def write_design_note(path: Path) -> None:
    lines = [
        "# E15 自适应调参稳定性实验设计说明",
        "",
        "## 最小命题",
        "",
        "当前 AP 原型中的自适应调参器能够在受控指标窗口中区分沉寂、注意力过热、虚能量传播偏薄、实能量诱发偏薄、虚能量保留偏薄和传播比例饱和等状态，并把真实 runtime 参数向稳定化方向推进。",
        "",
        "## 收窄边界",
        "",
        "- 本实验不证明任意开放环境下的长程自稳已经完成。",
        "- 本实验不把短窗口白箱调参等同于完整自主学习。",
        "- 本实验只验证 AutoTuner 的真实观测、判别和参数更新链路是否与 AP 的稳定化哲学一致。",
        "",
        "## 数据集构造",
        "",
        "每个 family 使用相同窗口长度与相同参数初值。健康分支给出目标区间内的指标，异常分支只改变一个主要失稳因素；关闭分支使用沉寂异常输入但关闭调参器，用来证明参数变化来自调参器，而不是数据生成脚本。",
        "",
        "## 强证据判据",
        "",
        "健康分支必须保持静默；沉寂分支必须识别内源恢复需求并提高 ER/EV 保留；注意力过热分支必须降低 CAM 上限；EV 传播偏薄分支必须提高 ev_propagation_ratio；ER 诱发偏薄分支必须提高 er_induction_ratio；EV 保留偏薄分支必须提高 default_ev_decay_ratio；传播比例饱和分支必须停止继续推高传播比例并转向提高 EV 保留；关闭分支必须静默。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    *,
    family_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    charts: list[Path],
    whitebox: dict[str, Any],
    stamp: str,
) -> Path:
    lines = [
        f"# E15 自适应调参稳定性实验报告（{stamp}）",
        "",
        "## 核心结论",
        "",
        f"- 支持等级：**{summary.get('support_level', 'unknown')}**",
        f"- family 数：{int(summary.get('family_count', 0))}",
        f"- case 数：{int(summary.get('case_count', 0))}",
        f"- family 级整体通过比例：{summary.get('all_ok_ratio', 0.0):.3f}",
        f"- family 级符号检验 p 值：{summary.get('all_ok_sign_p', 1.0):.8f}",
        f"- 参数方向均值：沉寂 ER保留 {summary.get('er_decay_delta_mean', 0.0):.4f}，沉寂 EV保留 {summary.get('ev_decay_delta_silent_mean', 0.0):.4f}，注意力 CAM {summary.get('cam_delta_overheat_mean', 0.0):.4f}，EV传播 {summary.get('ev_prop_delta_mean', 0.0):.4f}，ER诱发 {summary.get('er_induction_delta_mean', 0.0):.4f}。",
        "",
        "## 正文可使用的最小命题",
        "",
        "在当前 AP 原型中，自适应调参器可以根据短窗口指标区分不同失稳类型，并把相应 runtime 参数朝稳定化方向推进：沉寂时提高状态池保留，注意力过热时收紧 CAM，上游传播或诱发偏薄时分别调整 HDB 输入比例，输入比例已饱和时转向提高状态池 EV 保留。",
        "",
        "## family 级通过情况",
        "",
        "| family | 健康静默 | 沉寂保活 | 注意过热 | EV传播 | ER诱发 | EV保留 | 饱和转保留 | 关闭静默 | all_ok |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in family_rows:
        lines.append(
            f"| {row['family']} | {int(row['healthy_quiet_pass'])} | {int(row['endogenous_recovery_pass'])} | "
            f"{int(row['attention_overheat_pass'])} | {int(row['ev_propagation_pass'])} | {int(row['ev_induction_pass'])} | "
            f"{int(row['ev_retention_pass'])} | {int(row['ev_saturated_pass'])} | {int(row['disabled_quiet_pass'])} | {int(row['all_ok'])} |"
        )
    lines.extend(["", "## 白箱样例", ""])
    for branch in BRANCH_ORDER:
        row = whitebox.get(branch, {}) or {}
        lines.append(
            f"- {BRANCH_LABELS[branch]}：applied={row.get('applied', '')}，params=`{row.get('applied_params', '')}`，"
            f"deltas=`{row.get('applied_deltas', '')}`。"
        )
    lines.extend(["", "## 图表", ""])
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    report = REPORT_DIR / f"E15_auto_tuner_stability_report_{stamp}.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def run_experiment(*, stamp: str, family_count: int) -> dict[str, Any]:
    ensure_dirs()
    specs = FAMILY_SPECS[: max(1, min(int(family_count), len(FAMILY_SPECS)))]
    case_rows: list[dict[str, Any]] = []
    tick_rows: list[dict[str, Any]] = []
    for spec in specs:
        for branch in BRANCH_ORDER:
            case, ticks = run_case(spec, branch)
            case_rows.append(case)
            tick_rows.extend(ticks)
    case_rows.sort(key=lambda row: (str(row["family"]), BRANCH_ORDER.index(str(row["branch"]))))
    tick_rows.sort(key=lambda row: (str(row["family"]), BRANCH_ORDER.index(str(row["branch"])), int(row["tick"])))
    family_rows = build_family_rows(case_rows)
    summary = summarize(case_rows, family_rows)
    summary["stamp"] = stamp
    charts = make_charts(case_rows=case_rows, family_rows=family_rows, summary=summary, stamp=stamp)
    design_note = REPORT_DIR / "E15_auto_tuner_stability_design_logic.md"
    write_design_note(design_note)
    whitebox = {
        branch: next((row for row in case_rows if str(row.get("family", "")) == "F01" and str(row.get("branch", "")) == branch), {})
        for branch in BRANCH_ORDER
    }
    report = write_report(family_rows=family_rows, summary=summary, charts=charts, whitebox=whitebox, stamp=stamp)

    case_csv = TABLE_DIR / f"e15_auto_tuner_stability_case_rows_{stamp}.csv"
    tick_csv = TABLE_DIR / f"e15_auto_tuner_stability_tick_rows_{stamp}.csv"
    family_csv = TABLE_DIR / f"e15_auto_tuner_stability_family_rows_{stamp}.csv"
    summary_json = TABLE_DIR / f"e15_auto_tuner_stability_summary_{stamp}.json"
    whitebox_json = TABLE_DIR / f"e15_auto_tuner_stability_whitebox_{stamp}.json"
    e01.write_csv(case_csv, case_rows)
    e01.write_csv(tick_csv, tick_rows)
    e01.write_csv(family_csv, family_rows)
    e01.write_json(summary_json, summary)
    e01.write_json(whitebox_json, whitebox)
    evidence = {
        "experiment_id": "E15",
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
    e01.write_json(MANIFEST_DIR / f"E15_auto_tuner_stability_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E15_auto_tuner_stability_latest.json", evidence)
    return evidence


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper E15 auto-tuner stability experiment.")
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
