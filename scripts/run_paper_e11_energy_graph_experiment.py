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
from hdb import HDB


E11_ROOT = ARTIFACT_ROOT / "E11_energy_graph"
TABLE_DIR = E11_ROOT / "tables"
CHART_DIR = E11_ROOT / "charts"
REPORT_DIR = E11_ROOT / "reports"
MANIFEST_DIR = E11_ROOT / "manifests"

STAMP_DEFAULT = "e11_final_v1"


@dataclass(frozen=True)
class FamilySpec:
    family: str
    source_er: float
    source_ev: float
    root_b_weight: float
    root_c_weight: float
    root_memory_weight: float
    b_d_weight: float
    b_memory_weight: float
    c_f_weight: float
    c_memory_weight: float


FAMILY_SPECS: list[FamilySpec] = [
    FamilySpec("F01", 0.30, 1.00, 0.52, 0.28, 0.20, 0.64, 0.36, 0.58, 0.42),
    FamilySpec("F02", 0.31, 1.00, 0.51, 0.29, 0.20, 0.63, 0.37, 0.59, 0.41),
    FamilySpec("F03", 0.32, 1.00, 0.50, 0.30, 0.20, 0.62, 0.38, 0.60, 0.40),
    FamilySpec("F04", 0.33, 1.00, 0.53, 0.27, 0.20, 0.65, 0.35, 0.57, 0.43),
    FamilySpec("F05", 0.34, 1.00, 0.54, 0.26, 0.20, 0.66, 0.34, 0.56, 0.44),
    FamilySpec("F06", 0.35, 1.00, 0.49, 0.31, 0.20, 0.61, 0.39, 0.61, 0.39),
    FamilySpec("F07", 0.36, 1.00, 0.48, 0.32, 0.20, 0.60, 0.40, 0.62, 0.38),
    FamilySpec("F08", 0.37, 1.00, 0.55, 0.25, 0.20, 0.67, 0.33, 0.55, 0.45),
    FamilySpec("F09", 0.30, 1.02, 0.52, 0.30, 0.18, 0.64, 0.36, 0.58, 0.42),
    FamilySpec("F10", 0.32, 1.02, 0.50, 0.32, 0.18, 0.62, 0.38, 0.60, 0.40),
    FamilySpec("F11", 0.34, 1.02, 0.54, 0.28, 0.18, 0.66, 0.34, 0.56, 0.44),
    FamilySpec("F12", 0.36, 1.02, 0.48, 0.34, 0.18, 0.60, 0.40, 0.62, 0.38),
]

BRANCH_ORDER = (
    "deep_multilayer",
    "single_round_cap",
    "high_frontier_threshold",
    "high_budget_threshold",
    "width_cap_one",
    "no_er_reinduction",
)

BRANCH_LABELS = {
    "deep_multilayer": "多轮扩散",
    "single_round_cap": "单轮截断",
    "high_frontier_threshold": "前沿阈值剪枝",
    "high_budget_threshold": "预算阈值剪枝",
    "width_cap_one": "宽度上限",
    "no_er_reinduction": "关闭根源ER重诱发",
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


def make_packet(text: str, *, prefix: str) -> dict[str, Any]:
    sa_items = []
    for idx, ch in enumerate(text):
        sa_id = f"sa_{prefix}_{text}_{idx}"
        sa_items.append(
            {
                "id": sa_id,
                "object_type": "sa",
                "content": {"raw": ch, "display": ch, "normalized": ch},
                "stimulus": {"role": "feature", "modality": "text"},
                "energy": {"er": 1.0, "ev": 0.0},
                "ext": {"packet_context": {"sequence_index": idx}},
            }
        )
    return {
        "id": f"spkt_{prefix}_{text}",
        "object_type": "stimulus_packet",
        "sa_items": sa_items,
        "csa_items": [],
        "grouped_sa_sequences": [
            {
                "group_index": 0,
                "source_type": "current",
                "origin_frame_id": f"frame_{prefix}_{text}",
                "sa_ids": [item["id"] for item in sa_items],
                "csa_ids": [],
            }
        ],
        "energy_summary": {"current_total_er": float(len(sa_items)), "current_total_ev": 0.0},
        "source": {"parent_ids": []},
    }


def store_packet_as_structure(hdb: HDB, text: str, *, prefix: str, trace_id: str) -> dict[str, Any]:
    packet = make_packet(text, prefix=prefix)
    profile = hdb._cut.build_sequence_profile_from_stimulus_packet(packet)
    payload = hdb._cut.make_structure_payload_from_profile(
        profile,
        confidence=0.9,
        ext={"kind": "paper_e11_seed", "relation_type": "paper_e11_seed"},
    )
    structure_obj, _created = hdb._structure_store.create_structure(
        structure_payload=payload,
        trace_id=trace_id,
        tick_id=trace_id,
        origin="paper_e11_seed",
        origin_id=packet.get("id", trace_id),
        parent_ids=[],
    )
    hdb._pointer_index.register_structure(structure_obj)
    return structure_obj


def append_memory(hdb: HDB, *, label: str, structure_id: str, trace_id: str) -> str:
    result = hdb.append_episodic_memory(
        episodic_payload={
            "event_summary": label,
            "structure_refs": [structure_id],
            "group_refs": [],
            "meta": {"ext": {"display_text": label}},
        },
        trace_id=trace_id,
    )
    if not result.get("success", False):
        raise RuntimeError(f"append_episodic_memory failed: {result}")
    return str((result.get("data") or {}).get("episodic_id", "") or "")


def add_edge(
    hdb: HDB,
    *,
    owner: dict[str, Any],
    target: dict[str, Any],
    weight: float,
    residual: str,
    memory_id: str = "",
) -> None:
    ext = {
        "relation_type": "incoming_extension",
        "canonical_display_text": str(target.get("structure", {}).get("display_text", "") or target.get("id", "")),
    }
    if memory_id:
        ext["anchor_memory_id"] = memory_id
    entry = hdb._structure_store.add_diff_entry(
        owner["id"],
        target_id=target["id"],
        content_signature=str(target.get("structure", {}).get("content_signature", "")),
        base_weight=float(weight),
        residual_existing_signature="",
        residual_incoming_signature=str(residual),
        ext=ext,
    )
    if not entry:
        raise RuntimeError(f"add_diff_entry failed for {owner.get('id')} -> {target.get('id')}")


def branch_config(branch: str) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "induction_energy_graph_v2_enabled": True,
        "induction_energy_graph_v2_max_rounds": 4,
        "induction_energy_graph_v2_root_er_decay_ratio": 0.82,
        "induction_energy_graph_v2_root_source_ev_ratio": 1.0,
        "induction_energy_graph_v2_frontier_ev_ratio": 1.0,
        "induction_energy_graph_v2_er_round_ratio": 1.0,
        "induction_energy_graph_v2_min_frontier_ev": 0.05,
        "induction_energy_graph_v2_min_budget": 0.03,
        "induction_energy_graph_v2_max_frontier_nodes_per_source": 0,
        "induction_energy_graph_v2_target_top_k": 0,
        "ev_propagation_threshold": 0.05,
        "er_induction_threshold": 0.05,
        "induction_min_entry_base_weight": 0.0,
        "owner_db_runtime_budget_enabled": False,
    }
    if branch == "single_round_cap":
        cfg["induction_energy_graph_v2_max_rounds"] = 1
    elif branch == "high_frontier_threshold":
        cfg["induction_energy_graph_v2_min_frontier_ev"] = 0.80
        cfg["ev_propagation_threshold"] = 0.80
    elif branch == "high_budget_threshold":
        cfg["induction_energy_graph_v2_min_budget"] = 0.60
    elif branch == "width_cap_one":
        cfg["induction_energy_graph_v2_max_frontier_nodes_per_source"] = 1
    elif branch == "no_er_reinduction":
        pass
    elif branch == "deep_multilayer":
        pass
    else:
        raise ValueError(f"unknown branch: {branch}")
    return cfg


