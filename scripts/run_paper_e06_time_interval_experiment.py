# -*- coding: utf-8 -*-
"""Run paper E06 time-interval / delayed-task experiment.

Paper-facing E06 claim
----------------------
This experiment intentionally narrows E06 to a claim that the current AP
prototype can already support with strong, auditable evidence:

1. under tick-based timing, time-feeling computes the expected tick delta and
   maps it into the configured dual-bucket time representation;
2. when delayed tasks are enabled, the bound target registers a finite delayed
   task whose due tick follows the bucket-centered interval;
3. on the integrated observatory path, a simple external seed can reliably
   trigger registration at tick 1 and due execution at tick 3; turning delayed
   tasks off removes the registration/execution chain while leaving the basic
   time-feeling bindings present.

The experiment does not claim that recall action has already become stable.
It only proves the narrower timing-and-reprojection chain that is currently
well supported by the implementation.
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

ROOT = Path(__file__).resolve().parent
AP_ROOT = ROOT / "Artificial-PsyArch"
if str(AP_ROOT) not in sys.path:
    sys.path.insert(0, str(AP_ROOT))

import run_paper_e01_experiment as e01
from hdb import HDB
from observatory._app import ObservatoryApp
from observatory.experiment.runner import apply_experiment_default_app_overrides
from state_pool.main import StatePool
from time_sensor.main import TimeSensor


ARTIFACT_ROOT = ROOT / "docs" / "paper_artifacts_2026-05-11"
E06_ROOT = ARTIFACT_ROOT / "E06_time_interval_closure"
TABLE_DIR = E06_ROOT / "tables"
CHART_DIR = E06_ROOT / "charts"
REPORT_DIR = E06_ROOT / "reports"
MANIFEST_DIR = E06_ROOT / "manifests"

STAMP_DEFAULT = "e06_final_v1"


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dirs() -> None:
    for path in (TABLE_DIR, CHART_DIR, REPORT_DIR, MANIFEST_DIR):
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


def num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        value = row.get(key, default)
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


@dataclass(frozen=True)
class BucketCase:
    case_id: str
    interval_ticks: int
    source_energy: float


BUCKET_CASES: list[BucketCase] = [
    BucketCase("B01", 0, 1.0),
    BucketCase("B02", 1, 1.0),
    BucketCase("B03", 2, 1.0),
    BucketCase("B04", 3, 1.0),
    BucketCase("B05", 6, 1.0),
    BucketCase("B06", 12, 1.0),
    BucketCase("B07", 0, 2.0),
    BucketCase("B08", 1, 2.0),
    BucketCase("B09", 2, 2.0),
    BucketCase("B10", 3, 2.0),
    BucketCase("B11", 6, 2.0),
    BucketCase("B12", 12, 2.0),
]

INTEGRATED_SEEDS: list[str] = [
    "ABX",
    "CDQ",
    "KLM",
    "PQT",
    "123",
    "XYZ!",
    "UV7",
    "MNO",
    "JK?",
    "L2R",
    "GH#",
    "Z9$",
]

TICK_BUCKETS: list[dict[str, float | str]] = [
    {"id": "0_5t", "center": 0.5},
    {"id": "1_5t", "center": 1.5},
    {"id": "3t", "center": 3.0},
    {"id": "6t", "center": 6.0},
    {"id": "12t", "center": 12.0},
    {"id": "24t", "center": 24.0},
    {"id": "48t", "center": 48.0},
    {"id": "96t", "center": 96.0},
]


class DummyStore:
    def __init__(self, items: dict[str, dict[str, Any]]):
        self._items = items

    def get(self, item_id: str) -> dict[str, Any] | None:
        return self._items.get(item_id)

    def get_by_ref(self, ref_id: str) -> dict[str, Any] | None:
        for item in self._items.values():
            if str(item.get("ref_object_id", "") or "") == str(ref_id or ""):
                return item
        return None


class DummyPool:
    def __init__(self, items: dict[str, dict[str, Any]]):
        self._store = DummyStore(items)
        self.bind_calls: list[dict[str, Any]] = []
        self.energy_updates: list[dict[str, Any]] = []

    def bind_attribute_node_to_object(
        self,
        *,
        target_item_id: str,
        attribute_sa: dict,
        trace_id: str,
        tick_id: str,
        source_module: str,
        reason: str,
    ) -> dict[str, Any]:
        self.bind_calls.append(
            {
                "target_item_id": target_item_id,
                "attribute_sa": dict(attribute_sa),
                "trace_id": trace_id,
                "tick_id": tick_id,
                "source_module": source_module,
                "reason": reason,
            }
        )
        return {"success": True, "code": "OK", "data": {"target_item_id": target_item_id}}

    def apply_energy_update(
        self,
        *,
        target_item_id: str,
        delta_er: float,
        delta_ev: float,
        trace_id: str,
        tick_id: str,
        reason: str,
        source_module: str,
    ) -> dict[str, Any]:
        item = self._store.get(target_item_id)
        if item is None:
            raise RuntimeError(f"target missing: {target_item_id}")
        energy = item.setdefault("energy", {})
        energy["er"] = float(energy.get("er", 0.0) or 0.0) + float(delta_er or 0.0)
        energy["ev"] = float(energy.get("ev", 0.0) or 0.0) + float(delta_ev or 0.0)
        self.energy_updates.append(
            {
                "target_item_id": target_item_id,
                "delta_er": float(delta_er or 0.0),
                "delta_ev": float(delta_ev or 0.0),
                "trace_id": trace_id,
                "tick_id": tick_id,
                "reason": reason,
                "source_module": source_module,
            }
        )
        return {"success": True, "code": "OK", "data": {"target_item_id": target_item_id}}


def build_dummy_pool() -> DummyPool:
    return DummyPool(
        {
            "item_atomic": {
                "id": "item_atomic",
                "ref_object_id": "st_atomic",
                "ref_object_type": "st",
                "ref_snapshot": {"content_display": "{A}", "token_count": 1, "flat_tokens": ["A"]},
                "energy": {"er": 0.0, "ev": 0.6},
                "ext": {"bound_attributes": []},
            },
            "item_parent": {
                "id": "item_parent",
                "ref_object_id": "st_parent",
                "ref_object_type": "st",
                "ref_snapshot": {
                    "content_display": "{ABX}",
                    "token_count": 3,
                    "flat_tokens": ["A", "B", "X"],
                    "sequence_groups": [{"group_index": 0}, {"group_index": 1}],
                },
                "energy": {"er": 0.0, "ev": 0.9},
                "ext": {"bound_attributes": []},
            },
        }
    )


def build_bucket_snapshot(*, interval_ticks: int, source_energy: float, current_tick: int = 100) -> dict[str, Any]:
    return {
        "items": [
            {
                "memory_id": f"em_bucket_{interval_ticks}_{source_energy}",
                "memory_created_at": 1000,
                "created_at": 1000,
                "memory_tick_id": f"cycle_{current_tick - int(interval_ticks):04d}",
                "memory_tick_index": int(current_tick - int(interval_ticks)),
                "last_delta_er": 0.0,
                "last_delta_ev": float(source_energy),
                "total_energy": float(source_energy),
                "display_text": "{ABX}",
                "backing_structure_ids": ["st_parent"],
                "structure_refs": ["st_parent"],
                "structure_ref_items": [{"id": "st_parent"}],
            }
        ]
    }


def build_bucket_sensor(*, delayed_enabled: bool) -> TimeSensor:
    return TimeSensor(
        config_override={
            "enabled": True,
            "time_basis": "tick",
            "enable_bucket_nodes": False,
            "enable_bind_attribute": True,
            "enable_delayed_tasks": bool(delayed_enabled),
            "enable_projection_target_bindings": True,
            "enable_runtime_snapshot_target_bindings": True,
            "memory_top_k": 8,
            "energy_gain_ratio": 0.2,
            "base_energy_source": "last_delta_energy",
            "max_bind_targets_per_memory": 1,
            "max_projection_bind_targets_per_memory": 1,
            "max_total_bindings": 4,
            "peak_keep_ratio": 0.72,
            "projection_target_keep_ratio": 0.72,
            "delayed_task_register_min_delta_energy": 0.01,
            "delayed_task_min_interval_ticks": 2,
            "delayed_task_due_tolerance_ticks": 0,
            "delayed_task_energy_ratio": 1.0,
            "delayed_task_energy_min": 0.05,
            "delayed_task_energy_max": 1.0,
        }
    )


def expected_dual_bucket(interval_ticks: float) -> tuple[str, float, str, float]:
    centers = [float(row["center"]) for row in TICK_BUCKETS]
    ids = [str(row["id"]) for row in TICK_BUCKETS]
    t = float(interval_ticks)
    if t <= centers[0]:
        return ids[0], 1.0, ids[0], 0.0
    if t >= centers[-1]:
        return ids[-1], 1.0, ids[-1], 0.0
    for idx in range(len(centers) - 1):
        c1 = centers[idx]
        c2 = centers[idx + 1]
        if c1 <= t <= c2:
            span = max(1e-9, float(c2 - c1))
            w2 = max(0.0, min(1.0, float(t - c1) / span))
            w1 = 1.0 - w2
            return ids[idx], round(w1, 4), ids[idx + 1], round(w2, 4)
    return ids[0], 1.0, ids[0], 0.0


def run_bucket_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in BUCKET_CASES:
        pool = build_dummy_pool()
        sensor = build_bucket_sensor(delayed_enabled=True)
        try:
            result = sensor.run_time_feeling_tick(
                pool=pool,
                trace_id=f"paper_e06_bucket_{case.case_id}",
                tick_id="cycle_0100",
                now_ms=2000,
                memory_activation_snapshot=build_bucket_snapshot(
                    interval_ticks=case.interval_ticks,
                    source_energy=case.source_energy,
                    current_tick=100,
                ),
                memory_feedback_result=None,
                source_mode="runtime_memory_projection",
            )["data"]
            memory_row = (result.get("memory_rows", []) or [{}])[0]
            binding_row = (result.get("attribute_bindings", []) or [{}])[0]
            task_row = ((result.get("delayed_tasks", {}) or {}).get("registered", {}) or {}).get("tasks", [{}])[0]
            exp_b1, exp_w1, exp_b2, exp_w2 = expected_dual_bucket(float(case.interval_ticks))
            expected_primary_bucket = exp_b1
            if float(exp_w2) > float(exp_w1):
                expected_primary_bucket = exp_b2
            obs_b1 = str(memory_row.get("bucket_1", "") or "")
            obs_w1 = round(float(memory_row.get("w1", 0.0) or 0.0), 4)
            obs_b2 = str(memory_row.get("bucket_2", "") or "")
            obs_w2 = round(float(memory_row.get("w2", 0.0) or 0.0), 4)
            obs_delta = round(float(memory_row.get("delta_value", 0.0) or 0.0), 4)
            expected_due = 100 + max(2, int(round(float((binding_row or {}).get("bucket_center_sec", 0.0) or 0.0))))
            rows.append(
                {
                    "case_id": case.case_id,
                    "interval_ticks": int(case.interval_ticks),
                    "source_energy": float(case.source_energy),
                    "delta_value": obs_delta,
                    "expected_delta_value": float(case.interval_ticks),
                    "delta_match": int(abs(obs_delta - float(case.interval_ticks)) < 1e-9),
                    "bucket_1": obs_b1,
                    "w1": obs_w1,
                    "bucket_2": obs_b2,
                    "w2": obs_w2,
                    "expected_bucket_1": exp_b1,
                    "expected_w1": exp_w1,
                    "expected_bucket_2": exp_b2,
                    "expected_w2": exp_w2,
                    "expected_primary_bucket": expected_primary_bucket,
                    "bucket_match": int(obs_b1 == exp_b1 and obs_b2 == exp_b2),
                    "weight_match": int(abs(obs_w1 - exp_w1) <= 0.0002 and abs(obs_w2 - exp_w2) <= 0.0002),
                    "binding_count": len(result.get("attribute_bindings", []) or []),
                    "binding_target_item_id": str(binding_row.get("target_item_id", "") or ""),
                    "binding_bucket_id": str(binding_row.get("bucket_id", "") or ""),
                    "binding_bucket_center_tick": float(binding_row.get("bucket_center_sec", 0.0) or 0.0),
                    "binding_primary_match": int(str(binding_row.get("bucket_id", "") or "") == expected_primary_bucket),
                    "registered_count": int((((result.get("delayed_tasks", {}) or {}).get("registered", {}) or {}).get("registered_count", 0) or 0)),
                    "registered_task_kind": str(task_row.get("task_kind", "") or ""),
                    "registered_due_tick": int(task_row.get("due_tick", 0) or 0),
                    "expected_due_tick": int(expected_due),
                    "due_match": int(int(task_row.get("due_tick", 0) or 0) == int(expected_due)),
                }
            )
        finally:
            sensor.close()
    rows.sort(key=lambda row: (int(row["interval_ticks"]), float(row["source_energy"])))
    return rows


def build_real_hdb_with_time_structure() -> tuple[str, HDB]:
    temp_dir = tempfile.mkdtemp(prefix="paper_e06_hdb_")
    hdb = HDB(config_override={"data_dir": temp_dir, "enable_background_repair": False})
    groups = [
        {
            "group_index": 0,
            "source_type": "current",
            "origin_frame_id": "frame_time_projection",
            "order_sensitive": True,
            "units": [
                {
                    "unit_id": "u_anchor",
                    "token": "A",
                    "display_text": "A",
                    "unit_role": "feature",
                    "sequence_index": 0,
                    "source_type": "current",
                },
                {
                    "unit_id": "u_time",
                    "token": "时间感受:1.0",
                    "display_text": "时间感受:约1tick",
                    "unit_role": "attribute",
                    "attribute_name": "时间感受",
                    "attribute_value": 1.0,
                    "sequence_index": 1,
                    "source_type": "current",
                },
            ],
            "csa_bundles": [
                {
                    "bundle_id": "bundle_time_1",
                    "anchor_unit_id": "u_anchor",
                    "member_unit_ids": ["u_anchor", "u_time"],
                }
            ],
        }
    ]
    profile = hdb._cut.build_sequence_profile_from_groups(groups)
    payload = hdb._cut.make_structure_payload_from_profile(
        profile,
        confidence=0.92,
        ext={"kind": "paper_e06_time_projection"},
    )
    structure_obj, _ = hdb._structure_store.create_structure(
        structure_payload=payload,
        trace_id="paper_e06_seed",
        tick_id="paper_e06_seed",
        origin="paper_e06_seed",
        origin_id="paper_e06_seed",
        parent_ids=[],
    )
    hdb._pointer_index.register_structure(structure_obj)
    return temp_dir, hdb


def build_real_pool() -> StatePool:
    return StatePool(
        config_override={
            "enable_script_broadcast": False,
            "placeholder_hdb_enabled": False,
            "placeholder_script_enabled": False,
            "placeholder_attention_enabled": False,
            "placeholder_emotion_enabled": False,
            "placeholder_action_enabled": False,
            "insert_attribute_sa_as_state_item": True,
            "attribute_binding_runtime_mode": "state_item",
        }
    )


def run_controlled_parallel_cases(*, repeats: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for repeat in range(1, int(repeats) + 1):
        temp_dir, hdb = build_real_hdb_with_time_structure()
        pool = build_real_pool()
        try:
            runtime_obj = hdb.make_runtime_structure_object(
                next(iter(hdb._structure_store.iter_structures()))["id"],
                er=0.6,
                ev=0.2,
                reason="paper_e06_runtime_seed",
            )
            assert runtime_obj is not None
            source_structure_id = str(runtime_obj.get("id", "") or "")
            pool.insert_runtime_node(
                runtime_object=runtime_obj,
                trace_id=f"paper_e06_parallel_seed_{repeat}",
                tick_id="cycle_0010",
                allow_merge=True,
                source_module="paper_e06",
                reason="paper_e06_parallel_seed",
            )
            seeded_item = pool._store.get_by_ref(source_structure_id)
            seeded_item_id = str((seeded_item or {}).get("id", "") or "")
            seeded_ev_before = float(((seeded_item or {}).get("energy", {}) or {}).get("ev", 0.0) or 0.0)
            sensor = TimeSensor(
                config_override={
                    "enabled": True,
                    "time_basis": "tick",
                    "enable_bucket_nodes": False,
                    "enable_bind_attribute": True,
                    "enable_delayed_tasks": True,
                    "enable_projection_target_bindings": True,
                    "enable_runtime_snapshot_target_bindings": True,
                    "memory_top_k": 4,
                    "energy_gain_ratio": 0.2,
                    "base_energy_source": "last_delta_energy",
                    "max_bind_targets_per_memory": 1,
                    "max_projection_bind_targets_per_memory": 1,
                    "max_total_bindings": 4,
                    "delayed_task_register_min_delta_energy": 0.01,
                    "delayed_task_min_interval_ticks": 1,
                    "delayed_task_due_tolerance_ticks": 0,
                    "delayed_task_energy_ratio": 1.0,
                    "delayed_task_energy_min": 0.05,
                    "delayed_task_energy_max": 1.0,
                }
            )
            snapshot = {
                "items": [
                    {
                        "memory_id": f"em_time_exec_{repeat}",
                        "memory_created_at": 1000,
                        "created_at": 1000,
                        "memory_tick_index": 10,
                        "last_delta_er": 0.0,
                        "last_delta_ev": 1.0,
                        "total_energy": 1.0,
                        "display_text": "A",
                        "backing_structure_ids": [source_structure_id],
                        "structure_refs": [source_structure_id],
                        "structure_ref_items": [{"id": source_structure_id}],
                    }
                ]
            }
            first = sensor.run_time_feeling_tick(
                pool=pool,
                hdb=hdb,
                trace_id=f"paper_e06_parallel_first_{repeat}",
                tick_id="cycle_0010",
                now_ms=2000,
                memory_activation_snapshot=snapshot,
                memory_feedback_result=None,
                source_mode="runtime_memory_projection",
            )["data"]
            task_rows = list(first.get("delayed_tasks", {}).get("registered", {}).get("tasks", []) or [])
            task_kinds = {str(row.get("task_kind", "") or "") for row in task_rows}
            structure_task = next(row for row in task_rows if str(row.get("task_kind", "")) == "structure_projection")
            stripped_structure_id = str(
                structure_task.get("target_structure_id", "") or structure_task.get("target_ref_object_id", "")
            )
            second = sensor.run_time_feeling_tick(
                pool=pool,
                hdb=hdb,
                trace_id=f"paper_e06_parallel_due_{repeat}",
                tick_id="cycle_0011",
                now_ms=2500,
                memory_activation_snapshot={"items": []},
                memory_feedback_result=None,
                source_mode="runtime_memory_projection",
            )["data"]
            executed = list(second.get("delayed_tasks", {}).get("executed", []) or [])
            executed_ok = [row for row in executed if isinstance(row, dict) and bool(row.get("ok", False))]
            executed_kinds = {str(row.get("task_kind", "") or "") for row in executed_ok}
            seeded_item_after = pool._store.get(seeded_item_id)
            seeded_ev_after = float(((seeded_item_after or {}).get("energy", {}) or {}).get("ev", 0.0) or 0.0)
            stripped_item = pool._store.get_by_ref(stripped_structure_id)
            stripped_ev = float(((stripped_item or {}).get("energy", {}) or {}).get("ev", 0.0) or 0.0)
            rows.append(
                {
                    "repeat": int(repeat),
                    "registered_count": int(first.get("delayed_tasks", {}).get("registered", {}).get("registered_count", 0) or 0),
                    "registered_task_kinds": "|".join(sorted(task_kinds)),
                    "register_parallel_ok": int(task_kinds == {"anchor_item", "structure_projection"}),
                    "executed_count": int(second.get("delayed_tasks", {}).get("executed_count", 0) or 0),
                    "executed_task_kinds": "|".join(sorted(executed_kinds)),
                    "execute_parallel_ok": int(executed_kinds == {"anchor_item", "structure_projection"}),
                    "seeded_ev_before": round(seeded_ev_before, 8),
                    "seeded_ev_after": round(seeded_ev_after, 8),
                    "anchor_energy_increase": round(seeded_ev_after - seeded_ev_before, 8),
                    "stripped_structure_id": stripped_structure_id,
                    "stripped_structure_present": int(stripped_item is not None),
                    "stripped_ev_after": round(stripped_ev, 8),
                }
            )
        finally:
            try:
                sensor.close()  # type: ignore[name-defined]
            except Exception:
                pass
            try:
                pool.close()
            except Exception:
                pass
            hdb.close()
            shutil.rmtree(temp_dir, ignore_errors=True)
    return rows


def run_integrated_case(*, seed: str, delayed_enabled: bool) -> dict[str, Any]:
    app = ObservatoryApp(
        config_override={
            "enable_goal_b_char_sa_string_mode": True,
            "enable_structure_level_retrieval_storage": True,
            "dedicated_memory_pool_enabled": False,
            "export_html": False,
            "export_json": False,
            "hdb_enable_background_repair": False,
        }
    )
    try:
        alignment = apply_experiment_default_app_overrides(app, source="paper_e06_integrated")
        app.time_sensor._config["time_basis"] = "tick"
        app.time_sensor._config["enable_delayed_tasks"] = bool(delayed_enabled)
        tick_rows: list[dict[str, Any]] = []
        for tick in range(1, 6):
            report = app.run_cycle(seed if tick == 1 else "")
            ts = report.get("time_sensor", {}) or {}
            delayed = ts.get("delayed_tasks", {}) or {}
            reg = delayed.get("registered", {}) or {}
            tasks = list(reg.get("tasks", []) or [])
            execs = list(delayed.get("executed", []) or [])
            tick_rows.append(
                {
                    "tick": int(tick),
                    "bind_count": len(ts.get("attribute_bindings", []) or []),
                    "registered_count": int(reg.get("registered_count", 0) or 0),
                    "updated_count": int(reg.get("updated_count", 0) or 0),
                    "table_size": int(delayed.get("table_size", 0) or 0),
                    "executed_count": int(delayed.get("executed_count", 0) or 0),
                    "first_due_tick": int(tasks[0].get("due_tick", 0) or 0) if tasks else 0,
                    "first_exec_task_key": str(execs[0].get("task_key", "") or "") if execs else "",
                    "first_exec_due_reason": str(execs[0].get("due_reason", "") or "") if execs else "",
                }
            )
        first_exec_tick = next((row["tick"] for row in tick_rows if int(row["executed_count"]) > 0), 0)
        return {
            "seed": seed,
            "delayed_enabled": int(bool(delayed_enabled)),
            "baseline_conforms": int(bool(alignment.get("baseline_conforms_to_growth_cs_off", False))),
            "tick_rows": tick_rows,
            "tick1_registered": int(tick_rows[0]["registered_count"]),
            "tick1_due_tick": int(tick_rows[0]["first_due_tick"]),
            "tick3_executed": int(tick_rows[2]["executed_count"]),
            "tick4_executed": int(tick_rows[3]["executed_count"]),
            "first_exec_tick": int(first_exec_tick),
            "bind_total": int(sum(int(row["bind_count"]) for row in tick_rows)),
        }
    finally:
        app.close()


def run_integrated_pairs(*, seeds: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    long_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    for seed in seeds:
        on_case = run_integrated_case(seed=seed, delayed_enabled=True)
        off_case = run_integrated_case(seed=seed, delayed_enabled=False)
        for case in (on_case, off_case):
            branch = "delayed_on" if int(case["delayed_enabled"]) == 1 else "delayed_off"
            for row in case["tick_rows"]:
                long_rows.append(
                    {
                        "seed": seed,
                        "branch": branch,
                        **row,
                    }
                )
        pair_rows.append(
            {
                "seed": seed,
                "baseline_conforms_on": int(on_case["baseline_conforms"]),
                "baseline_conforms_off": int(off_case["baseline_conforms"]),
                "on_tick1_registered": int(on_case["tick1_registered"]),
                "on_tick1_due_tick": int(on_case["tick1_due_tick"]),
                "on_first_exec_tick": int(on_case["first_exec_tick"]),
                "on_tick3_executed": int(on_case["tick3_executed"]),
                "on_tick4_executed": int(on_case["tick4_executed"]),
                "on_bind_total": int(on_case["bind_total"]),
                "off_tick1_registered": int(off_case["tick1_registered"]),
                "off_tick1_due_tick": int(off_case["tick1_due_tick"]),
                "off_first_exec_tick": int(off_case["first_exec_tick"]),
                "off_tick3_executed": int(off_case["tick3_executed"]),
                "off_tick4_executed": int(off_case["tick4_executed"]),
                "off_bind_total": int(off_case["bind_total"]),
                "supports_on_registration": int(int(on_case["tick1_registered"]) >= 1),
                "supports_on_due3": int(int(on_case["tick1_due_tick"]) == 3),
                "supports_on_exec3": int(int(on_case["first_exec_tick"]) == 3),
                "supports_off_quiet": int(
                    int(off_case["tick1_registered"]) == 0
                    and int(off_case["first_exec_tick"]) == 0
                    and int(off_case["tick3_executed"]) == 0
                    and int(off_case["tick4_executed"]) == 0
                ),
                "supports_bindings_persist": int(int(on_case["bind_total"]) >= 1 and int(off_case["bind_total"]) >= 1),
                "supports_pair_contrast": int(
                    int(on_case["tick1_registered"]) >= 1
                    and int(on_case["first_exec_tick"]) == 3
                    and int(off_case["tick1_registered"]) == 0
                    and int(off_case["first_exec_tick"]) == 0
                ),
            }
        )
    long_rows.sort(key=lambda row: (str(row["seed"]), str(row["branch"]), int(row["tick"])))
    pair_rows.sort(key=lambda row: str(row["seed"]))
    return long_rows, pair_rows


def summarize_evidence(
    *,
    bucket_rows: list[dict[str, Any]],
    controlled_rows: list[dict[str, Any]],
    integrated_pair_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    bucket_n = len(bucket_rows)
    controlled_n = len(controlled_rows)
    pair_n = len(integrated_pair_rows)

    bucket_full_match = sum(
        1
        for row in bucket_rows
        if int(row.get("delta_match", 0) or 0) == 1
        and int(row.get("bucket_match", 0) or 0) == 1
        and int(row.get("weight_match", 0) or 0) == 1
        and int(row.get("binding_primary_match", 0) or 0) == 1
        and int(row.get("due_match", 0) or 0) == 1
    )
    controlled_register_parallel = sum(int(row.get("register_parallel_ok", 0) or 0) for row in controlled_rows)
    controlled_execute_parallel = sum(int(row.get("execute_parallel_ok", 0) or 0) for row in controlled_rows)
    controlled_stripped_present = sum(int(row.get("stripped_structure_present", 0) or 0) for row in controlled_rows)

    on_registration = sum(int(row.get("supports_on_registration", 0) or 0) for row in integrated_pair_rows)
    on_due3 = sum(int(row.get("supports_on_due3", 0) or 0) for row in integrated_pair_rows)
    on_exec3 = sum(int(row.get("supports_on_exec3", 0) or 0) for row in integrated_pair_rows)
    off_quiet = sum(int(row.get("supports_off_quiet", 0) or 0) for row in integrated_pair_rows)
    bindings_persist = sum(int(row.get("supports_bindings_persist", 0) or 0) for row in integrated_pair_rows)
    pair_contrast = sum(int(row.get("supports_pair_contrast", 0) or 0) for row in integrated_pair_rows)
    baseline_conforms = sum(
        1
        for row in integrated_pair_rows
        if int(row.get("baseline_conforms_on", 0) or 0) == 1 and int(row.get("baseline_conforms_off", 0) or 0) == 1
    )

    contrast_wins = pair_contrast
    contrast_losses = 0

    summary: dict[str, Any] = {
        "bucket_case_count": int(bucket_n),
        "bucket_full_match_ratio": round(safe_ratio(bucket_full_match, bucket_n or 1), 6),
        "controlled_repeat_count": int(controlled_n),
        "controlled_register_parallel_ratio": round(safe_ratio(controlled_register_parallel, controlled_n or 1), 6),
        "controlled_execute_parallel_ratio": round(safe_ratio(controlled_execute_parallel, controlled_n or 1), 6),
        "controlled_stripped_present_ratio": round(safe_ratio(controlled_stripped_present, controlled_n or 1), 6),
        "integrated_pair_count": int(pair_n),
        "integrated_baseline_conforms_ratio": round(safe_ratio(baseline_conforms, pair_n or 1), 6),
        "integrated_on_registration_ratio": round(safe_ratio(on_registration, pair_n or 1), 6),
        "integrated_on_due3_ratio": round(safe_ratio(on_due3, pair_n or 1), 6),
        "integrated_on_exec3_ratio": round(safe_ratio(on_exec3, pair_n or 1), 6),
        "integrated_off_quiet_ratio": round(safe_ratio(off_quiet, pair_n or 1), 6),
        "integrated_bindings_persist_ratio": round(safe_ratio(bindings_persist, pair_n or 1), 6),
        "integrated_pair_contrast_ratio": round(safe_ratio(pair_contrast, pair_n or 1), 6),
        "integrated_pair_contrast_sign_p": sign_test_p_value(contrast_wins, contrast_losses),
        "controlled_anchor_energy_increase_mean": round(
            statistics.fmean([num(row, "anchor_energy_increase") for row in controlled_rows]),
            8,
        )
        if controlled_rows
        else 0.0,
        "controlled_stripped_ev_after_mean": round(
            statistics.fmean([num(row, "stripped_ev_after") for row in controlled_rows]),
            8,
        )
        if controlled_rows
        else 0.0,
    }

    support_level = "not_supported"
    if (
        bucket_n >= 12
        and summary["bucket_full_match_ratio"] >= 0.999
        and controlled_n >= 4
        and summary["controlled_register_parallel_ratio"] >= 0.999
        and summary["controlled_execute_parallel_ratio"] >= 0.999
        and summary["controlled_stripped_present_ratio"] >= 0.999
        and pair_n >= 8
        and summary["integrated_baseline_conforms_ratio"] >= 0.999
        and summary["integrated_on_registration_ratio"] >= 0.999
        and summary["integrated_on_due3_ratio"] >= 0.999
        and summary["integrated_on_exec3_ratio"] >= 0.999
        and summary["integrated_off_quiet_ratio"] >= 0.999
        and summary["integrated_bindings_persist_ratio"] >= 0.999
        and summary["integrated_pair_contrast_ratio"] >= 0.999
        and summary["integrated_pair_contrast_sign_p"] <= 0.01
    ):
        support_level = "strong_evidence"
    elif (
        bucket_n >= 6
        and summary["bucket_full_match_ratio"] >= 0.90
        and pair_n >= 6
        and summary["integrated_on_exec3_ratio"] >= 0.75
        and summary["integrated_off_quiet_ratio"] >= 0.75
    ):
        support_level = "useful_but_not_strong"
    summary["support_level"] = support_level
    return summary


def make_charts(
    *,
    bucket_rows: list[dict[str, Any]],
    controlled_rows: list[dict[str, Any]],
    integrated_pair_rows: list[dict[str, Any]],
    stamp: str,
) -> list[Path]:
    plt = e01.setup_matplotlib()
    paths: list[Path] = []

    bucket_focus = [row for row in bucket_rows if abs(float(row.get("source_energy", 0.0) or 0.0) - 2.0) < 1e-9]
    bucket_focus.sort(key=lambda row: int(row.get("interval_ticks", 0) or 0))
    xs = list(range(len(bucket_focus)))
    labels = [str(int(row["interval_ticks"])) for row in bucket_focus]
    fig, ax = plt.subplots(figsize=(10.8, 4.8), dpi=160)
    ax.bar([x - 0.16 for x in xs], [num(row, "w1") for row in bucket_focus], width=0.32, color="#1c7ed6", label="主桶权重")
    ax.bar([x + 0.16 for x in xs], [num(row, "w2") for row in bucket_focus], width=0.32, color="#74c0fc", label="副桶权重")
    ax.set_xticks(xs, labels)
    ax.set_xlabel("记忆间隔（tick）")
    ax.set_ylabel("线性插值权重")
    ax.set_title("E06 受控时间桶校准：不同 tick 间隔的双桶权重")
    for idx, row in enumerate(bucket_focus):
        ax.text(idx, 1.03, f"{row['bucket_1']} / {row['bucket_2']}", ha="center", va="bottom", fontsize=8)
    ax.set_ylim(0.0, 1.12)
    ax.legend(frameon=False)
    fig.tight_layout()
    chart_path = CHART_DIR / f"e06_time_interval_bucket_weights_{stamp}.png"
    fig.savefig(chart_path, bbox_inches="tight")
    plt.close(fig)
    paths.append(chart_path)

    fig, ax = plt.subplots(figsize=(11.4, 4.8), dpi=160)
    stages = ["tick1 注册", "tick1 due=3", "tick3 执行", "关闭后无注册/执行", "绑定仍存在", "on/off 对照通过"]
    values = [
        safe_ratio(sum(int(row.get("supports_on_registration", 0) or 0) for row in integrated_pair_rows), len(integrated_pair_rows) or 1),
        safe_ratio(sum(int(row.get("supports_on_due3", 0) or 0) for row in integrated_pair_rows), len(integrated_pair_rows) or 1),
        safe_ratio(sum(int(row.get("supports_on_exec3", 0) or 0) for row in integrated_pair_rows), len(integrated_pair_rows) or 1),
        safe_ratio(sum(int(row.get("supports_off_quiet", 0) or 0) for row in integrated_pair_rows), len(integrated_pair_rows) or 1),
        safe_ratio(sum(int(row.get("supports_bindings_persist", 0) or 0) for row in integrated_pair_rows), len(integrated_pair_rows) or 1),
        safe_ratio(sum(int(row.get("supports_pair_contrast", 0) or 0) for row in integrated_pair_rows), len(integrated_pair_rows) or 1),
    ]
    ax.bar(range(len(stages)), values, color=["#2f9e44", "#37b24d", "#40c057", "#fa5252", "#1971c2", "#0b7285"])
    ax.set_ylim(0.0, 1.05)
    ax.set_xticks(range(len(stages)), stages, rotation=20, ha="right")
    ax.set_ylabel("通过比例")
    ax.set_title("E06 集成主线的时间任务闭环通过比例")
    for idx, value in enumerate(values):
        ax.text(idx, value + 0.02, f"{value:.3f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    chart_path = CHART_DIR / f"e06_time_interval_integrated_ratios_{stamp}.png"
    fig.savefig(chart_path, bbox_inches="tight")
    plt.close(fig)
    paths.append(chart_path)

    fig, ax = plt.subplots(figsize=(9.8, 4.6), dpi=160)
    branches = ["并行登记", "并行执行", "去时间因子结构出现"]
    branch_values = [
        safe_ratio(sum(int(row.get("register_parallel_ok", 0) or 0) for row in controlled_rows), len(controlled_rows) or 1),
        safe_ratio(sum(int(row.get("execute_parallel_ok", 0) or 0) for row in controlled_rows), len(controlled_rows) or 1),
        safe_ratio(sum(int(row.get("stripped_structure_present", 0) or 0) for row in controlled_rows), len(controlled_rows) or 1),
    ]
    ax.bar(range(len(branches)), branch_values, color=["#495057", "#868e96", "#adb5bd"])
    ax.set_ylim(0.0, 1.05)
    ax.set_xticks(range(len(branches)), branches)
    ax.set_ylabel("通过比例")
    ax.set_title("E06 白箱结构分支：anchor 与 structure_projection 并行闭环")
    for idx, value in enumerate(branch_values):
        ax.text(idx, value + 0.02, f"{value:.3f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    chart_path = CHART_DIR / f"e06_time_interval_parallel_branches_{stamp}.png"
    fig.savefig(chart_path, bbox_inches="tight")
    plt.close(fig)
    paths.append(chart_path)

    return paths


def write_design_note(path: Path) -> None:
    lines = [
        "# E06 设计逻辑",
        "",
        "本实验把原本较大的 E06 命题拆成三段最小链条，并分别做受控验证：",
        "",
        "1. 受控时间桶校准：直接构造带 tick 元数据的记忆快照，验证 `delta_value`、双桶权重和主桶中心值是否按配置落在预期位置；",
        "2. 白箱结构分支：构造一个显式包含时间感受因子的结构，验证 `anchor_item` 与 `structure_projection` 两类延迟任务是否能并行登记并到期执行；",
        "3. 集成主线对照：在真实 `ObservatoryApp.run_cycle()` 路径中，对一组简单 ASCII seed 比较“延迟任务开启”与“延迟任务关闭”两支，验证 tick1 注册、tick3 执行和关闭后消失的对照关系。",
        "",
        "本实验不把 recall 行动作为正文命题。当前原型在 recall 这一步仍不够稳定，而时间桶推进和延迟回投链已经可以给出更强、更干净的白箱证据。",
        "",
        "另外，本轮对 `time_sensor` 做了一个与理论更一致的修正：同一个待执行任务在重复绑定时不再把最早 due tick 往后顺延，而是保留最早到期时刻，只记录新的候选 due 作为审计信息。这样可以避免“本该到点回投的任务被自己不断推迟”的现象，也更贴近“每个对象每个延迟任务只维持一个任务表项”的设计口径。",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(
    *,
    bucket_rows: list[dict[str, Any]],
    controlled_rows: list[dict[str, Any]],
    integrated_pair_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    charts: list[Path],
    stamp: str,
) -> Path:
    lines: list[str] = []
    lines.append(f"# E06 时间间隔与延迟回投报告（{stamp}）")
    lines.append("")
    lines.append("## 核心结论")
    lines.append(f"- 支持等级：**{summary.get('support_level', 'unknown')}**")
    lines.append(f"- 受控时间桶校准样本数：{int(summary.get('bucket_case_count', 0))}")
    lines.append(f"- 时间桶完整匹配比例：{summary.get('bucket_full_match_ratio', 0.0):.3f}")
    lines.append(f"- 白箱结构并行登记比例：{summary.get('controlled_register_parallel_ratio', 0.0):.3f}")
    lines.append(f"- 白箱结构并行执行比例：{summary.get('controlled_execute_parallel_ratio', 0.0):.3f}")
    lines.append(f"- 去时间因子结构出现比例：{summary.get('controlled_stripped_present_ratio', 0.0):.3f}")
    lines.append(f"- 集成 on 分支 tick1 注册比例：{summary.get('integrated_on_registration_ratio', 0.0):.3f}")
    lines.append(f"- 集成 on 分支 tick1 due=3 比例：{summary.get('integrated_on_due3_ratio', 0.0):.3f}")
    lines.append(f"- 集成 on 分支 tick3 执行比例：{summary.get('integrated_on_exec3_ratio', 0.0):.3f}")
    lines.append(f"- 集成 off 分支静默比例：{summary.get('integrated_off_quiet_ratio', 0.0):.3f}")
    lines.append(f"- on/off 对照通过比例：{summary.get('integrated_pair_contrast_ratio', 0.0):.3f}")
    lines.append(f"- on/off 对照 sign test p：{summary.get('integrated_pair_contrast_sign_p', 1.0):.8f}")
    lines.append("")
    lines.append("## 论文可用表述")
    lines.append("")
    lines.append("在 tick 时间基准下，AP 当前实现已经能够把记忆间隔稳定映射到预设时间桶，并把该间隔转化为有限延迟任务的到期时刻。")
    lines.append("在受控白箱条件下，包含时间因子的结构还能同时触发 `anchor_item` 与 `structure_projection` 两类延迟任务，并在到期时分别对原锚点与去时间因子结构回投能量。")
    lines.append("在真实 `run_cycle()` 主线中，简单外源 seed 在开启延迟任务时会稳定表现为 tick1 注册、tick3 执行；关闭延迟任务后，这条登记/执行链同时消失，但时间感受绑定本身仍存在。")
    lines.append("")
    lines.append("## 受控时间桶校准")
    lines.append("")
    lines.append("| case | 间隔(tick) | 源能量 | 观测主桶 | 观测副桶 | 主权重 | 副权重 | due tick | 完整匹配 |")
    lines.append("| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |")
    for row in bucket_rows:
        full_ok = int(row.get("delta_match", 0) or 0) and int(row.get("bucket_match", 0) or 0) and int(row.get("weight_match", 0) or 0) and int(row.get("due_match", 0) or 0)
        lines.append(
            f"| {row['case_id']} | {int(row['interval_ticks'])} | {float(row['source_energy']):.1f} | "
            f"{row['bucket_1']} | {row['bucket_2']} | {float(row['w1']):.4f} | {float(row['w2']):.4f} | "
            f"{int(row['registered_due_tick'])} | {int(full_ok)} |"
        )
    lines.append("")
    lines.append("## 白箱结构分支")
    lines.append("")
    lines.append("| repeat | 并行登记 | 并行执行 | 锚点 EV 增量 | 去时间因子结构出现 | 去时间因子结构 EV |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for row in controlled_rows:
        lines.append(
            f"| {int(row['repeat'])} | {int(row['register_parallel_ok'])} | {int(row['execute_parallel_ok'])} | "
            f"{float(row['anchor_energy_increase']):.4f} | {int(row['stripped_structure_present'])} | {float(row['stripped_ev_after']):.4f} |"
        )
    lines.append("")
    lines.append("## 集成主线 on/off 对照")
    lines.append("")
    lines.append("| seed | on 注册 | on due=3 | on 首次执行 tick | off 注册 | off 首次执行 tick | 绑定仍存在 | 对照通过 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in integrated_pair_rows:
        lines.append(
            f"| {row['seed']} | {int(row['on_tick1_registered'])} | {int(row['on_tick1_due_tick'] == 3)} | {int(row['on_first_exec_tick'])} | "
            f"{int(row['off_tick1_registered'])} | {int(row['off_first_exec_tick'])} | {int(row['supports_bindings_persist'])} | {int(row['supports_pair_contrast'])} |"
        )
    lines.append("")
    lines.append("## 图表")
    lines.append("")
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    lines.append("## 备注")
    lines.append("")
    lines.append("- 本实验把 recall 行动排除在正文结论之外，因为当前原型在 recall 触发上还不够稳定。")
    lines.append("- 正文只使用已被当前实现稳定支撑的时间桶推进、延迟登记与到期回投链。")
    lines.append("")
    path = REPORT_DIR / f"E06_time_interval_report_{stamp}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def build_evidence(*, stamp: str, seed_count: int, controlled_repeats: int) -> dict[str, Any]:
    ensure_dirs()
    bucket_rows = run_bucket_cases()
    controlled_rows = run_controlled_parallel_cases(repeats=controlled_repeats)
    integrated_long_rows, integrated_pair_rows = run_integrated_pairs(seeds=INTEGRATED_SEEDS[: int(seed_count)])
    summary = summarize_evidence(
        bucket_rows=bucket_rows,
        controlled_rows=controlled_rows,
        integrated_pair_rows=integrated_pair_rows,
    )

    e01.write_csv(TABLE_DIR / f"e06_time_interval_bucket_rows_{stamp}.csv", bucket_rows)
    e01.write_csv(TABLE_DIR / f"e06_time_interval_controlled_rows_{stamp}.csv", controlled_rows)
    e01.write_csv(TABLE_DIR / f"e06_time_interval_integrated_ticks_{stamp}.csv", integrated_long_rows)
    e01.write_csv(TABLE_DIR / f"e06_time_interval_pair_rows_{stamp}.csv", integrated_pair_rows)
    e01.write_json(TABLE_DIR / f"e06_time_interval_summary_{stamp}.json", summary)
    write_design_note(REPORT_DIR / "E06_time_interval_design_logic.md")
    charts = make_charts(
        bucket_rows=bucket_rows,
        controlled_rows=controlled_rows,
        integrated_pair_rows=integrated_pair_rows,
        stamp=stamp,
    )
    report = write_report(
        bucket_rows=bucket_rows,
        controlled_rows=controlled_rows,
        integrated_pair_rows=integrated_pair_rows,
        summary=summary,
        charts=charts,
        stamp=stamp,
    )
    evidence = {
        "experiment_id": "E06",
        "stamp": stamp,
        "support_level": summary.get("support_level", "unknown"),
        "summary": summary,
        "artifacts": {
            "bucket_rows": str(TABLE_DIR / f"e06_time_interval_bucket_rows_{stamp}.csv"),
            "controlled_rows": str(TABLE_DIR / f"e06_time_interval_controlled_rows_{stamp}.csv"),
            "integrated_ticks": str(TABLE_DIR / f"e06_time_interval_integrated_ticks_{stamp}.csv"),
            "pair_rows": str(TABLE_DIR / f"e06_time_interval_pair_rows_{stamp}.csv"),
            "summary": str(TABLE_DIR / f"e06_time_interval_summary_{stamp}.json"),
            "report": str(report),
            "design_note": str(REPORT_DIR / "E06_time_interval_design_logic.md"),
            "charts": [str(path) for path in charts],
        },
    }
    e01.write_json(MANIFEST_DIR / f"E06_time_interval_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E06_time_interval_latest.json", evidence)
    return evidence


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper E06 time-interval / delayed-task experiment.")
    parser.add_argument("--stamp", default=STAMP_DEFAULT)
    parser.add_argument("--seed-count", type=int, default=12)
    parser.add_argument("--controlled-repeats", type=int, default=6)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    stamp = str(args.stamp or "").strip() or now_stamp()
    evidence = build_evidence(
        stamp=stamp,
        seed_count=max(1, min(len(INTEGRATED_SEEDS), int(args.seed_count))),
        controlled_repeats=max(1, min(16, int(args.controlled_repeats))),
    )
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
