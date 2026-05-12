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

from _reproduction_paths import AP_ROOT, ARTIFACT_ROOT, ATTACHMENT_ROOT

if str(AP_ROOT) not in sys.path:
    sys.path.insert(0, str(AP_ROOT))

import run_paper_e01_experiment as e01
import run_paper_e11_energy_graph_experiment as e11
from hdb import HDB


E17_ROOT = ARTIFACT_ROOT / "E17_internal_narrative_chain"
TABLE_DIR = E17_ROOT / "tables"
CHART_DIR = E17_ROOT / "charts"
REPORT_DIR = E17_ROOT / "reports"
MANIFEST_DIR = E17_ROOT / "manifests"

STAMP_DEFAULT = "e17_final_v1"


@dataclass(frozen=True)
class FamilySpec:
    family: str
    chain_weight_1: float
    chain_weight_2: float
    terminal_weight: float
    branch_primary: float
    branch_secondary: float
    source_ev: float
    low_budget_ev: float


FAMILY_SPECS: list[FamilySpec] = [
    FamilySpec("F01", 0.82, 0.80, 0.78, 0.72, 0.40, 1.00, 0.012),
    FamilySpec("F02", 0.81, 0.79, 0.77, 0.71, 0.41, 1.01, 0.013),
    FamilySpec("F03", 0.80, 0.78, 0.76, 0.70, 0.42, 1.02, 0.014),
    FamilySpec("F04", 0.83, 0.81, 0.79, 0.73, 0.39, 1.03, 0.015),
    FamilySpec("F05", 0.84, 0.82, 0.80, 0.74, 0.38, 1.04, 0.016),
    FamilySpec("F06", 0.79, 0.77, 0.75, 0.69, 0.43, 1.05, 0.017),
    FamilySpec("F07", 0.78, 0.76, 0.74, 0.68, 0.44, 1.06, 0.018),
    FamilySpec("F08", 0.85, 0.83, 0.81, 0.75, 0.37, 1.07, 0.019),
    FamilySpec("F09", 0.82, 0.81, 0.76, 0.72, 0.36, 1.08, 0.020),
    FamilySpec("F10", 0.81, 0.80, 0.75, 0.71, 0.35, 1.09, 0.021),
    FamilySpec("F11", 0.84, 0.79, 0.78, 0.74, 0.34, 1.10, 0.022),
    FamilySpec("F12", 0.83, 0.78, 0.77, 0.73, 0.33, 1.11, 0.023),
]

BRANCH_ORDER = (
    "chain_follow",
    "wrong_seed_control",
    "low_budget_control",
    "no_carry_control",
    "branch_switch",
    "terminal_stop",
)

BRANCH_LABELS = {
    "chain_follow": "连续承接",
    "wrong_seed_control": "错误种子对照",
    "low_budget_control": "低预算剪枝",
    "no_carry_control": "无承接对照",
    "branch_switch": "权重转向",
    "terminal_stop": "终端停止",
}


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


def setup_hdb(tmp_dir: str, *, max_rounds: int = 1, min_budget: float = 0.03) -> HDB:
    return HDB(
        config_override={
            "data_dir": tmp_dir,
            "enable_background_repair": False,
            "induction_energy_graph_v2_enabled": True,
            "induction_energy_graph_v2_max_rounds": int(max_rounds),
            "induction_energy_graph_v2_root_er_decay_ratio": 0.82,
            "induction_energy_graph_v2_root_source_ev_ratio": 1.0,
            "induction_energy_graph_v2_frontier_ev_ratio": 1.0,
            "induction_energy_graph_v2_er_round_ratio": 1.0,
            "induction_energy_graph_v2_min_frontier_ev": 0.02,
            "induction_energy_graph_v2_min_budget": float(min_budget),
            "induction_energy_graph_v2_max_frontier_nodes_per_source": 0,
            "induction_energy_graph_v2_target_top_k": 0,
            "ev_propagation_threshold": 0.02,
            "er_induction_threshold": 0.02,
            "induction_min_entry_base_weight": 0.0,
            "owner_db_runtime_budget_enabled": False,
        }
    )


def token(spec: FamilySpec, suffix: str) -> str:
    return f"{spec.family}_{suffix}"