def source_energies(spec: FamilySpec, branch: str) -> tuple[float, float, bool]:
    if branch in {"high_budget_threshold", "no_er_reinduction"}:
        return 0.0, float(spec.source_ev), False
    return float(spec.source_er), float(spec.source_ev), True


def build_controlled_graph(hdb: HDB, *, spec: FamilySpec, branch: str) -> dict[str, Any]:
    prefix = f"{spec.family}_{branch}"
    structures = {
        "A": store_packet_as_structure(hdb, "A", prefix=prefix, trace_id=f"{prefix}_seed_A"),
        "AB": store_packet_as_structure(hdb, "AB", prefix=prefix, trace_id=f"{prefix}_seed_AB"),
        "AC": store_packet_as_structure(hdb, "AC", prefix=prefix, trace_id=f"{prefix}_seed_AC"),
        "AM": store_packet_as_structure(hdb, "AM", prefix=prefix, trace_id=f"{prefix}_seed_AM"),
        "ABD": store_packet_as_structure(hdb, "ABD", prefix=prefix, trace_id=f"{prefix}_seed_ABD"),
        "ABE": store_packet_as_structure(hdb, "ABE", prefix=prefix, trace_id=f"{prefix}_seed_ABE"),
        "ACF": store_packet_as_structure(hdb, "ACF", prefix=prefix, trace_id=f"{prefix}_seed_ACF"),
        "ACG": store_packet_as_structure(hdb, "ACG", prefix=prefix, trace_id=f"{prefix}_seed_ACG"),
    }
    memory_root = append_memory(hdb, label=f"{spec.family} root terminal memory", structure_id=structures["AM"]["id"], trace_id=f"{prefix}_mem_root")
    memory_b = append_memory(hdb, label=f"{spec.family} B terminal memory", structure_id=structures["ABE"]["id"], trace_id=f"{prefix}_mem_b")
    memory_c = append_memory(hdb, label=f"{spec.family} C terminal memory", structure_id=structures["ACG"]["id"], trace_id=f"{prefix}_mem_c")

    add_edge(hdb, owner=structures["A"], target=structures["AB"], weight=spec.root_b_weight, residual="B")
    add_edge(hdb, owner=structures["A"], target=structures["AC"], weight=spec.root_c_weight, residual="C")
    add_edge(hdb, owner=structures["A"], target=structures["AM"], weight=spec.root_memory_weight, residual="M", memory_id=memory_root)
    add_edge(hdb, owner=structures["AB"], target=structures["ABD"], weight=spec.b_d_weight, residual="D")
    add_edge(hdb, owner=structures["AB"], target=structures["ABE"], weight=spec.b_memory_weight, residual="E", memory_id=memory_b)
    add_edge(hdb, owner=structures["AC"], target=structures["ACF"], weight=spec.c_f_weight, residual="F")
    add_edge(hdb, owner=structures["AC"], target=structures["ACG"], weight=spec.c_memory_weight, residual="G", memory_id=memory_c)
    return {
        "structures": structures,
        "memory_root": memory_root,
        "memory_b": memory_b,
        "memory_c": memory_c,
    }


