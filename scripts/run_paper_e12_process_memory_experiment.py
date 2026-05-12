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


E12_ROOT = ARTIFACT_ROOT / "E12_process_memory_state"
TABLE_DIR = E12_ROOT / "tables"
CHART_DIR = E12_ROOT / "charts"
REPORT_DIR = E12_ROOT / "reports"
MANIFEST_DIR = E12_ROOT / "manifests"

STAMP_DEFAULT = "e12_final_v1"


@dataclass(frozen=True)
class FamilySpec:
    family: str
    process_ev: float
    memory_ev_a: float
    memory_ev_b: float
    memory_er_b: float
    process_weight_a: float
    process_weight_b: float


FAMILY_SPECS: list[FamilySpec] = [
    FamilySpec("F01", 0.40, 0.42, 0.58, 0.12, 0.62, 0.38),
    FamilySpec("F02", 0.41, 0.43, 0.57, 0.13, 0.61, 0.39),
    FamilySpec("F03", 0.42, 0.44, 0.56, 0.14, 0.60, 0.40),
    FamilySpec("F04", 0.43, 0.45, 0.55, 0.15, 0.63, 0.37),
    FamilySpec("F05", 0.44, 0.46, 0.54, 0.16, 0.64, 0.36),
    FamilySpec("F06", 0.45, 0.47, 0.53, 0.17, 0.59, 0.41),
    FamilySpec("F07", 0.46, 0.48, 0.52, 0.18, 0.58, 0.42),
    FamilySpec("F08", 0.47, 0.49, 0.51, 0.19, 0.65, 0.35),
    FamilySpec("F09", 0.48, 0.50, 0.50, 0.20, 0.57, 0.43),
    FamilySpec("F10", 0.49, 0.51, 0.49, 0.21, 0.66, 0.34),
    FamilySpec("F11", 0.50, 0.52, 0.48, 0.22, 0.56, 0.44),
    FamilySpec("F12", 0.51, 0.53, 0.47, 0.23, 0.67, 0.33),
]

BRANCHES = (
    "memory_converge",
    "structure_process_only",
    "split_memory_control",
    "memory_decay",
)

BRANCH_LABELS = {
    "memory_converge": "同记忆汇聚",
    "structure_process_only": "仅结构过程态",
    "split_memory_control": "不同记忆不合并",
    "memory_decay": "记忆激活衰减",
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
        ext={"kind": "paper_e12_seed", "relation_type": "paper_e12_seed"},
    )
    structure_obj, _created = hdb._structure_store.create_structure(
        structure_payload=payload,
        trace_id=trace_id,
        tick_id=trace_id,
        origin="paper_e12_seed",
        origin_id=packet.get("id", trace_id),
        parent_ids=[],
    )
    hdb._pointer_index.register_structure(structure_obj)
    return structure_obj