def build_graph(hdb: HDB, *, spec: FamilySpec, branch: str) -> dict[str, Any]:
    prefix = f"e17_{spec.family}_{branch}"
    structures = {
        "A": e11.store_packet_as_structure(hdb, token(spec, "A"), prefix=prefix, trace_id=f"{prefix}_A"),
        "AB": e11.store_packet_as_structure(hdb, token(spec, "AB"), prefix=prefix, trace_id=f"{prefix}_AB"),
        "ABC": e11.store_packet_as_structure(hdb, token(spec, "ABC"), prefix=prefix, trace_id=f"{prefix}_ABC"),
        "ABCD": e11.store_packet_as_structure(hdb, token(spec, "ABCD"), prefix=prefix, trace_id=f"{prefix}_ABCD"),
        "D": e11.store_packet_as_structure(hdb, token(spec, "D"), prefix=prefix, trace_id=f"{prefix}_D"),
        "DX": e11.store_packet_as_structure(hdb, token(spec, "DX"), prefix=prefix, trace_id=f"{prefix}_DX"),
        "ABY": e11.store_packet_as_structure(hdb, token(spec, "ABY"), prefix=prefix, trace_id=f"{prefix}_ABY"),
        "ABYZ": e11.store_packet_as_structure(hdb, token(spec, "ABYZ"), prefix=prefix, trace_id=f"{prefix}_ABYZ"),
    }
    terminal_memory = e11.append_memory(
        hdb,
        label=f"{spec.family} chain terminal memory ABCD",
        structure_id=structures["ABCD"]["id"],
        trace_id=f"{prefix}_terminal_memory",
    )
    distractor_memory = e11.append_memory(
        hdb,
        label=f"{spec.family} distractor terminal memory DX",
        structure_id=structures["DX"]["id"],
        trace_id=f"{prefix}_distractor_memory",
    )
    switch_memory = e11.append_memory(
        hdb,
        label=f"{spec.family} branch switch terminal memory ABYZ",
        structure_id=structures["ABYZ"]["id"],
        trace_id=f"{prefix}_switch_memory",
    )

    secondary = float(spec.branch_secondary)
    primary = float(spec.branch_primary)
    if branch == "branch_switch":
        primary, secondary = secondary, primary

    e11.add_edge(hdb, owner=structures["A"], target=structures["AB"], weight=spec.chain_weight_1, residual="B")
    e11.add_edge(hdb, owner=structures["AB"], target=structures["ABC"], weight=primary, residual="C")
    e11.add_edge(hdb, owner=structures["AB"], target=structures["ABY"], weight=secondary, residual="Y")
    e11.add_edge(
        hdb,
        owner=structures["ABC"],
        target=structures["ABCD"],
        weight=spec.terminal_weight,
        residual="D",
        memory_id=terminal_memory,
    )
    e11.add_edge(
        hdb,
        owner=structures["ABY"],
        target=structures["ABYZ"],
        weight=spec.terminal_weight,
        residual="Z",
        memory_id=switch_memory,
    )
    e11.add_edge(
        hdb,
        owner=structures["D"],
        target=structures["DX"],
        weight=spec.chain_weight_1,
        residual="X",
        memory_id=distractor_memory,
    )
    return {
        "structures": structures,
        "terminal_memory": terminal_memory,
        "distractor_memory": distractor_memory,
        "switch_memory": switch_memory,
    }


def run_induction_step(
    hdb: HDB,
    *,
    source_structure_id: str,
    display: str,
    ev: float,
    trace_id: str,
) -> dict[str, Any]:
    result = hdb.run_induction_propagation(
        state_snapshot={
            "summary": {"active_item_count": 1},
            "top_items": [
                {
                    "id": f"runtime_{trace_id}",
                    "ref_object_type": "st",
                    "ref_object_id": source_structure_id,
                    "display": display,
                    "display_text": display,
                    "er": 0.0,
                    "ev": round(float(ev), 8),
                }
            ],
        },
        trace_id=trace_id,
        tick_id=trace_id,
        max_source_items=1,
        enable_ev_propagation=True,
        enable_er_induction=False,
    )
    if not result.get("success", False):
        raise RuntimeError(f"run_induction_propagation failed: {result}")
    return result.get("data", {}) or {}


def top_target(data: dict[str, Any]) -> dict[str, Any]:
    targets = list(data.get("induction_targets", []) or [])
    if not targets:
        return {}
    return max(targets, key=lambda row: float(row.get("delta_ev", 0.0) or 0.0))


def target_hit(data: dict[str, Any], *, structure_id: str = "", memory_id: str = "") -> int:
    for row in list(data.get("induction_targets", []) or []):
        if structure_id and str(row.get("target_structure_id", "")) == str(structure_id):
            return 1
        if memory_id and str(row.get("memory_id", "")) == str(memory_id):
            return 1
    return 0