def max_round_value(rounds: list[dict[str, Any]], key: str) -> float:
    return max([float(row.get(key, 0.0) or 0.0) for row in rounds], default=0.0)


def run_case(spec: FamilySpec, branch: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    tmp_dir = tempfile.mkdtemp(prefix=f"paper_e11_{spec.family}_{branch}_")
    cfg = {
        "data_dir": tmp_dir,
        "enable_background_repair": False,
        **branch_config(branch),
    }
    hdb = HDB(config_override=cfg)
    try:
        graph = build_controlled_graph(hdb, spec=spec, branch=branch)
        source_er, source_ev, enable_er = source_energies(spec, branch)
        source = graph["structures"]["A"]
        result = hdb.run_induction_propagation(
            state_snapshot={
                "summary": {"active_item_count": 1},
                "top_items": [
                    {
                        "id": f"runtime_{spec.family}_{branch}_source",
                        "ref_object_type": "st",
                        "ref_object_id": source["id"],
                        "display": "A",
                        "display_text": "A",
                        "er": float(source_er),
                        "ev": float(source_ev),
                    }
                ],
            },
            trace_id=f"paper_e11_{spec.family}_{branch}",
            max_source_items=1,
            enable_ev_propagation=True,
            enable_er_induction=bool(enable_er),
        )
        if not result.get("success", False):
            raise RuntimeError(f"run_induction_propagation failed: {result}")
        data = result.get("data", {}) or {}
        targets = list(data.get("induction_targets", []) or [])
        rounds = list(data.get("energy_graph_round_summaries", []) or [])
        structure_targets = [row for row in targets if str(row.get("projection_kind", "")) == "structure"]
        memory_targets = [row for row in targets if str(row.get("projection_kind", "")) == "memory"]
        depth2_structure_targets = [row for row in structure_targets if int(row.get("energy_graph_depth_max", 0) or 0) >= 2]
        layer1_memory_targets = [row for row in memory_targets if int(row.get("energy_graph_depth_min", 0) or 0) == 1]
        deeper_memory_targets = [row for row in memory_targets if int(row.get("energy_graph_depth_max", 0) or 0) >= 2]

        case_row = {
            "family": spec.family,
            "branch": branch,
            "branch_label": BRANCH_LABELS.get(branch, branch),
            "source_er": round(float(source_er), 8),
            "source_ev": round(float(source_ev), 8),
            "enable_er_induction": int(bool(enable_er)),
            "root_b_weight": round(float(spec.root_b_weight), 8),
            "root_c_weight": round(float(spec.root_c_weight), 8),
            "root_memory_weight": round(float(spec.root_memory_weight), 8),
            "b_d_weight": round(float(spec.b_d_weight), 8),
            "b_memory_weight": round(float(spec.b_memory_weight), 8),
            "c_f_weight": round(float(spec.c_f_weight), 8),
            "c_memory_weight": round(float(spec.c_memory_weight), 8),
            "energy_graph_v2_enabled": int(bool(data.get("energy_graph_v2_enabled", False))),
            "config_max_rounds": int(data.get("energy_graph_config_max_rounds", 0) or 0),
            "round_count": int(data.get("energy_graph_round_count_max", 0) or 0),
            "depth_max": int(data.get("energy_graph_depth_max", 0) or 0),
            "frontier_generated_count": int(data.get("energy_graph_frontier_generated_count", 0) or 0),
            "frontier_pruned_count": int(data.get("energy_graph_frontier_pruned_count", 0) or 0),
            "terminal_memory_count": int(data.get("energy_graph_terminal_memory_count", 0) or 0),
            "root_reinduction_count": int(data.get("energy_graph_root_reinduction_count", 0) or 0),
            "layer_count": len([key for key, value in (data.get("energy_graph_layer_histogram", {}) or {}).items() if int(value or 0) > 0]),
            "layer_histogram_json": json.dumps(data.get("energy_graph_layer_histogram", {}) or {}, ensure_ascii=False, sort_keys=True),
            "frontier_out_count_max": int(max_round_value(rounds, "frontier_out_count")),
            "frontier_in_count_max": int(max_round_value(rounds, "frontier_in_count")),
            "frontier_budget_ev_total": round(sum(float(row.get("frontier_budget_ev", 0.0) or 0.0) for row in rounds), 8),
            "root_induction_budget_ev_total": round(sum(float(row.get("root_induction_budget_ev", 0.0) or 0.0) for row in rounds), 8),
            "round_delta_ev_total": round(sum(float(row.get("round_delta_ev", 0.0) or 0.0) for row in rounds), 8),
            "round_delta_ev_last": round(float(rounds[-1].get("round_delta_ev", 0.0) or 0.0), 8) if rounds else 0.0,
            "total_delta_ev": round(float(data.get("total_delta_ev", 0.0) or 0.0), 8),
            "total_ev_consumed": round(float(data.get("total_ev_consumed", 0.0) or 0.0), 8),
            "propagated_budget_total_ev": round(float(data.get("propagated_budget_total_ev", 0.0) or 0.0), 8),
            "structure_target_count": len(structure_targets),
            "memory_target_count": len(memory_targets),
            "depth2_structure_target_count": len(depth2_structure_targets),
            "layer1_memory_target_count": len(layer1_memory_targets),
            "deeper_memory_target_count": len(deeper_memory_targets),
            "has_AB_structure": int(any(row.get("target_structure_id") == graph["structures"]["AB"]["id"] for row in structure_targets)),
            "has_AC_structure": int(any(row.get("target_structure_id") == graph["structures"]["AC"]["id"] for row in structure_targets)),
            "has_ABD_structure_depth2": int(any(row.get("target_structure_id") == graph["structures"]["ABD"]["id"] and int(row.get("energy_graph_depth_max", 0) or 0) >= 2 for row in structure_targets)),
            "has_ACF_structure_depth2": int(any(row.get("target_structure_id") == graph["structures"]["ACF"]["id"] and int(row.get("energy_graph_depth_max", 0) or 0) >= 2 for row in structure_targets)),
            "has_root_terminal_memory": int(any(row.get("memory_id") == graph["memory_root"] for row in memory_targets)),
            "has_b_terminal_memory": int(any(row.get("memory_id") == graph["memory_b"] for row in memory_targets)),
            "has_c_terminal_memory": int(any(row.get("memory_id") == graph["memory_c"] for row in memory_targets)),
            "target_ids_json": json.dumps(
                [
                    {
                        "projection_kind": row.get("projection_kind", ""),
                        "memory_id": row.get("memory_id", ""),
                        "target_structure_id": row.get("target_structure_id", ""),
                        "depth_min": row.get("energy_graph_depth_min", 0),
                        "depth_max": row.get("energy_graph_depth_max", 0),
                        "delta_ev": row.get("delta_ev", 0.0),
                    }
                    for row in targets
                ],
                ensure_ascii=False,
            ),
        }
        target_rows = []
        for index, row in enumerate(targets):
            target_rows.append(
                {
                    "family": spec.family,
                    "branch": branch,
                    "target_index": index,
                    "projection_kind": row.get("projection_kind", ""),
                    "memory_id": row.get("memory_id", ""),
                    "target_structure_id": row.get("target_structure_id", ""),
                    "target_display_text": row.get("target_display_text", ""),
                    "delta_ev": round(float(row.get("delta_ev", 0.0) or 0.0), 8),
                    "runtime_weight": round(float(row.get("runtime_weight", 0.0) or 0.0), 8),
                    "modes": "|".join(str(x) for x in (row.get("modes", []) or [])),
                    "energy_graph_round_first": int(row.get("energy_graph_round_first", 0) or 0),
                    "energy_graph_round_last": int(row.get("energy_graph_round_last", 0) or 0),
                    "energy_graph_depth_min": int(row.get("energy_graph_depth_min", 0) or 0),
                    "energy_graph_depth_max": int(row.get("energy_graph_depth_max", 0) or 0),
                    "energy_graph_emit_count": int(row.get("energy_graph_emit_count", 0) or 0),
                    "frontier_source_kinds": "|".join(str(x) for x in (row.get("frontier_source_kinds", []) or [])),
                }
            )
        round_rows = []
        for round_row in rounds:
            round_rows.append(
                {
                    "family": spec.family,
                    "branch": branch,
                    "round_index": int(round_row.get("round_index", 0) or 0),
                    "frontier_in_count": int(round_row.get("frontier_in_count", 0) or 0),
                    "frontier_out_count": int(round_row.get("frontier_out_count", 0) or 0),
                    "frontier_pruned_count": int(round_row.get("frontier_pruned_count", 0) or 0),
                    "frontier_memory_terminal_count": int(round_row.get("frontier_memory_terminal_count", 0) or 0),
                    "root_reinduction_count": int(round_row.get("root_reinduction_count", 0) or 0),
                    "frontier_budget_ev": round(float(round_row.get("frontier_budget_ev", 0.0) or 0.0), 8),
                    "root_induction_budget_ev": round(float(round_row.get("root_induction_budget_ev", 0.0) or 0.0), 8),
                    "round_delta_ev": round(float(round_row.get("round_delta_ev", 0.0) or 0.0), 8),
                }
            )
        return case_row, target_rows, round_rows
    finally:
        hdb.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def build_pair_rows(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_family: dict[str, dict[str, dict[str, Any]]] = {}
    for row in case_rows:
        by_family.setdefault(str(row["family"]), {})[str(row["branch"])] = row

    pair_rows: list[dict[str, Any]] = []
    for family in sorted(by_family):
        mapping = by_family[family]
        deep = mapping.get("deep_multilayer", {})
        single = mapping.get("single_round_cap", {})
        high_frontier = mapping.get("high_frontier_threshold", {})
        high_budget = mapping.get("high_budget_threshold", {})
        width_cap = mapping.get("width_cap_one", {})
        no_er = mapping.get("no_er_reinduction", {})
        row = {
            "family": family,
            "deep_multilayer_pass": int(
                int(deep.get("energy_graph_v2_enabled", 0) or 0) == 1
                and int(deep.get("depth_max", 0) or 0) >= 2
                and int(deep.get("round_count", 0) or 0) >= 3
                and int(deep.get("depth2_structure_target_count", 0) or 0) >= 2
                and int(deep.get("terminal_memory_count", 0) or 0) >= 1
                and int(deep.get("root_reinduction_count", 0) or 0) >= 1
                and float(deep.get("propagated_budget_total_ev", 0.0) or 0.0) > float(deep.get("total_ev_consumed", 0.0) or 0.0)
            ),
            "single_round_cap_pass": int(
                int(single.get("round_count", 0) or 0) == 1
                and int(single.get("depth_max", 0) or 0) == 1
                and int(single.get("root_reinduction_count", 0) or 0) == 0
                and int(single.get("depth2_structure_target_count", 0) or 0) == 0
            ),
            "high_frontier_threshold_pass": int(
                int(high_frontier.get("depth_max", 0) or 0) == 1
                and int(high_frontier.get("frontier_pruned_count", 0) or 0) >= 1
                and int(high_frontier.get("depth2_structure_target_count", 0) or 0) == 0
            ),
            "high_budget_threshold_pass": int(
                int(high_budget.get("depth_max", 0) or 0) == 1
                and int(high_budget.get("frontier_pruned_count", 0) or 0) >= 1
                and int(high_budget.get("root_reinduction_count", 0) or 0) == 0
                and int(high_budget.get("depth2_structure_target_count", 0) or 0) == 0
            ),
            "width_cap_pass": int(
                int(width_cap.get("frontier_out_count_max", 0) or 0) <= 1
                and int(width_cap.get("frontier_pruned_count", 0) or 0) >= 1
                and int(width_cap.get("depth_max", 0) or 0) >= 2
            ),
            "no_er_reinduction_pass": int(
                int(no_er.get("root_reinduction_count", 0) or 0) == 0
                and int(deep.get("root_reinduction_count", 0) or 0) > int(no_er.get("root_reinduction_count", 0) or 0)
                and float(deep.get("total_delta_ev", 0.0) or 0.0) > float(no_er.get("total_delta_ev", 0.0) or 0.0)
            ),
            "deep_depth_max": int(deep.get("depth_max", 0) or 0),
            "single_depth_max": int(single.get("depth_max", 0) or 0),
            "high_frontier_depth_max": int(high_frontier.get("depth_max", 0) or 0),
            "high_budget_depth_max": int(high_budget.get("depth_max", 0) or 0),
            "width_cap_frontier_out_max": int(width_cap.get("frontier_out_count_max", 0) or 0),
            "deep_terminal_memory_count": int(deep.get("terminal_memory_count", 0) or 0),
            "deep_root_reinduction_count": int(deep.get("root_reinduction_count", 0) or 0),
            "no_er_root_reinduction_count": int(no_er.get("root_reinduction_count", 0) or 0),
            "deep_total_delta_ev": round(float(deep.get("total_delta_ev", 0.0) or 0.0), 8),
            "no_er_total_delta_ev": round(float(no_er.get("total_delta_ev", 0.0) or 0.0), 8),
        }
        row["all_ok"] = int(
            int(row["deep_multilayer_pass"]) == 1
            and int(row["single_round_cap_pass"]) == 1
            and int(row["high_frontier_threshold_pass"]) == 1
            and int(row["high_budget_threshold_pass"]) == 1
            and int(row["width_cap_pass"]) == 1
            and int(row["no_er_reinduction_pass"]) == 1
        )
        pair_rows.append(row)
    return pair_rows


def summarize_evidence(*, case_rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]]) -> dict[str, Any]:
    def branch_rows(branch: str) -> list[dict[str, Any]]:
        return [row for row in case_rows if str(row.get("branch", "")) == branch]

    deep_rows = branch_rows("deep_multilayer")
    single_rows = branch_rows("single_round_cap")
    high_frontier_rows = branch_rows("high_frontier_threshold")
    high_budget_rows = branch_rows("high_budget_threshold")
    width_rows = branch_rows("width_cap_one")
    no_er_rows = branch_rows("no_er_reinduction")

    summary: dict[str, Any] = {
        "case_count": int(len(case_rows)),
        "family_count": int(len(pair_rows)),
        "deep_multilayer_pass_ratio": round(safe_ratio(sum(int(row.get("deep_multilayer_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "single_round_cap_pass_ratio": round(safe_ratio(sum(int(row.get("single_round_cap_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "high_frontier_threshold_pass_ratio": round(safe_ratio(sum(int(row.get("high_frontier_threshold_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "high_budget_threshold_pass_ratio": round(safe_ratio(sum(int(row.get("high_budget_threshold_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "width_cap_pass_ratio": round(safe_ratio(sum(int(row.get("width_cap_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "no_er_reinduction_pass_ratio": round(safe_ratio(sum(int(row.get("no_er_reinduction_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "all_ok_ratio": round(safe_ratio(sum(int(row.get("all_ok", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "deep_depth_mean": mean_or_zero([num(row, "depth_max") for row in deep_rows]),
        "deep_round_count_mean": mean_or_zero([num(row, "round_count") for row in deep_rows]),
        "deep_terminal_memory_mean": mean_or_zero([num(row, "terminal_memory_count") for row in deep_rows]),
        "deep_root_reinduction_mean": mean_or_zero([num(row, "root_reinduction_count") for row in deep_rows]),
        "deep_total_delta_ev_mean": mean_or_zero([num(row, "total_delta_ev") for row in deep_rows]),
        "single_depth_mean": mean_or_zero([num(row, "depth_max") for row in single_rows]),
        "high_frontier_pruned_mean": mean_or_zero([num(row, "frontier_pruned_count") for row in high_frontier_rows]),
        "high_budget_pruned_mean": mean_or_zero([num(row, "frontier_pruned_count") for row in high_budget_rows]),
        "width_frontier_out_max_mean": mean_or_zero([num(row, "frontier_out_count_max") for row in width_rows]),
        "width_pruned_mean": mean_or_zero([num(row, "frontier_pruned_count") for row in width_rows]),
        "no_er_total_delta_ev_mean": mean_or_zero([num(row, "total_delta_ev") for row in no_er_rows]),
        "deep_vs_no_er_delta_ev_gain_mean": mean_or_zero(
            [
                num(mapping.get("deep_multilayer", {}), "total_delta_ev") - num(mapping.get("no_er_reinduction", {}), "total_delta_ev")
                for mapping in [
                    {str(row.get("branch", "")): row for row in case_rows if str(row.get("family", "")) == family}
                    for family in sorted({str(row.get("family", "")) for row in case_rows})
                ]
            ]
        ),
    }
    wins = int(sum(int(row.get("all_ok", 0) or 0) for row in pair_rows))
    losses = int(len(pair_rows) - wins)
    summary["all_ok_sign_p"] = sign_test_p_value(wins, losses)

    support_level = "not_supported"
    if (
        len(pair_rows) >= 8
        and summary["deep_multilayer_pass_ratio"] >= 0.999
        and summary["single_round_cap_pass_ratio"] >= 0.999
        and summary["high_frontier_threshold_pass_ratio"] >= 0.999
        and summary["high_budget_threshold_pass_ratio"] >= 0.999
        and summary["width_cap_pass_ratio"] >= 0.999
        and summary["no_er_reinduction_pass_ratio"] >= 0.999
        and summary["all_ok_ratio"] >= 0.999
        and summary["all_ok_sign_p"] <= 0.01
    ):
        support_level = "strong_evidence"
    elif (
        len(pair_rows) >= 4
        and summary["deep_multilayer_pass_ratio"] >= 0.80
        and summary["single_round_cap_pass_ratio"] >= 0.80
        and summary["high_frontier_threshold_pass_ratio"] >= 0.80
    ):
        support_level = "useful_but_not_strong"
    summary["support_level"] = support_level
    return summary


def make_charts(
    *,
    case_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    round_rows: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
    stamp: str,
) -> list[Path]:
    plt = e01.setup_matplotlib()
    paths: list[Path] = []

    branch_labels = [BRANCH_LABELS[branch] for branch in BRANCH_ORDER]
    depth_means = [mean_or_zero([num(row, "depth_max") for row in case_rows if str(row.get("branch", "")) == branch]) for branch in BRANCH_ORDER]
    pruned_means = [mean_or_zero([num(row, "frontier_pruned_count") for row in case_rows if str(row.get("branch", "")) == branch]) for branch in BRANCH_ORDER]
    terminal_means = [mean_or_zero([num(row, "terminal_memory_count") for row in case_rows if str(row.get("branch", "")) == branch]) for branch in BRANCH_ORDER]
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.4))
    xs = list(range(len(BRANCH_ORDER)))
    axes[0].bar(xs, depth_means, color="#2563eb", alpha=0.88)
    axes[0].set_xticks(xs, branch_labels, rotation=20, ha="right")
    axes[0].set_title("最大扩散深度")
    axes[0].grid(axis="y", alpha=0.22)
    axes[1].bar(xs, pruned_means, color="#dc2626", alpha=0.88)
    axes[1].set_xticks(xs, branch_labels, rotation=20, ha="right")
    axes[1].set_title("前沿剪枝次数")
    axes[1].grid(axis="y", alpha=0.22)
    axes[2].bar(xs, terminal_means, color="#16a34a", alpha=0.88)
    axes[2].set_xticks(xs, branch_labels, rotation=20, ha="right")
    axes[2].set_title("终止记忆计数")
    axes[2].grid(axis="y", alpha=0.22)
    fig.suptitle("E11 分层能量图的边界控制")
    fig.tight_layout()
    path = CHART_DIR / f"e11_energy_graph_branch_controls_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    deep_rounds = [row for row in round_rows if str(row.get("branch", "")) == "deep_multilayer"]
    round_indices = sorted({int(row.get("round_index", 0) or 0) for row in deep_rounds})
    frontier_budget = [mean_or_zero([num(row, "frontier_budget_ev") for row in deep_rounds if int(row.get("round_index", 0) or 0) == idx]) for idx in round_indices]
    root_budget = [mean_or_zero([num(row, "root_induction_budget_ev") for row in deep_rounds if int(row.get("round_index", 0) or 0) == idx]) for idx in round_indices]
    delta_ev = [mean_or_zero([num(row, "round_delta_ev") for row in deep_rounds if int(row.get("round_index", 0) or 0) == idx]) for idx in round_indices]
    fig, ax = plt.subplots(figsize=(10.2, 4.6))
    ax.plot(round_indices, frontier_budget, marker="o", linewidth=2.2, label="前沿传播预算")
    ax.plot(round_indices, root_budget, marker="o", linewidth=2.2, label="根源ER诱发预算")
    ax.plot(round_indices, delta_ev, marker="o", linewidth=2.2, label="本轮新增EV")
    ax.set_xticks(round_indices)
    ax.set_xlabel("round")
    ax.set_ylabel("EV")
    ax.set_title("E11 多轮扩散中的预算与新增能量")
    ax.grid(True, alpha=0.22)
    ax.legend(frameon=False)
    fig.tight_layout()
    path = CHART_DIR / f"e11_energy_graph_round_budget_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    deep_targets = [row for row in target_rows if str(row.get("branch", "")) == "deep_multilayer"]
    depth_values = sorted({int(row.get("energy_graph_depth_max", 0) or 0) for row in deep_targets if int(row.get("energy_graph_depth_max", 0) or 0) > 0})
    structure_delta = [
        mean_or_zero(
            [
                num(row, "delta_ev")
                for row in deep_targets
                if int(row.get("energy_graph_depth_max", 0) or 0) == depth and str(row.get("projection_kind", "")) == "structure"
            ]
        )
        for depth in depth_values
    ]
    memory_delta = [
        mean_or_zero(
            [
                num(row, "delta_ev")
                for row in deep_targets
                if int(row.get("energy_graph_depth_max", 0) or 0) == depth and str(row.get("projection_kind", "")) == "memory"
            ]
        )
        for depth in depth_values
    ]
    fig, ax = plt.subplots(figsize=(8.8, 4.4))
    width = 0.34
    xs = list(range(len(depth_values)))
    ax.bar([x - width / 2 for x in xs], structure_delta, width=width, color="#2563eb", label="结构目标")
    ax.bar([x + width / 2 for x in xs], memory_delta, width=width, color="#16a34a", label="记忆目标")
    ax.set_xticks(xs, [f"depth {depth}" for depth in depth_values])
    ax.set_ylabel("平均 delta EV")
    ax.set_title("E11 多轮扩散中的结构目标与终止记忆目标")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False)
    fig.tight_layout()
    path = CHART_DIR / f"e11_energy_graph_target_depth_kind_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    family_labels = [str(row.get("family", "")) for row in pair_rows]
    family_ok = [int(row.get("all_ok", 0) or 0) for row in pair_rows]
    fig, ax = plt.subplots(figsize=(9.4, 4.2))
    ax.bar(family_labels, family_ok, color=["#16a34a" if v else "#dc2626" for v in family_ok])
    ax.set_ylim(0.0, 1.1)
    ax.set_ylabel("all_ok")
    ax.set_title("E11 family 级有限扩散证据链是否全部通过")
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = CHART_DIR / f"e11_energy_graph_family_pass_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)
    return paths


def write_design_note(path: Path) -> None:
    lines = [
        "# E11 设计逻辑",
        "",
        "本实验把“分形式认知图景”收窄为当前原型可白箱验证的最小命题：分层能量图可以从一个源结构出发，沿局部结构数据库向下一层结构与记忆目标扩散；这种扩散不是无界增长，而是被轮数、前沿能量阈值、最小预算、前沿宽度上限和记忆终止叶节点共同约束。",
        "",
        "实验构造同一族受控结构图：A 指向两个结构目标 AB/AC 与一个记忆目标 AM；AB 和 AC 又分别指向一个结构目标与一个记忆目标。结构目标会进入下一轮前沿，记忆目标只计为终止叶节点，不继续展开。",
        "",
        "六个分支只改变一个边界条件：多轮扩散、单轮截断、提高前沿阈值、提高预算阈值、前沿宽度上限、关闭根源 ER 重诱发。若 AP 的分层能量图口径成立，多轮分支应出现 depth>=2；单轮与两类阈值分支应停止在 depth=1；宽度分支应把 frontier_out 限制在 1；关闭根源 ER 后，root_reinduction 应为 0 且总 delta EV 低于多轮分支。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    *,
    case_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    round_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    charts: list[Path],
    whitebox: dict[str, Any],
    stamp: str,
) -> Path:
    lines: list[str] = []
    lines.append(f"# E11 有限分形能量扩散报告（{stamp}）")
    lines.append("")
    lines.append("## 核心结论")
    lines.append("")
    lines.append(f"- 支持等级：**{summary.get('support_level', 'unknown')}**")
    lines.append(f"- family 数：{int(summary.get('family_count', 0))}")
    lines.append(f"- case 数：{int(summary.get('case_count', 0))}")
    lines.append(f"- 整体通过比例：{summary.get('all_ok_ratio', 0.0):.3f}")
    lines.append(f"- 符号检验 p 值：{summary.get('all_ok_sign_p', 1.0):.8f}")
    lines.append(f"- 多轮扩散 / 单轮截断 / 前沿阈值 / 预算阈值 / 宽度上限 / 无 ER 重诱发通过比例：{summary.get('deep_multilayer_pass_ratio', 0.0):.3f} / {summary.get('single_round_cap_pass_ratio', 0.0):.3f} / {summary.get('high_frontier_threshold_pass_ratio', 0.0):.3f} / {summary.get('high_budget_threshold_pass_ratio', 0.0):.3f} / {summary.get('width_cap_pass_ratio', 0.0):.3f} / {summary.get('no_er_reinduction_pass_ratio', 0.0):.3f}")
    lines.append("")
    lines.append("## 正文可使用的最小命题")
    lines.append("")
    lines.append(
        "在当前 AP 原型中，分层能量图可以从一个被激活的源结构出发，沿结构局部数据库向结构目标与记忆目标分配虚能量；"
        "结构目标可以作为下一轮前沿继续展开，记忆目标作为终止叶节点停止扩散。"
        "扩散深度和宽度不是无限增长，而会被最大轮数、前沿能量阈值、最小预算和前沿节点上限约束。"
    )
    lines.append("")
    lines.append("## 强证据边界")
    lines.append("")
    lines.append("- 本实验不宣称 AP 已经产生完整的人类联想、想象或叙事意识。")
    lines.append("- 本实验只证明当前原型中的分层能量图具备可控的多层展开、终止和剪枝边界。")
    lines.append("")
    lines.append("## family 级通过情况")
    lines.append("")
    lines.append("| family | 多轮 | 单轮 | 前沿阈值 | 预算阈值 | 宽度上限 | 无ER重诱发 | all_ok |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in pair_rows:
        lines.append(
            f"| {row['family']} | {int(row['deep_multilayer_pass'])} | {int(row['single_round_cap_pass'])} | "
            f"{int(row['high_frontier_threshold_pass'])} | {int(row['high_budget_threshold_pass'])} | "
            f"{int(row['width_cap_pass'])} | {int(row['no_er_reinduction_pass'])} | {int(row['all_ok'])} |"
        )
    lines.append("")
    lines.append("## 白箱样例")
    lines.append("")
    deep = dict((whitebox.get("deep_case", {}) or {}))
    high_frontier = dict((whitebox.get("high_frontier_case", {}) or {}))
    width_cap = dict((whitebox.get("width_cap_case", {}) or {}))
    lines.append(f"- 多轮样例：family `{deep.get('family', '')}`，depth_max={deep.get('depth_max', 0)}，round_count={deep.get('round_count', 0)}，terminal_memory_count={deep.get('terminal_memory_count', 0)}，root_reinduction_count={deep.get('root_reinduction_count', 0)}。")
    lines.append(f"- 前沿阈值样例：depth_max={high_frontier.get('depth_max', 0)}，frontier_pruned_count={high_frontier.get('frontier_pruned_count', 0)}。")
    lines.append(f"- 宽度上限样例：frontier_out_count_max={width_cap.get('frontier_out_count_max', 0)}，frontier_pruned_count={width_cap.get('frontier_pruned_count', 0)}。")
    lines.append("")
    lines.append("## 多轮样例 round 摘要")
    lines.append("")
    lines.append("| round | frontier_in | frontier_out | pruned | memory_terminal | root_reinduction | frontier_budget | root_budget | delta_ev |")
    lines.append("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in round_rows:
        if str(row.get("family", "")) != str(deep.get("family", "")) or str(row.get("branch", "")) != "deep_multilayer":
            continue
        lines.append(
            f"| {int(row['round_index'])} | {int(row['frontier_in_count'])} | {int(row['frontier_out_count'])} | "
            f"{int(row['frontier_pruned_count'])} | {int(row['frontier_memory_terminal_count'])} | "
            f"{int(row['root_reinduction_count'])} | {float(row['frontier_budget_ev']):.6f} | "
            f"{float(row['root_induction_budget_ev']):.6f} | {float(row['round_delta_ev']):.6f} |"
        )
    lines.append("")
    lines.append("## 图表")
    lines.append("")
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    path = REPORT_DIR / f"E11_energy_graph_report_{stamp}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_experiment(*, stamp: str, family_count: int) -> dict[str, Any]:
    ensure_dirs()
    specs = FAMILY_SPECS[: max(1, min(int(family_count), len(FAMILY_SPECS)))]
    case_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    round_rows: list[dict[str, Any]] = []
    for spec in specs:
        for branch in BRANCH_ORDER:
            case_row, case_target_rows, case_round_rows = run_case(spec, branch)
            case_rows.append(case_row)
            target_rows.extend(case_target_rows)
            round_rows.extend(case_round_rows)
    case_rows.sort(key=lambda row: (str(row["family"]), BRANCH_ORDER.index(str(row["branch"]))))
    target_rows.sort(key=lambda row: (str(row["family"]), BRANCH_ORDER.index(str(row["branch"])), int(row["target_index"])))
    round_rows.sort(key=lambda row: (str(row["family"]), BRANCH_ORDER.index(str(row["branch"])), int(row["round_index"])))
    pair_rows = build_pair_rows(case_rows)
    summary = summarize_evidence(case_rows=case_rows, pair_rows=pair_rows)
    charts = make_charts(case_rows=case_rows, pair_rows=pair_rows, round_rows=round_rows, target_rows=target_rows, stamp=stamp)
    design_note = REPORT_DIR / "E11_energy_graph_design_logic.md"
    write_design_note(design_note)
    whitebox = {
        "deep_case": next((row for row in case_rows if str(row.get("branch", "")) == "deep_multilayer"), {}),
        "high_frontier_case": next((row for row in case_rows if str(row.get("branch", "")) == "high_frontier_threshold"), {}),
        "width_cap_case": next((row for row in case_rows if str(row.get("branch", "")) == "width_cap_one"), {}),
    }
    report = write_report(
        case_rows=case_rows,
        pair_rows=pair_rows,
        round_rows=round_rows,
        summary=summary,
        charts=charts,
        whitebox=whitebox,
        stamp=stamp,
    )
    case_csv = TABLE_DIR / f"e11_energy_graph_case_rows_{stamp}.csv"
    target_csv = TABLE_DIR / f"e11_energy_graph_target_rows_{stamp}.csv"
    round_csv = TABLE_DIR / f"e11_energy_graph_round_rows_{stamp}.csv"
    pair_csv = TABLE_DIR / f"e11_energy_graph_pair_rows_{stamp}.csv"
    summary_json = TABLE_DIR / f"e11_energy_graph_summary_{stamp}.json"
    whitebox_json = TABLE_DIR / f"e11_energy_graph_whitebox_{stamp}.json"
    e01.write_csv(case_csv, case_rows)
    e01.write_csv(target_csv, target_rows)
    e01.write_csv(round_csv, round_rows)
    e01.write_csv(pair_csv, pair_rows)
    e01.write_json(summary_json, summary)
    e01.write_json(whitebox_json, whitebox)
    evidence = {
        "experiment_id": "E11",
        "stamp": stamp,
        "support_level": summary.get("support_level", "unknown"),
        "summary": summary,
        "artifacts": {
            "case_rows": str(case_csv),
            "target_rows": str(target_csv),
            "round_rows": str(round_csv),
            "pair_rows": str(pair_csv),
            "summary": str(summary_json),
            "whitebox": str(whitebox_json),
            "report": str(report),
            "design_note": str(design_note),
            "charts": [str(path) for path in charts],
        },
    }
    e01.write_json(MANIFEST_DIR / f"E11_energy_graph_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E11_energy_graph_latest.json", evidence)
    return evidence


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper E11 finite energy graph experiment.")
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