def append_memory(hdb: HDB, *, label: str, structure_refs: list[str], trace_id: str) -> str:
    result = hdb.append_episodic_memory(
        episodic_payload={
            "event_summary": label,
            "structure_refs": list(structure_refs),
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


def setup_hdb(tmp_dir: str) -> HDB:
    return HDB(
        config_override={
            "data_dir": tmp_dir,
            "enable_background_repair": False,
            "induction_energy_graph_v2_enabled": True,
            "induction_energy_graph_v2_max_rounds": 3,
            "induction_energy_graph_v2_root_er_decay_ratio": 0.82,
            "induction_energy_graph_v2_min_frontier_ev": 0.05,
            "induction_energy_graph_v2_min_budget": 0.03,
            "induction_min_entry_base_weight": 0.0,
            "owner_db_runtime_budget_enabled": False,
            "ev_propagation_threshold": 0.05,
            "er_induction_threshold": 0.05,
            "memory_activation_decay_round_ratio_ev": 0.5,
            "memory_activation_prune_threshold_ev": 0.05,
        }
    )


def build_graph(hdb: HDB, *, spec: FamilySpec, branch: str) -> dict[str, Any]:
    prefix = f"{spec.family}_{branch}"
    structures = {
        "A": store_packet_as_structure(hdb, "A", prefix=prefix, trace_id=f"{prefix}_seed_A"),
        "B": store_packet_as_structure(hdb, "B", prefix=prefix, trace_id=f"{prefix}_seed_B"),
        "AB": store_packet_as_structure(hdb, "AB", prefix=prefix, trace_id=f"{prefix}_seed_AB"),
        "AC": store_packet_as_structure(hdb, "AC", prefix=prefix, trace_id=f"{prefix}_seed_AC"),
        "ABD": store_packet_as_structure(hdb, "ABD", prefix=prefix, trace_id=f"{prefix}_seed_ABD"),
        "ACD": store_packet_as_structure(hdb, "ACD", prefix=prefix, trace_id=f"{prefix}_seed_ACD"),
        "A_only_tail": store_packet_as_structure(hdb, "AX", prefix=prefix, trace_id=f"{prefix}_seed_AX"),
        "B_only_tail": store_packet_as_structure(hdb, "BY", prefix=prefix, trace_id=f"{prefix}_seed_BY"),
    }
    shared_memory = append_memory(
        hdb,
        label=f"{spec.family} shared target memory",
        structure_refs=[structures["ABD"]["id"], structures["ACD"]["id"]],
        trace_id=f"{prefix}_memory_shared",
    )
    memory_a = append_memory(
        hdb,
        label=f"{spec.family} split target memory A",
        structure_refs=[structures["A_only_tail"]["id"]],
        trace_id=f"{prefix}_memory_a",
    )
    memory_b = append_memory(
        hdb,
        label=f"{spec.family} split target memory B",
        structure_refs=[structures["B_only_tail"]["id"]],
        trace_id=f"{prefix}_memory_b",
    )

    add_edge(hdb, owner=structures["A"], target=structures["AB"], weight=spec.process_weight_a, residual="B")
    add_edge(hdb, owner=structures["A"], target=structures["ABD"], weight=1.0 - spec.process_weight_a, residual="D", memory_id=shared_memory)
    add_edge(hdb, owner=structures["B"], target=structures["AC"], weight=spec.process_weight_b, residual="C")
    add_edge(hdb, owner=structures["B"], target=structures["ACD"], weight=1.0 - spec.process_weight_b, residual="D", memory_id=shared_memory)
    add_edge(hdb, owner=structures["AB"], target=structures["ABD"], weight=1.0, residual="D", memory_id=shared_memory)
    add_edge(hdb, owner=structures["AC"], target=structures["ACD"], weight=1.0, residual="D", memory_id=shared_memory)
    add_edge(hdb, owner=structures["A"], target=structures["A_only_tail"], weight=1.0, residual="X", memory_id=memory_a)
    add_edge(hdb, owner=structures["B"], target=structures["B_only_tail"], weight=1.0, residual="Y", memory_id=memory_b)
    return {"structures": structures, "shared_memory": shared_memory, "memory_a": memory_a, "memory_b": memory_b}


def run_induction_for_source(hdb: HDB, *, source_id: str, er: float, ev: float, trace_id: str) -> dict[str, Any]:
    result = hdb.run_induction_propagation(
        state_snapshot={
            "summary": {"active_item_count": 1},
            "top_items": [
                {
                    "id": f"runtime_{trace_id}",
                    "ref_object_type": "st",
                    "ref_object_id": source_id,
                    "display": source_id,
                    "display_text": source_id,
                    "er": float(er),
                    "ev": float(ev),
                }
            ],
        },
        trace_id=trace_id,
        max_source_items=1,
        enable_ev_propagation=True,
        enable_er_induction=True,
    )
    if not result.get("success", False):
        raise RuntimeError(f"run_induction_propagation failed: {result}")
    return result.get("data", {}) or {}


def apply_memory_targets(hdb: HDB, targets: list[dict[str, Any]], *, trace_id: str) -> dict[str, Any]:
    result = hdb.apply_memory_activation_targets(targets=targets, trace_id=trace_id)
    if not result.get("success", False):
        raise RuntimeError(f"apply_memory_activation_targets failed: {result}")
    return result.get("data", {}) or {}


def snapshot_memory(hdb: HDB, *, trace_id: str) -> dict[str, Any]:
    result = hdb.get_memory_activation_snapshot(trace_id=trace_id, limit=8)
    if not result.get("success", False):
        raise RuntimeError(f"get_memory_activation_snapshot failed: {result}")
    return result.get("data", {}) or {}


def item_for_memory(snapshot: dict[str, Any], memory_id: str) -> dict[str, Any]:
    for item in list(snapshot.get("items", []) or []):
        if str(item.get("memory_id", "") or "") == str(memory_id):
            return dict(item)
    return {}


def memory_targets_from(data: dict[str, Any], memory_id: str | None = None) -> list[dict[str, Any]]:
    rows = [row for row in list(data.get("induction_targets", []) or []) if str(row.get("projection_kind", "")) == "memory"]
    if memory_id:
        rows = [row for row in rows if str(row.get("memory_id", "")) == memory_id]
    return rows


def structure_targets_from(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in list(data.get("induction_targets", []) or []) if str(row.get("projection_kind", "")) == "structure"]


def run_case(spec: FamilySpec, branch: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    tmp_dir = tempfile.mkdtemp(prefix=f"paper_e12_{spec.family}_{branch}_")
    hdb = setup_hdb(tmp_dir)
    try:
        graph = build_graph(hdb, spec=spec, branch=branch)
        st = graph["structures"]
        shared_memory = graph["shared_memory"]
        memory_a = graph["memory_a"]
        memory_b = graph["memory_b"]
        target_rows: list[dict[str, Any]] = []

        if branch == "memory_converge":
            data_a = run_induction_for_source(hdb, source_id=st["A"]["id"], er=spec.memory_er_b, ev=spec.memory_ev_a, trace_id=f"{spec.family}_{branch}_A_mixed")
            data_b = run_induction_for_source(hdb, source_id=st["B"]["id"], er=spec.memory_er_b, ev=spec.memory_ev_b, trace_id=f"{spec.family}_{branch}_B_mixed")
            targets = memory_targets_from(data_a, shared_memory) + memory_targets_from(data_b, shared_memory)
            apply_data = apply_memory_targets(hdb, targets, trace_id=f"{spec.family}_{branch}_apply")
            snap = snapshot_memory(hdb, trace_id=f"{spec.family}_{branch}_snapshot")
            item = item_for_memory(snap, shared_memory)
            process_targets = structure_targets_from(data_a) + structure_targets_from(data_b)
            row = summarize_case(
                spec=spec,
                branch=branch,
                graph=graph,
                apply_data=apply_data,
                snapshot=snap,
                item=item,
                process_targets=process_targets,
                memory_targets=targets,
            )
        elif branch == "structure_process_only":
            data_a = run_induction_for_source(hdb, source_id=st["A"]["id"], er=0.0, ev=spec.process_ev, trace_id=f"{spec.family}_{branch}_A_process")
            data_b = run_induction_for_source(hdb, source_id=st["B"]["id"], er=0.0, ev=spec.process_ev, trace_id=f"{spec.family}_{branch}_B_process")
            process_targets = structure_targets_from(data_a) + structure_targets_from(data_b)
            apply_data = apply_memory_targets(hdb, [], trace_id=f"{spec.family}_{branch}_apply_empty")
            snap = snapshot_memory(hdb, trace_id=f"{spec.family}_{branch}_snapshot")
            row = summarize_case(
                spec=spec,
                branch=branch,
                graph=graph,
                apply_data=apply_data,
                snapshot=snap,
                item={},
                process_targets=process_targets,
                memory_targets=[],
            )
        elif branch == "split_memory_control":
            targets = [
                {
                    "projection_kind": "memory",
                    "memory_id": memory_a,
                    "target_display_text": f"{spec.family} split A",
                    "delta_ev": spec.memory_ev_a,
                    "sources": [st["A"]["id"]],
                    "modes": ["ev_propagation"],
                    "backing_structure_id": st["A_only_tail"]["id"],
                },
                {
                    "projection_kind": "memory",
                    "memory_id": memory_b,
                    "target_display_text": f"{spec.family} split B",
                    "delta_ev": spec.memory_ev_b,
                    "sources": [st["B"]["id"]],
                    "modes": ["er_induction"],
                    "backing_structure_id": st["B_only_tail"]["id"],
                },
            ]
            apply_data = apply_memory_targets(hdb, targets, trace_id=f"{spec.family}_{branch}_apply")
            snap = snapshot_memory(hdb, trace_id=f"{spec.family}_{branch}_snapshot")
            row = summarize_case(
                spec=spec,
                branch=branch,
                graph=graph,
                apply_data=apply_data,
                snapshot=snap,
                item={},
                process_targets=[],
                memory_targets=targets,
            )
        elif branch == "memory_decay":
            targets = [
                {
                    "projection_kind": "memory",
                    "memory_id": shared_memory,
                    "target_display_text": f"{spec.family} shared target memory",
                    "delta_ev": spec.memory_ev_a + spec.memory_ev_b,
                    "sources": [st["A"]["id"], st["B"]["id"]],
                    "modes": ["ev_propagation"],
                    "backing_structure_id": st["ABD"]["id"],
                }
            ]
            apply_data = apply_memory_targets(hdb, targets, trace_id=f"{spec.family}_{branch}_apply")
            before = snapshot_memory(hdb, trace_id=f"{spec.family}_{branch}_snapshot_before")
            tick_result = hdb.tick_memory_activation_pool(trace_id=f"{spec.family}_{branch}_tick")
            if not tick_result.get("success", False):
                raise RuntimeError(f"tick_memory_activation_pool failed: {tick_result}")
            after = snapshot_memory(hdb, trace_id=f"{spec.family}_{branch}_snapshot_after")
            item_before = item_for_memory(before, shared_memory)
            item_after = item_for_memory(after, shared_memory)
            row = summarize_case(
                spec=spec,
                branch=branch,
                graph=graph,
                apply_data=apply_data,
                snapshot=after,
                item=item_after,
                process_targets=[],
                memory_targets=targets,
            )
            row["decay_before_ev"] = round(float(item_before.get("ev", 0.0) or 0.0), 8)
            row["decay_after_ev"] = round(float(item_after.get("ev", 0.0) or 0.0), 8)
            row["decay_ratio_observed"] = round(
                float(row["decay_after_ev"]) / max(1e-12, float(row["decay_before_ev"])),
                8,
            )
        else:
            raise ValueError(f"unknown branch: {branch}")

        for index, target in enumerate(row.pop("_target_dump", [])):
            target_rows.append(
                {
                    "family": spec.family,
                    "branch": branch,
                    "target_index": index,
                    "projection_kind": target.get("projection_kind", ""),
                    "memory_id": target.get("memory_id", ""),
                    "target_structure_id": target.get("target_structure_id", target.get("structure_id", "")),
                    "delta_ev": round(float(target.get("delta_ev", 0.0) or 0.0), 8),
                    "delta_er": round(float(target.get("delta_er", 0.0) or 0.0), 8),
                    "modes": "|".join(str(x) for x in (target.get("modes", []) or [])),
                    "sources": "|".join(str(x) for x in (target.get("sources", []) or [])),
                    "backing_structure_id": target.get("backing_structure_id", ""),
                }
            )
        return row, target_rows
    finally:
        hdb.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def summarize_case(
    *,
    spec: FamilySpec,
    branch: str,
    graph: dict[str, Any],
    apply_data: dict[str, Any],
    snapshot: dict[str, Any],
    item: dict[str, Any],
    process_targets: list[dict[str, Any]],
    memory_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    shared_memory = graph["shared_memory"]
    memory_a = graph["memory_a"]
    memory_b = graph["memory_b"]
    st = graph["structures"]
    summary = dict(snapshot.get("summary", {}) or {})
    mode_totals = dict(item.get("mode_totals", {}) or {})
    mode_totals_ev = dict(item.get("mode_totals_ev", {}) or {})
    source_ids = [str(x) for x in list(item.get("source_structure_ids", []) or [])]
    backing_ids = [str(x) for x in list(item.get("backing_structure_ids", []) or [])]
    memory_ids_in_snapshot = [str(row.get("memory_id", "")) for row in list(snapshot.get("items", []) or [])]
    process_ids = {str(row.get("target_structure_id", row.get("structure_id", "")) or "") for row in process_targets}

    row = {
        "family": spec.family,
        "branch": branch,
        "branch_label": BRANCH_LABELS.get(branch, branch),
        "memory_apply_count": int(apply_data.get("applied_count", 0) or 0),
        "memory_apply_total_delta_ev": round(float(apply_data.get("total_delta_ev", 0.0) or 0.0), 8),
        "memory_snapshot_count": int(summary.get("count", 0) or 0),
        "memory_snapshot_total_ev": round(float(summary.get("total_ev", 0.0) or 0.0), 8),
        "shared_memory_present": int(shared_memory in memory_ids_in_snapshot),
        "split_memory_a_present": int(memory_a in memory_ids_in_snapshot),
        "split_memory_b_present": int(memory_b in memory_ids_in_snapshot),
        "shared_memory_ev": round(float(item.get("ev", 0.0) or 0.0), 8),
        "shared_memory_er": round(float(item.get("er", 0.0) or 0.0), 8),
        "shared_memory_hit_count": int(item.get("hit_count", 0) or 0),
        "shared_memory_update_count": int(item.get("update_count", 0) or 0),
        "shared_mode_ev_propagation": round(float(mode_totals.get("ev_propagation", 0.0) or 0.0), 8),
        "shared_mode_er_induction": round(float(mode_totals.get("er_induction", 0.0) or 0.0), 8),
        "shared_mode_ev_only_ev": round(float(mode_totals_ev.get("ev_propagation", 0.0) or 0.0), 8),
        "shared_mode_er_only_ev": round(float(mode_totals_ev.get("er_induction", 0.0) or 0.0), 8),
        "shared_source_count": len(set(source_ids)),
        "shared_backing_count": len(set(backing_ids)),
        "process_target_count": len(process_targets),
        "process_has_AB": int(st["AB"]["id"] in process_ids),
        "process_has_AC": int(st["AC"]["id"] in process_ids),
        "process_has_continuable": int(st["AB"]["id"] in process_ids or st["AC"]["id"] in process_ids),
        "memory_target_count": len(memory_targets),
        "memory_targets_unique_memory_count": len({str(row.get("memory_id", "")) for row in memory_targets if str(row.get("memory_id", ""))}),
        "decay_before_ev": 0.0,
        "decay_after_ev": 0.0,
        "decay_ratio_observed": 0.0,
        "_target_dump": list(memory_targets) + list(process_targets),
    }
    return row


def build_pair_rows(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_family: dict[str, dict[str, dict[str, Any]]] = {}
    for row in case_rows:
        by_family.setdefault(str(row["family"]), {})[str(row["branch"])] = row
    pair_rows: list[dict[str, Any]] = []
    for family in sorted(by_family):
        mapping = by_family[family]
        converge = mapping.get("memory_converge", {})
        process = mapping.get("structure_process_only", {})
        split = mapping.get("split_memory_control", {})
        decay = mapping.get("memory_decay", {})
        row = {
            "family": family,
            "memory_converge_pass": int(
                int(converge.get("memory_apply_count", 0) or 0) == 1
                and int(converge.get("memory_snapshot_count", 0) or 0) == 1
                and int(converge.get("shared_memory_hit_count", 0) or 0) >= 2
                and int(converge.get("shared_source_count", 0) or 0) >= 2
                and int(converge.get("shared_backing_count", 0) or 0) >= 1
                and float(converge.get("shared_mode_ev_propagation", 0.0) or 0.0) > 0.0
                and float(converge.get("shared_mode_er_induction", 0.0) or 0.0) > 0.0
            ),
            "structure_process_pass": int(
                int(process.get("memory_apply_count", 0) or 0) == 0
                and int(process.get("memory_snapshot_count", 0) or 0) == 0
                and int(process.get("process_has_AB", 0) or 0) == 1
                and int(process.get("process_has_AC", 0) or 0) == 1
            ),
            "split_memory_control_pass": int(
                int(split.get("memory_apply_count", 0) or 0) == 2
                and int(split.get("memory_snapshot_count", 0) or 0) == 2
                and int(split.get("split_memory_a_present", 0) or 0) == 1
                and int(split.get("split_memory_b_present", 0) or 0) == 1
                and int(split.get("shared_memory_present", 0) or 0) == 0
            ),
            "memory_decay_pass": int(
                int(decay.get("memory_apply_count", 0) or 0) == 1
                and float(decay.get("decay_before_ev", 0.0) or 0.0) > float(decay.get("decay_after_ev", 0.0) or 0.0) > 0.0
                and abs(float(decay.get("decay_ratio_observed", 0.0) or 0.0) - 0.5) <= 1e-6
            ),
            "converge_shared_ev": round(float(converge.get("shared_memory_ev", 0.0) or 0.0), 8),
            "converge_hit_count": int(converge.get("shared_memory_hit_count", 0) or 0),
            "converge_source_count": int(converge.get("shared_source_count", 0) or 0),
            "process_target_count": int(process.get("process_target_count", 0) or 0),
            "split_memory_count": int(split.get("memory_snapshot_count", 0) or 0),
            "decay_ratio_observed": round(float(decay.get("decay_ratio_observed", 0.0) or 0.0), 8),
        }
        row["all_ok"] = int(
            int(row["memory_converge_pass"]) == 1
            and int(row["structure_process_pass"]) == 1
            and int(row["split_memory_control_pass"]) == 1
            and int(row["memory_decay_pass"]) == 1
        )
        pair_rows.append(row)
    return pair_rows


def summarize_evidence(*, case_rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]]) -> dict[str, Any]:
    def branch_rows(branch: str) -> list[dict[str, Any]]:
        return [row for row in case_rows if str(row.get("branch", "")) == branch]

    converge_rows = branch_rows("memory_converge")
    process_rows = branch_rows("structure_process_only")
    split_rows = branch_rows("split_memory_control")
    decay_rows = branch_rows("memory_decay")
    summary: dict[str, Any] = {
        "case_count": int(len(case_rows)),
        "family_count": int(len(pair_rows)),
        "memory_converge_pass_ratio": round(safe_ratio(sum(int(row.get("memory_converge_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "structure_process_pass_ratio": round(safe_ratio(sum(int(row.get("structure_process_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "split_memory_control_pass_ratio": round(safe_ratio(sum(int(row.get("split_memory_control_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "memory_decay_pass_ratio": round(safe_ratio(sum(int(row.get("memory_decay_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "all_ok_ratio": round(safe_ratio(sum(int(row.get("all_ok", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "converge_apply_count_mean": mean_or_zero([num(row, "memory_apply_count") for row in converge_rows]),
        "converge_snapshot_count_mean": mean_or_zero([num(row, "memory_snapshot_count") for row in converge_rows]),
        "converge_hit_count_mean": mean_or_zero([num(row, "shared_memory_hit_count") for row in converge_rows]),
        "converge_source_count_mean": mean_or_zero([num(row, "shared_source_count") for row in converge_rows]),
        "converge_ev_mean": mean_or_zero([num(row, "shared_memory_ev") for row in converge_rows]),
        "converge_ev_mode_mean": mean_or_zero([num(row, "shared_mode_ev_propagation") for row in converge_rows]),
        "converge_er_mode_mean": mean_or_zero([num(row, "shared_mode_er_induction") for row in converge_rows]),
        "process_target_count_mean": mean_or_zero([num(row, "process_target_count") for row in process_rows]),
        "process_memory_snapshot_count_mean": mean_or_zero([num(row, "memory_snapshot_count") for row in process_rows]),
        "split_memory_count_mean": mean_or_zero([num(row, "memory_snapshot_count") for row in split_rows]),
        "decay_ratio_mean": mean_or_zero([num(row, "decay_ratio_observed") for row in decay_rows]),
    }
    wins = int(sum(int(row.get("all_ok", 0) or 0) for row in pair_rows))
    losses = int(len(pair_rows) - wins)
    summary["all_ok_sign_p"] = sign_test_p_value(wins, losses)
    support_level = "not_supported"
    if (
        len(pair_rows) >= 8
        and summary["memory_converge_pass_ratio"] >= 0.999
        and summary["structure_process_pass_ratio"] >= 0.999
        and summary["split_memory_control_pass_ratio"] >= 0.999
        and summary["memory_decay_pass_ratio"] >= 0.999
        and summary["all_ok_ratio"] >= 0.999
        and summary["all_ok_sign_p"] <= 0.01
    ):
        support_level = "strong_evidence"
    elif len(pair_rows) >= 4 and summary["memory_converge_pass_ratio"] >= 0.80:
        support_level = "useful_but_not_strong"
    summary["support_level"] = support_level
    return summary


def make_charts(*, case_rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]], stamp: str) -> list[Path]:
    plt = e01.setup_matplotlib()
    paths: list[Path] = []

    branch_labels = [BRANCH_LABELS[b] for b in BRANCHES]
    memory_counts = [mean_or_zero([num(row, "memory_snapshot_count") for row in case_rows if str(row.get("branch", "")) == b]) for b in BRANCHES]
    process_counts = [mean_or_zero([num(row, "process_target_count") for row in case_rows if str(row.get("branch", "")) == b]) for b in BRANCHES]
    fig, ax = plt.subplots(figsize=(10.5, 4.5))
    xs = list(range(len(BRANCHES)))
    width = 0.35
    ax.bar([x - width / 2 for x in xs], memory_counts, width=width, color="#16a34a", label="记忆激活条目")
    ax.bar([x + width / 2 for x in xs], process_counts, width=width, color="#2563eb", label="结构过程目标")
    ax.set_xticks(xs, branch_labels, rotation=15)
    ax.set_title("E12 结构过程态与记忆目标态的角色分离")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False)
    fig.tight_layout()
    path = CHART_DIR / f"e12_process_memory_role_split_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    converge_rows = [row for row in case_rows if str(row.get("branch", "")) == "memory_converge"]
    metrics = [
        ("shared_memory_hit_count", "命中计数"),
        ("shared_source_count", "来源数"),
        ("shared_mode_ev_propagation", "EV模式量"),
        ("shared_mode_er_induction", "ER模式量"),
    ]
    fig, ax = plt.subplots(figsize=(9.4, 4.2))
    vals = [mean_or_zero([num(row, key) for row in converge_rows]) for key, _ in metrics]
    ax.bar([label for _, label in metrics], vals, color=["#16a34a", "#16a34a", "#2563eb", "#dc2626"], alpha=0.88)
    ax.set_title("E12 同一记忆目标的多来源/多模式汇聚")
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = CHART_DIR / f"e12_memory_convergence_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    decay_rows = [row for row in case_rows if str(row.get("branch", "")) == "memory_decay"]
    before = mean_or_zero([num(row, "decay_before_ev") for row in decay_rows])
    after = mean_or_zero([num(row, "decay_after_ev") for row in decay_rows])
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    ax.bar(["维护前", "维护后"], [before, after], color=["#2563eb", "#16a34a"], alpha=0.88)
    ax.set_title("E12 记忆激活维护中的目标态衰减")
    ax.set_ylabel("EV")
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = CHART_DIR / f"e12_memory_decay_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    family_labels = [str(row.get("family", "")) for row in pair_rows]
    family_ok = [int(row.get("all_ok", 0) or 0) for row in pair_rows]
    fig, ax = plt.subplots(figsize=(9.4, 4.2))
    ax.bar(family_labels, family_ok, color=["#16a34a" if v else "#dc2626" for v in family_ok])
    ax.set_ylim(0.0, 1.1)
    ax.set_ylabel("all_ok")
    ax.set_title("E12 family 级过程态/目标态证据链整体通过情况")
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = CHART_DIR / f"e12_process_memory_family_pass_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)
    return paths


def write_design_note(path: Path) -> None:
    lines = [
        "# E12 设计逻辑",
        "",
        "本实验把“结构过程态与记忆目标态”收窄为三个白箱命题：同一 memory_id 可以汇聚来自不同结构和不同模式的能量；只含结构目标的过程路径不会写入记忆激活池；不同 memory_id 即使同时被赋能，也不会被错误合并成同一个记忆目标。",
        "",
        "实验避免使用宽泛自然语言判断，而是直接观察 `apply_memory_activation_targets`、`get_memory_activation_snapshot` 和 induction 结构目标。记忆目标以 memory_id 为聚合键；结构目标以 target_structure_id 保留为可继续展开的过程节点。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    *,
    case_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    charts: list[Path],
    whitebox: dict[str, Any],
    stamp: str,
) -> Path:
    lines = [
        f"# E12 结构过程态与记忆目标态报告（{stamp}）",
        "",
        "## 核心结论",
        "",
        f"- 支持等级：**{summary.get('support_level', 'unknown')}**",
        f"- family 数：{int(summary.get('family_count', 0))}",
        f"- case 数：{int(summary.get('case_count', 0))}",
        f"- 整体通过比例：{summary.get('all_ok_ratio', 0.0):.3f}",
        f"- 符号检验 p 值：{summary.get('all_ok_sign_p', 1.0):.8f}",
        f"- 四分支通过比例：{summary.get('memory_converge_pass_ratio', 0.0):.3f} / {summary.get('structure_process_pass_ratio', 0.0):.3f} / {summary.get('split_memory_control_pass_ratio', 0.0):.3f} / {summary.get('memory_decay_pass_ratio', 0.0):.3f}",
        "",
        "## 正文可使用的最小命题",
        "",
        "在当前 AP 原型中，结构目标与情景记忆目标具有可复查的角色差异。结构目标保留为可继续进入诱发链的过程节点；同一情景记忆目标则以 memory_id 为稳定聚合键，能够汇聚不同来源与不同模式的能量，并在记忆激活池中作为具体经历目标被维护。",
        "",
        "## family 级通过情况",
        "",
        "| family | 记忆汇聚 | 结构过程 | 不同记忆不合并 | 记忆衰减 | all_ok |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in pair_rows:
        lines.append(
            f"| {row['family']} | {int(row['memory_converge_pass'])} | {int(row['structure_process_pass'])} | "
            f"{int(row['split_memory_control_pass'])} | {int(row['memory_decay_pass'])} | {int(row['all_ok'])} |"
        )
    lines.extend(
        [
            "",
            "## 白箱样例",
            "",
        ]
    )
    converge = dict((whitebox.get("memory_converge", {}) or {}))
    process = dict((whitebox.get("structure_process_only", {}) or {}))
    split = dict((whitebox.get("split_memory_control", {}) or {}))
    decay = dict((whitebox.get("memory_decay", {}) or {}))
    lines.append(f"- 记忆汇聚样例：family `{converge.get('family', '')}`，apply_count={converge.get('memory_apply_count', 0)}，snapshot_count={converge.get('memory_snapshot_count', 0)}，hit_count={converge.get('shared_memory_hit_count', 0)}，source_count={converge.get('shared_source_count', 0)}。")
    lines.append(f"- 结构过程样例：process_target_count={process.get('process_target_count', 0)}，memory_snapshot_count={process.get('memory_snapshot_count', 0)}。")
    lines.append(f"- 不同记忆不合并样例：apply_count={split.get('memory_apply_count', 0)}，snapshot_count={split.get('memory_snapshot_count', 0)}。")
    lines.append(f"- 记忆衰减样例：before_ev={decay.get('decay_before_ev', 0.0)}，after_ev={decay.get('decay_after_ev', 0.0)}，ratio={decay.get('decay_ratio_observed', 0.0)}。")
    lines.extend(["", "## 图表", ""])
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    path = REPORT_DIR / f"E12_process_memory_report_{stamp}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_experiment(*, stamp: str, family_count: int) -> dict[str, Any]:
    ensure_dirs()
    specs = FAMILY_SPECS[: max(1, min(int(family_count), len(FAMILY_SPECS)))]
    case_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    for spec in specs:
        for branch in BRANCHES:
            case_row, branch_targets = run_case(spec, branch)
            case_rows.append(case_row)
            target_rows.extend(branch_targets)
    case_rows.sort(key=lambda row: (str(row["family"]), BRANCHES.index(str(row["branch"]))))
    target_rows.sort(key=lambda row: (str(row["family"]), BRANCHES.index(str(row["branch"])), int(row["target_index"])))
    pair_rows = build_pair_rows(case_rows)
    summary = summarize_evidence(case_rows=case_rows, pair_rows=pair_rows)
    charts = make_charts(case_rows=case_rows, pair_rows=pair_rows, stamp=stamp)
    design_note = REPORT_DIR / "E12_process_memory_design_logic.md"
    write_design_note(design_note)
    whitebox = {
        "memory_converge": next((row for row in case_rows if str(row.get("branch", "")) == "memory_converge"), {}),
        "structure_process_only": next((row for row in case_rows if str(row.get("branch", "")) == "structure_process_only"), {}),
        "split_memory_control": next((row for row in case_rows if str(row.get("branch", "")) == "split_memory_control"), {}),
        "memory_decay": next((row for row in case_rows if str(row.get("branch", "")) == "memory_decay"), {}),
    }
    report = write_report(case_rows=case_rows, pair_rows=pair_rows, summary=summary, charts=charts, whitebox=whitebox, stamp=stamp)
    case_csv = TABLE_DIR / f"e12_process_memory_case_rows_{stamp}.csv"
    target_csv = TABLE_DIR / f"e12_process_memory_target_rows_{stamp}.csv"
    pair_csv = TABLE_DIR / f"e12_process_memory_pair_rows_{stamp}.csv"
    summary_json = TABLE_DIR / f"e12_process_memory_summary_{stamp}.json"
    whitebox_json = TABLE_DIR / f"e12_process_memory_whitebox_{stamp}.json"
    e01.write_csv(case_csv, case_rows)
    e01.write_csv(target_csv, target_rows)
    e01.write_csv(pair_csv, pair_rows)
    e01.write_json(summary_json, summary)
    e01.write_json(whitebox_json, whitebox)
    evidence = {
        "experiment_id": "E12",
        "stamp": stamp,
        "support_level": summary.get("support_level", "unknown"),
        "summary": summary,
        "artifacts": {
            "case_rows": str(case_csv),
            "target_rows": str(target_csv),
            "pair_rows": str(pair_csv),
            "summary": str(summary_json),
            "whitebox": str(whitebox_json),
            "report": str(report),
            "design_note": str(design_note),
            "charts": [str(path) for path in charts],
        },
    }
    e01.write_json(MANIFEST_DIR / f"E12_process_memory_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E12_process_memory_latest.json", evidence)
    return evidence


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper E12 process/memory state experiment.")
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