def memory_target_count(data: dict[str, Any]) -> int:
    return len([row for row in list(data.get("induction_targets", []) or []) if str(row.get("projection_kind", "")) == "memory"])


def run_case(spec: FamilySpec, branch: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    tmp_dir = tempfile.mkdtemp(prefix=f"paper_e17_{spec.family}_{branch}_")
    max_rounds = 1
    min_budget = 0.03
    if branch == "low_budget_control":
        min_budget = 0.05
    hdb = setup_hdb(tmp_dir, max_rounds=max_rounds, min_budget=min_budget)
    step_rows: list[dict[str, Any]] = []
    try:
        graph = build_graph(hdb, spec=spec, branch=branch)
        st = graph["structures"]

        if branch == "wrong_seed_control":
            seeds = [("D", st["D"]["id"], spec.source_ev), ("DX", st["DX"]["id"], spec.source_ev)]
            expected = ["DX", "memory:distractor"]
            target_chain = ["AB", "ABC", "memory:terminal"]
        elif branch == "low_budget_control":
            seeds = [("A", st["A"]["id"], spec.low_budget_ev)]
            expected = ["none"]
            target_chain = ["AB", "ABC", "memory:terminal"]
        elif branch == "no_carry_control":
            seeds = [
                ("A", st["A"]["id"], spec.source_ev),
                ("A", st["A"]["id"], spec.source_ev),
                ("A", st["A"]["id"], spec.source_ev),
            ]
            expected = ["AB", "AB", "AB"]
            target_chain = ["AB", "ABC", "memory:terminal"]
        elif branch == "branch_switch":
            seeds = [
                ("A", st["A"]["id"], spec.source_ev),
                ("AB", st["AB"]["id"], spec.source_ev),
                ("ABY", st["ABY"]["id"], spec.source_ev),
            ]
            expected = ["AB", "ABY", "memory:switch"]
            target_chain = ["AB", "ABY", "memory:switch"]
        elif branch == "terminal_stop":
            seeds = [
                ("A", st["A"]["id"], spec.source_ev),
                ("AB", st["AB"]["id"], spec.source_ev),
                ("ABC", st["ABC"]["id"], spec.source_ev),
            ]
            expected = ["AB", "ABC", "memory:terminal"]
            target_chain = ["AB", "ABC", "memory:terminal"]
        else:
            seeds = [
                ("A", st["A"]["id"], spec.source_ev),
                ("AB", st["AB"]["id"], spec.source_ev),
                ("ABC", st["ABC"]["id"], spec.source_ev),
            ]
            expected = ["AB", "ABC", "memory:terminal"]
            target_chain = ["AB", "ABC", "memory:terminal"]

        top_sequence: list[str] = []
        next_seed_from_previous_top_count = 0
        terminal_step_index = -1
        terminal_followup_target_count = 0
        carried_source_ids: list[str] = []
        previous_top_structure_id = ""

        for idx, (source_key, source_id, ev) in enumerate(seeds, start=1):
            if previous_top_structure_id and source_id == previous_top_structure_id:
                next_seed_from_previous_top_count += 1
            carried_source_ids.append(source_key)
            data = run_induction_step(
                hdb,
                source_structure_id=source_id,
                display=source_key,
                ev=ev,
                trace_id=f"paper_e17_{spec.family}_{branch}_step{idx}_{source_key}",
            )
            top = top_target(data)
            top_structure_id = str(top.get("target_structure_id", "") or "")
            top_memory_id = str(top.get("memory_id", "") or "")
            top_kind = str(top.get("projection_kind", "") or "")
            if top_memory_id == graph["terminal_memory"]:
                top_label = "memory:terminal"
                terminal_step_index = idx
            elif top_memory_id == graph["distractor_memory"]:
                top_label = "memory:distractor"
            elif top_memory_id == graph["switch_memory"]:
                top_label = "memory:switch"
                terminal_step_index = idx
            else:
                top_label = next((key for key, value in st.items() if str(value.get("id", "")) == top_structure_id), "")
            if top_kind == "structure":
                previous_top_structure_id = top_structure_id
            else:
                previous_top_structure_id = ""
            top_sequence.append(top_label or "none")
            step_rows.append(
                {
                    "family": spec.family,
                    "branch": branch,
                    "branch_label": BRANCH_LABELS.get(branch, branch),
                    "step": idx,
                    "source_key": source_key,
                    "source_structure_id": source_id,
                    "source_ev": round(float(ev), 8),
                    "expected_top": expected[idx - 1] if idx - 1 < len(expected) else "",
                    "top_label": top_label or "none",
                    "top_projection_kind": top_kind,
                    "top_structure_id": top_structure_id,
                    "top_memory_id": top_memory_id,
                    "top_delta_ev": round(float(top.get("delta_ev", 0.0) or 0.0), 8),
                    "target_count": len(list(data.get("induction_targets", []) or [])),
                    "memory_target_count": memory_target_count(data),
                    "round_count": int(data.get("energy_graph_round_count_max", 0) or 0),
                    "depth_max": int(data.get("energy_graph_depth_max", 0) or 0),
                    "frontier_pruned_count": int(data.get("energy_graph_frontier_pruned_count", 0) or 0),
                    "hit_AB": target_hit(data, structure_id=st["AB"]["id"]),
                    "hit_ABC": target_hit(data, structure_id=st["ABC"]["id"]),
                    "hit_ABY": target_hit(data, structure_id=st["ABY"]["id"]),
                    "hit_terminal_memory": target_hit(data, memory_id=graph["terminal_memory"]),
                    "hit_switch_memory": target_hit(data, memory_id=graph["switch_memory"]),
                    "hit_distractor_memory": target_hit(data, memory_id=graph["distractor_memory"]),
                }
            )

        if branch == "terminal_stop":
            terminal_data = run_induction_step(
                hdb,
                source_structure_id=st["ABCD"]["id"],
                display="ABCD",
                ev=spec.source_ev,
                trace_id=f"paper_e17_{spec.family}_{branch}_terminal_followup",
            )
            terminal_followup_target_count = len(list(terminal_data.get("induction_targets", []) or []))
            step_rows.append(
                {
                    "family": spec.family,
                    "branch": branch,
                    "branch_label": BRANCH_LABELS.get(branch, branch),
                    "step": 4,
                    "source_key": "ABCD",
                    "source_structure_id": st["ABCD"]["id"],
                    "source_ev": round(float(spec.source_ev), 8),
                    "expected_top": "none",
                    "top_label": top_target(terminal_data).get("target_display_text", "") or "none",
                    "top_projection_kind": str(top_target(terminal_data).get("projection_kind", "") or ""),
                    "top_structure_id": str(top_target(terminal_data).get("target_structure_id", "") or ""),
                    "top_memory_id": str(top_target(terminal_data).get("memory_id", "") or ""),
                    "top_delta_ev": round(float(top_target(terminal_data).get("delta_ev", 0.0) or 0.0), 8),
                    "target_count": terminal_followup_target_count,
                    "memory_target_count": memory_target_count(terminal_data),
                    "round_count": int(terminal_data.get("energy_graph_round_count_max", 0) or 0),
                    "depth_max": int(terminal_data.get("energy_graph_depth_max", 0) or 0),
                    "frontier_pruned_count": int(terminal_data.get("energy_graph_frontier_pruned_count", 0) or 0),
                    "hit_AB": 0,
                    "hit_ABC": 0,
                    "hit_ABY": 0,
                    "hit_terminal_memory": target_hit(terminal_data, memory_id=graph["terminal_memory"]),
                    "hit_switch_memory": target_hit(terminal_data, memory_id=graph["switch_memory"]),
                    "hit_distractor_memory": target_hit(terminal_data, memory_id=graph["distractor_memory"]),
                }
            )

        expected_hits = sum(1 for idx, label in enumerate(expected) if idx < len(top_sequence) and top_sequence[idx] == label)
        chain_order_ok = int(top_sequence[: len(expected)] == expected)
        target_chain_ok = int(top_sequence[: len(target_chain)] == target_chain)
        wrong_target_quiet = int("AB" not in top_sequence and "ABC" not in top_sequence and "memory:terminal" not in top_sequence)
        low_budget_quiet = int(all(row["target_count"] == 0 for row in step_rows if row["branch"] == branch))
        no_carry_stalled = int(top_sequence == ["AB", "AB", "AB"])
        branch_switched = int(top_sequence == ["AB", "ABY", "memory:switch"])
        terminal_stopped = int(terminal_step_index == 3 and terminal_followup_target_count == 0)
        carry_ratio = safe_ratio(next_seed_from_previous_top_count, max(1, len(seeds) - 1))

        case_row = {
            "family": spec.family,
            "branch": branch,
            "branch_label": BRANCH_LABELS.get(branch, branch),
            "case_counted_steps": len(seeds),
            "source_ev": round(float(spec.source_ev), 8),
            "low_budget_ev": round(float(spec.low_budget_ev), 8),
            "expected_sequence": ">".join(expected),
            "top_sequence": ">".join(top_sequence),
            "expected_hit_ratio": round(safe_ratio(expected_hits, len(expected)), 8),
            "chain_order_ok": chain_order_ok,
            "target_chain_ok": target_chain_ok,
            "next_seed_from_previous_top_count": next_seed_from_previous_top_count,
            "next_seed_from_previous_top_ratio": round(carry_ratio, 8),
            "wrong_target_quiet": wrong_target_quiet,
            "low_budget_quiet": low_budget_quiet,
            "no_carry_stalled": no_carry_stalled,
            "branch_switched": branch_switched,
            "terminal_stopped": terminal_stopped,
            "terminal_followup_target_count": int(terminal_followup_target_count),
            "terminal_step_index": int(terminal_step_index),
            "carried_source_ids": ">".join(carried_source_ids),
        }
        return case_row, step_rows
    finally:
        hdb.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def build_family_rows(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_family: dict[str, dict[str, dict[str, Any]]] = {}
    for row in case_rows:
        by_family.setdefault(str(row.get("family", "")), {})[str(row.get("branch", ""))] = row
    family_rows: list[dict[str, Any]] = []
    for family in sorted(by_family):
        mapping = by_family[family]
        chain = mapping.get("chain_follow", {})
        wrong = mapping.get("wrong_seed_control", {})
        low = mapping.get("low_budget_control", {})
        no_carry = mapping.get("no_carry_control", {})
        switch = mapping.get("branch_switch", {})
        terminal = mapping.get("terminal_stop", {})
        row = {
            "family": family,
            "chain_follow_pass": int(
                int(chain.get("chain_order_ok", 0) or 0) == 1
                and float(chain.get("expected_hit_ratio", 0.0) or 0.0) >= 0.999
                and float(chain.get("next_seed_from_previous_top_ratio", 0.0) or 0.0) >= 0.999
            ),
            "wrong_seed_control_pass": int(int(wrong.get("wrong_target_quiet", 0) or 0) == 1),
            "low_budget_control_pass": int(int(low.get("low_budget_quiet", 0) or 0) == 1),
            "no_carry_control_pass": int(
                int(no_carry.get("no_carry_stalled", 0) or 0) == 1
                and float(no_carry.get("next_seed_from_previous_top_ratio", 0.0) or 0.0) <= 0.001
            ),
            "branch_switch_pass": int(int(switch.get("branch_switched", 0) or 0) == 1),
            "terminal_stop_pass": int(int(terminal.get("terminal_stopped", 0) or 0) == 1),
            "chain_sequence": str(chain.get("top_sequence", "")),
            "wrong_seed_sequence": str(wrong.get("top_sequence", "")),
            "no_carry_sequence": str(no_carry.get("top_sequence", "")),
            "branch_switch_sequence": str(switch.get("top_sequence", "")),
            "chain_carry_ratio": round(float(chain.get("next_seed_from_previous_top_ratio", 0.0) or 0.0), 8),
            "no_carry_ratio": round(float(no_carry.get("next_seed_from_previous_top_ratio", 0.0) or 0.0), 8),
            "terminal_followup_target_count": int(terminal.get("terminal_followup_target_count", 0) or 0),
        }
        row["all_ok"] = int(
            int(row["chain_follow_pass"]) == 1
            and int(row["wrong_seed_control_pass"]) == 1
            and int(row["low_budget_control_pass"]) == 1
            and int(row["no_carry_control_pass"]) == 1
            and int(row["branch_switch_pass"]) == 1
            and int(row["terminal_stop_pass"]) == 1
        )
        family_rows.append(row)
    return family_rows


def summarize_evidence(*, case_rows: list[dict[str, Any]], step_rows: list[dict[str, Any]], family_rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "case_count": int(len(case_rows)),
        "step_count": int(len(step_rows)),
        "family_count": int(len(family_rows)),
        "chain_follow_pass_ratio": round(safe_ratio(sum(int(row.get("chain_follow_pass", 0) or 0) for row in family_rows), len(family_rows) or 1), 6),
        "wrong_seed_control_pass_ratio": round(safe_ratio(sum(int(row.get("wrong_seed_control_pass", 0) or 0) for row in family_rows), len(family_rows) or 1), 6),
        "low_budget_control_pass_ratio": round(safe_ratio(sum(int(row.get("low_budget_control_pass", 0) or 0) for row in family_rows), len(family_rows) or 1), 6),
        "no_carry_control_pass_ratio": round(safe_ratio(sum(int(row.get("no_carry_control_pass", 0) or 0) for row in family_rows), len(family_rows) or 1), 6),
        "branch_switch_pass_ratio": round(safe_ratio(sum(int(row.get("branch_switch_pass", 0) or 0) for row in family_rows), len(family_rows) or 1), 6),
        "terminal_stop_pass_ratio": round(safe_ratio(sum(int(row.get("terminal_stop_pass", 0) or 0) for row in family_rows), len(family_rows) or 1), 6),
        "all_ok_ratio": round(safe_ratio(sum(int(row.get("all_ok", 0) or 0) for row in family_rows), len(family_rows) or 1), 6),
        "chain_expected_hit_ratio_mean": mean_or_zero([num(row, "expected_hit_ratio") for row in case_rows if str(row.get("branch", "")) == "chain_follow"]),
        "chain_carry_ratio_mean": mean_or_zero([num(row, "next_seed_from_previous_top_ratio") for row in case_rows if str(row.get("branch", "")) == "chain_follow"]),
        "no_carry_ratio_mean": mean_or_zero([num(row, "next_seed_from_previous_top_ratio") for row in case_rows if str(row.get("branch", "")) == "no_carry_control"]),
        "terminal_followup_target_count_mean": mean_or_zero([num(row, "terminal_followup_target_count") for row in case_rows if str(row.get("branch", "")) == "terminal_stop"]),
        "low_budget_target_count_mean": mean_or_zero([num(row, "target_count") for row in step_rows if str(row.get("branch", "")) == "low_budget_control"]),
    }
    wins = int(sum(int(row.get("all_ok", 0) or 0) for row in family_rows))
    losses = int(len(family_rows) - wins)
    summary["all_ok_sign_p"] = sign_test_p_value(wins, losses)
    if (
        len(family_rows) >= 8
        and summary["chain_follow_pass_ratio"] >= 0.999
        and summary["wrong_seed_control_pass_ratio"] >= 0.999
        and summary["low_budget_control_pass_ratio"] >= 0.999
        and summary["no_carry_control_pass_ratio"] >= 0.999
        and summary["branch_switch_pass_ratio"] >= 0.999
        and summary["terminal_stop_pass_ratio"] >= 0.999
        and summary["all_ok_ratio"] >= 0.999
        and summary["all_ok_sign_p"] <= 0.01
    ):
        summary["support_level"] = "strong_evidence"
    else:
        summary["support_level"] = "useful_but_not_strong"
    return summary


def make_charts(*, case_rows: list[dict[str, Any]], step_rows: list[dict[str, Any]], family_rows: list[dict[str, Any]], stamp: str) -> list[Path]:
    plt = e01.setup_matplotlib()
    paths: list[Path] = []

    labels = [BRANCH_LABELS[b] for b in BRANCH_ORDER]
    branch_pass = {
        "chain_follow": mean_or_zero([int(row.get("chain_follow_pass", 0) or 0) for row in family_rows]),
        "wrong_seed_control": mean_or_zero([int(row.get("wrong_seed_control_pass", 0) or 0) for row in family_rows]),
        "low_budget_control": mean_or_zero([int(row.get("low_budget_control_pass", 0) or 0) for row in family_rows]),
        "no_carry_control": mean_or_zero([int(row.get("no_carry_control_pass", 0) or 0) for row in family_rows]),
        "branch_switch": mean_or_zero([int(row.get("branch_switch_pass", 0) or 0) for row in family_rows]),
        "terminal_stop": mean_or_zero([int(row.get("terminal_stop_pass", 0) or 0) for row in family_rows]),
    }
    fig, ax = plt.subplots(figsize=(10.5, 4.5))
    ax.bar(labels, [branch_pass[b] for b in BRANCH_ORDER], color=["#2563eb", "#64748b", "#f59e0b", "#8b5cf6", "#16a34a", "#dc2626"])
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("通过比例")
    ax.set_title("E17 内部候选链的分支判据")
    ax.tick_params(axis="x", rotation=15)
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = CHART_DIR / f"e17_branch_pass_rates_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    chain_steps = [row for row in step_rows if str(row.get("branch", "")) == "chain_follow"]
    step_values = []
    step_labels = []
    for step in (1, 2, 3):
        rows = [row for row in chain_steps if int(row.get("step", 0) or 0) == step]
        step_labels.append(f"step {step}")
        step_values.append(mean_or_zero([num(row, "top_delta_ev") for row in rows]))
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.plot(step_labels, step_values, marker="o", color="#2563eb", linewidth=2.4)
    ax.set_title("E17 连续承接分支的逐拍 top 候选能量")
    ax.set_ylabel("top delta EV 均值")
    ax.grid(alpha=0.22)
    fig.tight_layout()
    path = CHART_DIR / f"e17_chain_step_delta_ev_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    families = [str(row.get("family", "")) for row in family_rows]
    matrix_keys = [
        "chain_follow_pass",
        "wrong_seed_control_pass",
        "low_budget_control_pass",
        "no_carry_control_pass",
        "branch_switch_pass",
        "terminal_stop_pass",
    ]
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    data = [[int(row.get(key, 0) or 0) for key in matrix_keys] for row in family_rows]
    ax.imshow(data, aspect="auto", cmap="Greens", vmin=0, vmax=1)
    ax.set_xticks(range(len(matrix_keys)), [BRANCH_LABELS[b] for b in BRANCH_ORDER], rotation=20)
    ax.set_yticks(range(len(families)), families)
    ax.set_title("E17 family 级强证据判据矩阵")
    for y, row in enumerate(data):
        for x, value in enumerate(row):
            ax.text(x, y, str(value), ha="center", va="center", color="#0f172a", fontsize=8)
    fig.tight_layout()
    path = CHART_DIR / f"e17_family_pass_matrix_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    sample_rows = [row for row in step_rows if str(row.get("family", "")) == "F01" and str(row.get("branch", "")) in {"chain_follow", "no_carry_control", "branch_switch"}]
    sample_labels = [f"{row.get('branch_label')}#{row.get('step')}" for row in sample_rows]
    sample_delta = [num(row, "top_delta_ev") for row in sample_rows]
    fig, ax = plt.subplots(figsize=(10.8, 4.2))
    ax.bar(sample_labels, sample_delta, color="#0f766e")
    ax.set_title("E17 F01 样例：承接、无承接与转向")
    ax.set_ylabel("top delta EV")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = CHART_DIR / f"e17_sample_path_contrast_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)
    return paths


def write_design_note(path: Path) -> None:
    lines = [
        "# E17 内部候选链实验设计",
        "",
        "本实验不把当前原型的能力扩写为完整自然语言生成，而是验证一个更小、可复查的命题：上一拍高能结构候选被作为下一拍种子时，HDB 的感应赋能链路能否沿受控结构链逐拍推进，直到终端记忆目标；当种子错误、能量预算低、上一拍候选没有被承接或权重被调换时，链路是否按设计中断、静默或转向。",
        "",
        "实验使用真实 `HDB.run_induction_propagation` 接口。脚本只模拟状态池/注意力在 tick 间选择上一拍 top 结构作为下一拍 source，不直接改写 HDB 的候选结果。",
        "",
        "六个分支分别约束六个解释：正常链路证明逐拍推进；错误种子证明不是任意输入都激活目标链；低预算证明能量阈值可以剪枝；无承接证明链路推进依赖上一拍 top 候选进入下一拍；权重转向证明候选路径受结构权重调制；终端停止证明到达情景记忆目标后不会继续无限展开。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    *,
    case_rows: list[dict[str, Any]],
    step_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    charts: list[Path],
    whitebox: dict[str, Any],
    stamp: str,
) -> Path:
    lines = [
        f"# E17 内部候选链实验报告 {stamp}",
        "",
        "## 结论摘要",
        "",
        f"- 支持等级：{summary.get('support_level', '')}",
        f"- family 数：{summary.get('family_count', 0)}",
        f"- case 数：{summary.get('case_count', 0)}",
        f"- step 数：{summary.get('step_count', 0)}",
        f"- 整体通过比例：{summary.get('all_ok_ratio', 0.0):.3f}",
        f"- 符号检验 p 值：{summary.get('all_ok_sign_p', 1.0):.8f}",
        f"- 六分支通过比例：{summary.get('chain_follow_pass_ratio', 0.0):.3f} / {summary.get('wrong_seed_control_pass_ratio', 0.0):.3f} / {summary.get('low_budget_control_pass_ratio', 0.0):.3f} / {summary.get('no_carry_control_pass_ratio', 0.0):.3f} / {summary.get('branch_switch_pass_ratio', 0.0):.3f} / {summary.get('terminal_stop_pass_ratio', 0.0):.3f}",
        "",
        "## 正文可使用的最小命题",
        "",
        "在当前 AP 原型中，结构目标可以作为跨 tick 的内部候选链节点被承接：当上一拍 top 结构进入下一拍 source 后，感应赋能会沿已学习结构链逐拍推进；错误种子、低预算、无承接和终端记忆均能形成可复查的边界。这支持“内部续写链/叙事候选链”的工程基础，但不等同于完整自然语言生成能力已经完成。",
        "",
        "## family 判据",
        "",
        "| family | 连续承接 | 错误种子静默 | 低预算静默 | 无承接停滞 | 权重转向 | 终端停止 | all_ok |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in family_rows:
        lines.append(
            f"| {row['family']} | {int(row['chain_follow_pass'])} | {int(row['wrong_seed_control_pass'])} | "
            f"{int(row['low_budget_control_pass'])} | {int(row['no_carry_control_pass'])} | "
            f"{int(row['branch_switch_pass'])} | {int(row['terminal_stop_pass'])} | {int(row['all_ok'])} |"
        )
    lines.extend(["", "## 白箱样例", ""])
    for key, value in whitebox.items():
        lines.append(f"- {key}: `{json.dumps(value, ensure_ascii=False)}`")
    lines.extend(["", "## 图表", ""])
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    report = REPORT_DIR / f"E17_internal_narrative_chain_report_{stamp}.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def run_experiment(*, stamp: str, family_count: int) -> dict[str, Any]:
    ensure_dirs()
    selected = FAMILY_SPECS[: int(family_count)]
    case_rows: list[dict[str, Any]] = []
    step_rows: list[dict[str, Any]] = []
    for spec in selected:
        for branch in BRANCH_ORDER:
            case, steps = run_case(spec, branch)
            case_rows.append(case)
            step_rows.extend(steps)
    family_rows = build_family_rows(case_rows)
    summary = summarize_evidence(case_rows=case_rows, step_rows=step_rows, family_rows=family_rows)
    charts = make_charts(case_rows=case_rows, step_rows=step_rows, family_rows=family_rows, stamp=stamp)
    design_note = REPORT_DIR / "E17_internal_narrative_chain_design_logic.md"
    write_design_note(design_note)
    whitebox = {
        "chain_follow": next((row for row in case_rows if str(row.get("branch", "")) == "chain_follow"), {}),
        "no_carry_control": next((row for row in case_rows if str(row.get("branch", "")) == "no_carry_control"), {}),
        "branch_switch": next((row for row in case_rows if str(row.get("branch", "")) == "branch_switch"), {}),
        "terminal_stop": next((row for row in case_rows if str(row.get("branch", "")) == "terminal_stop"), {}),
    }
    report = write_report(
        case_rows=case_rows,
        step_rows=step_rows,
        family_rows=family_rows,
        summary=summary,
        charts=charts,
        whitebox=whitebox,
        stamp=stamp,
    )
    case_csv = TABLE_DIR / f"e17_internal_narrative_chain_case_rows_{stamp}.csv"
    step_csv = TABLE_DIR / f"e17_internal_narrative_chain_step_rows_{stamp}.csv"
    family_csv = TABLE_DIR / f"e17_internal_narrative_chain_family_rows_{stamp}.csv"
    summary_json = TABLE_DIR / f"e17_internal_narrative_chain_summary_{stamp}.json"
    whitebox_json = TABLE_DIR / f"e17_internal_narrative_chain_whitebox_{stamp}.json"
    e01.write_csv(case_csv, case_rows)
    e01.write_csv(step_csv, step_rows)
    e01.write_csv(family_csv, family_rows)
    e01.write_json(summary_json, summary)
    e01.write_json(whitebox_json, whitebox)
    evidence = {
        "experiment_id": "E17",
        "stamp": stamp,
        "support_level": summary.get("support_level", "not_supported"),
        "summary": summary,
        "artifacts": {
            "case_csv": str(case_csv),
            "step_csv": str(step_csv),
            "family_csv": str(family_csv),
            "summary_json": str(summary_json),
            "whitebox_json": str(whitebox_json),
            "report": str(report),
            "design_note": str(design_note),
            "charts": [str(path) for path in charts],
        },
        "claim_boundary": "证明内部候选链的逐拍承接、可控转向、阈值剪枝和终端停止，不证明完整自然语言生成能力已经完成。",
    }
    e01.write_json(MANIFEST_DIR / f"E17_internal_narrative_chain_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E17_internal_narrative_chain_latest.json", evidence)
    return evidence


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper E17 internal narrative candidate-chain experiment.")
    parser.add_argument("--stamp", default=STAMP_DEFAULT)
    parser.add_argument("--family-count", type=int, default=12)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    evidence = run_experiment(stamp=str(args.stamp), family_count=int(args.family_count))
    print(json.dumps(evidence["summary"], ensure_ascii=False, indent=2))
    return 0 if evidence.get("support_level") == "strong_evidence" else 2


if __name__ == "__main__":
    raise SystemExit(main())
