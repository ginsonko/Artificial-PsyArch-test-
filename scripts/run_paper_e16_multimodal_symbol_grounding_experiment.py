from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from _reproduction_paths import AP_ROOT, ARTIFACT_ROOT, ATTACHMENT_ROOT

if str(AP_ROOT) not in sys.path:
    sys.path.insert(0, str(AP_ROOT))

import run_paper_e01_experiment as e01
from state_pool.main import StatePool


E16_ROOT = ARTIFACT_ROOT / "E16_multimodal_symbol_grounding"
TABLE_DIR = E16_ROOT / "tables"
CHART_DIR = E16_ROOT / "charts"
REPORT_DIR = E16_ROOT / "reports"
MANIFEST_DIR = E16_ROOT / "manifests"

STAMP_DEFAULT = "e16_final_v1"


BRANCH_ORDER = (
    "packet_multimodal_bound",
    "packet_wrong_anchor_control",
    "packet_attribute_folded_control",
    "runtime_tool_binding",
    "runtime_wrong_target_control",
    "runtime_invalid_role_control",
)

BRANCH_LABELS = {
    "packet_multimodal_bound": "packet多来源绑定",
    "packet_wrong_anchor_control": "packet错误锚点对照",
    "packet_attribute_folded_control": "packet折叠对照",
    "runtime_tool_binding": "runtime工具绑定",
    "runtime_wrong_target_control": "runtime错误目标对照",
    "runtime_invalid_role_control": "runtime非法角色对照",
}


@dataclass(frozen=True)
class FamilySpec:
    family: str
    target_token: str
    distractor_token: str
    visual_attr_name: str
    visual_attr_value: str
    spatial_attr_name: str
    spatial_attr_value: str
    tool_attr_name: str
    tool_attr_value: str
    tactile_attr_name: str
    tactile_attr_value: float
    visual_er: float
    spatial_er: float
    tactile_er: float
    tool_ev: float


FAMILY_SPECS: list[FamilySpec] = [
    FamilySpec("F01", "目标物A01", "干扰物B01", "visual_color", "red", "visual_position", "left_top", "tool_result", "verified", "tactile_pressure", 0.21, 0.42, 0.31, 0.22, 0.56),
    FamilySpec("F02", "目标物A02", "干扰物B02", "visual_color", "blue", "visual_position", "right_top", "tool_result", "cached", "tactile_pressure", 0.24, 0.44, 0.32, 0.24, 0.58),
    FamilySpec("F03", "目标物A03", "干扰物B03", "visual_shape", "circle", "visual_position", "center", "tool_result", "matched", "tactile_pressure", 0.27, 0.46, 0.33, 0.26, 0.60),
    FamilySpec("F04", "目标物A04", "干扰物B04", "visual_shape", "triangle", "visual_position", "left_bottom", "tool_result", "parsed", "tactile_pressure", 0.30, 0.48, 0.34, 0.28, 0.62),
    FamilySpec("F05", "目标物A05", "干扰物B05", "visual_texture", "rough", "visual_position", "right_bottom", "tool_status", "ok", "tactile_pressure", 0.33, 0.50, 0.35, 0.30, 0.64),
    FamilySpec("F06", "目标物A06", "干扰物B06", "visual_texture", "smooth", "visual_position", "front", "tool_status", "stable", "tactile_pressure", 0.36, 0.52, 0.36, 0.32, 0.66),
    FamilySpec("F07", "目标物A07", "干扰物B07", "visual_brightness", "high", "visual_position", "rear", "tool_status", "ready", "tactile_pressure", 0.39, 0.54, 0.37, 0.34, 0.68),
    FamilySpec("F08", "目标物A08", "干扰物B08", "visual_brightness", "low", "visual_position", "near", "tool_status", "fresh", "tactile_pressure", 0.42, 0.56, 0.38, 0.36, 0.70),
    FamilySpec("F09", "目标物A09", "干扰物B09", "visual_motion", "moving", "visual_position", "far", "tool_confidence", "high", "tactile_pressure", 0.45, 0.58, 0.39, 0.38, 0.72),
    FamilySpec("F10", "目标物A10", "干扰物B10", "visual_motion", "still", "visual_position", "upper", "tool_confidence", "medium", "tactile_pressure", 0.48, 0.60, 0.40, 0.40, 0.74),
    FamilySpec("F11", "目标物A11", "干扰物B11", "visual_marker", "alpha", "visual_position", "lower", "tool_confidence", "checked", "tactile_pressure", 0.51, 0.62, 0.41, 0.42, 0.76),
    FamilySpec("F12", "目标物A12", "干扰物B12", "visual_marker", "beta", "visual_position", "middle", "tool_confidence", "confirmed", "tactile_pressure", 0.54, 0.64, 0.42, 0.44, 0.78),
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


def make_pool(*, store_attribute_state_items: bool = True, runtime_mode: str = "state_item") -> StatePool:
    return StatePool(
        config_override={
            "enable_priority_neutralization": False,
            "insert_attribute_sa_as_state_item": bool(store_attribute_state_items),
            "attribute_binding_runtime_mode": str(runtime_mode),
            "enable_semantic_same_object_merge": False,
            "aggregate_same_semantic_incoming_objects": False,
            "attribute_bind_replace_by_attribute_name": True,
            "allow_auto_create_csa_on_attribute_bind": False,
        }
    )


def feature_sa(sa_id: str, token: str, *, er: float = 2.0, modality: str = "text", source_type: str = "text") -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    return {
        "id": sa_id,
        "object_type": "sa",
        "content": {
            "raw": token,
            "normalized": token,
            "display": token,
            "value_type": "discrete",
        },
        "stimulus": {"role": "feature", "modality": modality},
        "energy": {"er": round(float(er), 8), "ev": 0.0},
        "source": {"parent_ids": []},
        "ext": {"packet_context": {"source_type": source_type, "origin_frame_id": f"frame_{sa_id}"}},
        "created_at": now_ms,
        "updated_at": now_ms,
    }


def attribute_sa(
    sa_id: str,
    *,
    attr_name: str,
    attr_value: str | float,
    parent_id: str,
    modality: str,
    source_type: str,
    er: float = 0.0,
    ev: float = 0.0,
    role: str = "attribute",
    sub_type: str = "grounded_attribute",
) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    is_num = isinstance(attr_value, (int, float))
    raw_value = round(float(attr_value), 8) if is_num else str(attr_value)
    return {
        "id": sa_id,
        "object_type": "sa",
        "sub_type": sub_type,
        "content": {
            "raw": f"{attr_name}:{raw_value}",
            "normalized": f"{attr_name}:{raw_value}",
            "display": f"{attr_name}:{raw_value}",
            "value_type": "numerical" if is_num else "discrete",
            "attribute_name": attr_name,
            "attribute_value": raw_value,
        },
        "stimulus": {"role": role, "modality": modality},
        "energy": {"er": round(float(er), 8), "ev": round(float(ev), 8)},
        "source": {"parent_ids": [parent_id] if parent_id else [], "sensor_name": source_type},
        "ext": {"packet_context": {"source_type": source_type, "origin_frame_id": f"frame_{source_type}_{sa_id}"}},
        "meta": {"ext": {"source_sensor": source_type}},
        "created_at": now_ms,
        "updated_at": now_ms,
    }


def packet_for_objects(packet_id: str, objects: list[dict[str, Any]], *, source_type: str) -> dict[str, Any]:
    total_er = sum(float(obj.get("energy", {}).get("er", 0.0) or 0.0) for obj in objects)
    total_ev = sum(float(obj.get("energy", {}).get("ev", 0.0) or 0.0) for obj in objects)
    return {
        "id": packet_id,
        "object_type": "stimulus_packet",
        "type": "stimulus_packet",
        "sa_items": list(objects),
        "csa_items": [],
        "grouped_sa_sequences": [
            {
                "group_index": 0,
                "source_type": source_type,
                "origin_frame_id": packet_id,
                "sa_ids": [str(obj.get("id", "")) for obj in objects],
                "csa_ids": [],
            }
        ],
        "energy_summary": {
            "total_er": round(total_er, 8),
            "total_ev": round(total_ev, 8),
            "current_total_er": round(total_er, 8),
            "current_total_ev": round(total_ev, 8),
        },
        "trace_id": packet_id,
    }


def insert_base_targets(pool: StatePool, spec: FamilySpec, branch: str) -> dict[str, Any]:
    target_id = f"sa_e16_{spec.family}_target"
    distractor_id = f"sa_e16_{spec.family}_distractor"
    objects = [
        feature_sa(target_id, spec.target_token, er=2.0, modality="text", source_type="text_sensor"),
        feature_sa(distractor_id, spec.distractor_token, er=1.8, modality="text", source_type="text_sensor"),
    ]
    result = pool.apply_stimulus_packet(
        packet_for_objects(f"pkt_e16_{spec.family}_{branch}_base", objects, source_type="text_sensor"),
        trace_id=f"e16_{spec.family}_{branch}_base",
        source_module="e16_experiment",
    )
    target = pool._store.get_by_ref(target_id)
    distractor = pool._store.get_by_ref(distractor_id)
    return {
        "target_ref_id": target_id,
        "distractor_ref_id": distractor_id,
        "target_item_id": str((target or {}).get("id", "")),
        "distractor_item_id": str((distractor or {}).get("id", "")),
        "base_success": bool(result.get("success", False)),
    }


def get_store_item(pool: StatePool, ref_id: str) -> dict[str, Any]:
    item = pool._store.get_by_ref(ref_id)
    return item if isinstance(item, dict) else {}


def packet_attr_map(item: dict[str, Any]) -> dict[str, Any]:
    bs = item.get("binding_state", {}) if isinstance(item.get("binding_state", {}), dict) else {}
    row = bs.get("packet_attribute_by_name", {})
    return row if isinstance(row, dict) else {}


def runtime_attr_map(item: dict[str, Any]) -> dict[str, Any]:
    bs = item.get("binding_state", {}) if isinstance(item.get("binding_state", {}), dict) else {}
    row = bs.get("bound_attribute_by_name", {})
    return row if isinstance(row, dict) else {}


def snapshot_for_ref(pool: StatePool, ref_id: str) -> dict[str, Any]:
    snap = pool.get_state_snapshot(f"snap_{ref_id}", top_k=80).get("data", {}).get("snapshot", {})
    for row in snap.get("top_items", []) or []:
        if str(row.get("ref_object_id", "")) == ref_id:
            return row
    return {}


def attr_item_checks(pool: StatePool, attr_ref_ids: list[str], expected: dict[str, dict[str, Any]]) -> dict[str, Any]:
    present = 0
    modality_ok = 0
    source_ok = 0
    parent_ok = 0
    value_ok = 0
    energy_ok = 0
    signature_parent_ok = 0
    details: dict[str, Any] = {}
    for attr_id in attr_ref_ids:
        item = get_store_item(pool, attr_id)
        exp = expected.get(attr_id, {})
        if item:
            present += 1
        ref_snapshot = item.get("ref_snapshot", {}) if isinstance(item.get("ref_snapshot", {}), dict) else {}
        source = item.get("source", {}) if isinstance(item.get("source", {}), dict) else {}
        ext = item.get("ext", {}) if isinstance(item.get("ext", {}), dict) else {}
        meta_ext = item.get("meta", {}).get("ext", {}) if isinstance(item.get("meta", {}), dict) and isinstance(item.get("meta", {}).get("ext", {}), dict) else {}
        sig = str(item.get("semantic_signature", ""))
        modality = str(exp.get("modality", ""))
        source_type = str(exp.get("source_type", ""))
        parent = str(exp.get("parent_id", ""))
        attr_value = exp.get("value")
        expected_er = float(exp.get("er", 0.0) or 0.0)
        expected_ev = float(exp.get("ev", 0.0) or 0.0)
        incoming_sources = ext.get("incoming_packet_source_types", [])
        if modality and f"|{modality}|" in sig:
            modality_ok += 1
        if source_type and (source_type in incoming_sources or meta_ext.get("source_sensor") == source_type):
            source_ok += 1
        if parent and (source.get("context_ref_object_id") == parent or parent in (source.get("parent_ids", []) or [])):
            parent_ok += 1
        if str(ref_snapshot.get("attribute_value", "")) == str(attr_value):
            value_ok += 1
        energy = item.get("energy", {}) if isinstance(item.get("energy", {}), dict) else {}
        if abs(float(energy.get("er", 0.0) or 0.0) - expected_er) <= 1e-7 and abs(float(energy.get("ev", 0.0) or 0.0) - expected_ev) <= 1e-7:
            energy_ok += 1
        if parent and (parent in sig or str(exp.get("parent_token", "")) in sig):
            signature_parent_ok += 1
        details[attr_id] = {
            "present": bool(item),
            "semantic_signature": sig,
            "source": source,
            "incoming_packet_source_types": incoming_sources,
            "meta_ext": meta_ext,
            "ref_snapshot": ref_snapshot,
            "energy": energy,
        }
    n = max(1, len(attr_ref_ids))
    return {
        "attr_item_present_ratio": round(present / n, 8),
        "attr_item_modality_ok_ratio": round(modality_ok / n, 8),
        "attr_item_source_ok_ratio": round(source_ok / n, 8),
        "attr_item_parent_ok_ratio": round(parent_ok / n, 8),
        "attr_item_value_ok_ratio": round(value_ok / n, 8),
        "attr_item_energy_ok_ratio": round(energy_ok / n, 8),
        "attr_item_signature_parent_ok_ratio": round(signature_parent_ok / n, 8),
        "attr_item_details": details,
    }


def packet_expected_attrs(spec: FamilySpec, target_ref_id: str, wrong: bool = False) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    parent = f"sa_e16_{spec.family}_distractor" if wrong else target_ref_id
    attrs = [
        attribute_sa(
            f"sa_e16_{spec.family}_packet_visual_primary",
            attr_name=spec.visual_attr_name,
            attr_value=spec.visual_attr_value,
            parent_id=parent,
            modality="vision",
            source_type="vision_sensor",
            er=spec.visual_er,
            ev=0.0,
            sub_type="visual_attribute",
        ),
        attribute_sa(
            f"sa_e16_{spec.family}_packet_visual_spatial",
            attr_name=spec.spatial_attr_name,
            attr_value=spec.spatial_attr_value,
            parent_id=parent,
            modality="vision",
            source_type="vision_sensor",
            er=spec.spatial_er,
            ev=0.0,
            sub_type="visual_attribute",
        ),
        attribute_sa(
            f"sa_e16_{spec.family}_packet_tactile_pressure",
            attr_name=spec.tactile_attr_name,
            attr_value=spec.tactile_attr_value,
            parent_id=parent,
            modality="tactile",
            source_type="tactile_sensor",
            er=spec.tactile_er,
            ev=0.0,
            sub_type="tactile_attribute",
        ),
    ]
    expected = {
        str(attr["id"]): {
            "modality": str(attr.get("stimulus", {}).get("modality", "")),
            "source_type": str(attr.get("ext", {}).get("packet_context", {}).get("source_type", "")),
            "parent_id": parent,
            "parent_token": spec.distractor_token if wrong else spec.target_token,
            "value": attr.get("content", {}).get("attribute_value"),
            "er": attr.get("energy", {}).get("er", 0.0),
            "ev": attr.get("energy", {}).get("ev", 0.0),
        }
        for attr in attrs
    }
    return attrs, expected


def packet_branch(pool: StatePool, spec: FamilySpec, branch: str) -> dict[str, Any]:
    base = insert_base_targets(pool, spec, branch)
    wrong = branch == "packet_wrong_anchor_control"
    attrs, expected = packet_expected_attrs(spec, base["target_ref_id"], wrong=wrong)
    result = pool.apply_stimulus_packet(
        packet_for_objects(f"pkt_e16_{spec.family}_{branch}_attrs", attrs, source_type="multi_source_attributes"),
        trace_id=f"e16_{spec.family}_{branch}_attrs",
        source_module="e16_experiment",
    )
    target = get_store_item(pool, base["target_ref_id"])
    distractor = get_store_item(pool, base["distractor_ref_id"])
    target_packet = packet_attr_map(target)
    distractor_packet = packet_attr_map(distractor)
    expected_names = {spec.visual_attr_name, spec.spatial_attr_name, spec.tactile_attr_name}
    target_names = set(target_packet)
    distractor_names = set(distractor_packet)
    attr_ids = [str(attr["id"]) for attr in attrs]
    checks = attr_item_checks(pool, attr_ids, expected) if branch != "packet_attribute_folded_control" else {
        "attr_item_present_ratio": 0.0,
        "attr_item_modality_ok_ratio": 0.0,
        "attr_item_source_ok_ratio": 0.0,
        "attr_item_parent_ok_ratio": 0.0,
        "attr_item_value_ok_ratio": 0.0,
        "attr_item_energy_ok_ratio": 0.0,
        "attr_item_signature_parent_ok_ratio": 0.0,
        "attr_item_details": {},
    }
    target_snap = snapshot_for_ref(pool, base["target_ref_id"])
    distractor_snap = snapshot_for_ref(pool, base["distractor_ref_id"])
    if branch == "packet_multimodal_bound":
        packet_anchor_ok = expected_names.issubset(target_names) and not expected_names.intersection(distractor_names)
        attr_items_expected_ok = all(float(checks.get(key, 0.0)) >= 1.0 for key in [
            "attr_item_present_ratio",
            "attr_item_modality_ok_ratio",
            "attr_item_source_ok_ratio",
            "attr_item_parent_ok_ratio",
            "attr_item_value_ok_ratio",
            "attr_item_energy_ok_ratio",
            "attr_item_signature_parent_ok_ratio",
        ])
        case_ok = bool(result.get("success", False)) and packet_anchor_ok and attr_items_expected_ok
    elif branch == "packet_wrong_anchor_control":
        packet_anchor_ok = expected_names.issubset(distractor_names) and not expected_names.intersection(target_names)
        attr_items_expected_ok = all(float(checks.get(key, 0.0)) >= 1.0 for key in [
            "attr_item_present_ratio",
            "attr_item_modality_ok_ratio",
            "attr_item_source_ok_ratio",
            "attr_item_parent_ok_ratio",
            "attr_item_value_ok_ratio",
            "attr_item_energy_ok_ratio",
            "attr_item_signature_parent_ok_ratio",
        ])
        case_ok = bool(result.get("success", False)) and packet_anchor_ok and attr_items_expected_ok
    else:
        packet_anchor_ok = expected_names.issubset(target_names) and not expected_names.intersection(distractor_names)
        folded_ok = all(get_store_item(pool, attr_id) == {} for attr_id in attr_ids)
        case_ok = bool(result.get("success", False)) and packet_anchor_ok and folded_ok
    return {
        **base,
        "family": spec.family,
        "branch": branch,
        "branch_label": BRANCH_LABELS[branch],
        "apply_success": int(bool(result.get("success", False))),
        "case_ok": int(bool(case_ok)),
        "target_packet_attr_names": "|".join(sorted(target_names)),
        "distractor_packet_attr_names": "|".join(sorted(distractor_names)),
        "expected_packet_attr_names": "|".join(sorted(expected_names)),
        "packet_anchor_ok": int(bool(packet_anchor_ok)),
        "target_pollution_quiet": int(not bool(expected_names.intersection(target_names)) if wrong else not bool(expected_names.intersection(distractor_names))),
        "folded_control_attr_items_absent": int(branch == "packet_attribute_folded_control" and all(get_store_item(pool, attr_id) == {} for attr_id in attr_ids)),
        "target_snapshot_all_attrs": "|".join(target_snap.get("all_attribute_names", []) or []),
        "distractor_snapshot_all_attrs": "|".join(distractor_snap.get("all_attribute_names", []) or []),
        **{key: value for key, value in checks.items() if key != "attr_item_details"},
        "attr_item_ids": "|".join(attr_ids),
        "whitebox": {
            "target_store": target,
            "distractor_store": distractor,
            "target_snapshot": target_snap,
            "distractor_snapshot": distractor_snap,
            "attr_item_checks": checks,
            "apply_result": result,
        },
    }


def runtime_branch(pool: StatePool, spec: FamilySpec, branch: str) -> dict[str, Any]:
    base = insert_base_targets(pool, spec, branch)
    if branch == "runtime_tool_binding":
        target_item_id = base["target_item_id"]
        parent_ref_id = base["target_ref_id"]
        expected_target_ref = base["target_ref_id"]
        expected_quiet_ref = base["distractor_ref_id"]
        role = "attribute"
    elif branch == "runtime_wrong_target_control":
        target_item_id = base["distractor_item_id"]
        parent_ref_id = base["distractor_ref_id"]
        expected_target_ref = base["distractor_ref_id"]
        expected_quiet_ref = base["target_ref_id"]
        role = "attribute"
    else:
        target_item_id = base["target_item_id"]
        parent_ref_id = base["target_ref_id"]
        expected_target_ref = base["target_ref_id"]
        expected_quiet_ref = base["distractor_ref_id"]
        role = "feature"
    attr_id = f"sa_e16_{spec.family}_{branch}_tool_attr"
    attr = attribute_sa(
        attr_id,
        attr_name=spec.tool_attr_name,
        attr_value=spec.tool_attr_value,
        parent_id=parent_ref_id,
        modality="tool",
        source_type="tool_feedback",
        er=0.0,
        ev=spec.tool_ev,
        role=role,
        sub_type="tool_feedback_attribute",
    )
    result = pool.bind_attribute_node_to_object(
        target_item_id=target_item_id,
        attribute_sa=attr,
        trace_id=f"e16_{spec.family}_{branch}_runtime_bind",
        tick_id=f"tick_e16_{spec.family}_{branch}",
        source_module="e16_experiment",
        reason=f"e16_{branch}",
    )
    target = get_store_item(pool, base["target_ref_id"])
    distractor = get_store_item(pool, base["distractor_ref_id"])
    expected_item = get_store_item(pool, expected_target_ref)
    quiet_item = get_store_item(pool, expected_quiet_ref)
    expected_runtime = runtime_attr_map(expected_item)
    quiet_runtime = runtime_attr_map(quiet_item)
    attr_item = get_store_item(pool, attr_id)
    attr_expected = {
        attr_id: {
            "modality": "tool",
            "source_type": "tool_feedback",
            "parent_id": parent_ref_id,
            "parent_token": spec.distractor_token if branch == "runtime_wrong_target_control" else spec.target_token,
            "value": spec.tool_attr_value,
            "er": 0.0,
            "ev": spec.tool_ev,
        }
    }
    checks = attr_item_checks(pool, [attr_id], attr_expected) if branch != "runtime_invalid_role_control" else {
        "attr_item_present_ratio": 0.0,
        "attr_item_modality_ok_ratio": 0.0,
        "attr_item_source_ok_ratio": 0.0,
        "attr_item_parent_ok_ratio": 0.0,
        "attr_item_value_ok_ratio": 0.0,
        "attr_item_energy_ok_ratio": 0.0,
        "attr_item_signature_parent_ok_ratio": 0.0,
        "attr_item_details": {},
    }
    target_snap = snapshot_for_ref(pool, base["target_ref_id"])
    distractor_snap = snapshot_for_ref(pool, base["distractor_ref_id"])
    if branch == "runtime_invalid_role_control":
        runtime_bind_ok = not bool(result.get("success", False)) and not expected_runtime and not quiet_runtime and not attr_item
        case_ok = runtime_bind_ok
    else:
        runtime_bind_ok = (
            bool(result.get("success", False))
            and spec.tool_attr_name in expected_runtime
            and spec.tool_attr_name not in quiet_runtime
            and bool(attr_item)
            and all(float(checks.get(key, 0.0)) >= 1.0 for key in [
                "attr_item_present_ratio",
                "attr_item_modality_ok_ratio",
                "attr_item_source_ok_ratio",
                "attr_item_parent_ok_ratio",
                "attr_item_value_ok_ratio",
                "attr_item_energy_ok_ratio",
                "attr_item_signature_parent_ok_ratio",
            ])
        )
        case_ok = runtime_bind_ok
    return {
        **base,
        "family": spec.family,
        "branch": branch,
        "branch_label": BRANCH_LABELS[branch],
        "bind_success": int(bool(result.get("success", False))),
        "bind_code": str(result.get("code", "")),
        "case_ok": int(bool(case_ok)),
        "runtime_bind_ok": int(bool(runtime_bind_ok)),
        "expected_runtime_attr_names": "|".join(sorted(expected_runtime)),
        "quiet_runtime_attr_names": "|".join(sorted(quiet_runtime)),
        "target_runtime_attr_names": "|".join(sorted(runtime_attr_map(target))),
        "distractor_runtime_attr_names": "|".join(sorted(runtime_attr_map(distractor))),
        "runtime_quiet_ok": int(spec.tool_attr_name not in quiet_runtime),
        "invalid_role_rejected": int(branch == "runtime_invalid_role_control" and not bool(result.get("success", False))),
        "target_snapshot_all_attrs": "|".join(target_snap.get("all_attribute_names", []) or []),
        "distractor_snapshot_all_attrs": "|".join(distractor_snap.get("all_attribute_names", []) or []),
        **{key: value for key, value in checks.items() if key != "attr_item_details"},
        "attr_item_ids": attr_id,
        "whitebox": {
            "target_store": target,
            "distractor_store": distractor,
            "expected_store": expected_item,
            "quiet_store": quiet_item,
            "target_snapshot": target_snap,
            "distractor_snapshot": distractor_snap,
            "attr_item": attr_item,
            "attr_item_checks": checks,
            "bind_result": result,
        },
    }


def run_case(spec: FamilySpec, branch: str) -> dict[str, Any]:
    if branch == "packet_attribute_folded_control":
        pool = make_pool(store_attribute_state_items=False, runtime_mode="legacy_bind")
        return packet_branch(pool, spec, branch)
    pool = make_pool(store_attribute_state_items=True, runtime_mode="state_item")
    if branch.startswith("packet_"):
        return packet_branch(pool, spec, branch)
    return runtime_branch(pool, spec, branch)


def build_family_rows(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_family: dict[str, dict[str, dict[str, Any]]] = {}
    for row in case_rows:
        by_family.setdefault(str(row["family"]), {})[str(row["branch"])] = row
    for family in sorted(by_family):
        branches = by_family[family]
        row: dict[str, Any] = {"family": family}
        for branch in BRANCH_ORDER:
            row[f"{branch}_case_ok"] = int(branches.get(branch, {}).get("case_ok", 0) or 0)
        row["packet_multimodal_pass"] = int(branches.get("packet_multimodal_bound", {}).get("case_ok", 0) or 0)
        row["packet_wrong_anchor_pass"] = int(branches.get("packet_wrong_anchor_control", {}).get("case_ok", 0) or 0)
        row["packet_folded_control_pass"] = int(branches.get("packet_attribute_folded_control", {}).get("case_ok", 0) or 0)
        row["runtime_tool_binding_pass"] = int(branches.get("runtime_tool_binding", {}).get("case_ok", 0) or 0)
        row["runtime_wrong_target_pass"] = int(branches.get("runtime_wrong_target_control", {}).get("case_ok", 0) or 0)
        row["runtime_invalid_role_pass"] = int(branches.get("runtime_invalid_role_control", {}).get("case_ok", 0) or 0)
        row["all_ok"] = int(all(int(row[f"{branch}_case_ok"]) == 1 for branch in BRANCH_ORDER))
        row["packet_attr_item_present_ratio"] = float(branches.get("packet_multimodal_bound", {}).get("attr_item_present_ratio", 0.0) or 0.0)
        row["packet_attr_modality_ok_ratio"] = float(branches.get("packet_multimodal_bound", {}).get("attr_item_modality_ok_ratio", 0.0) or 0.0)
        row["packet_attr_source_ok_ratio"] = float(branches.get("packet_multimodal_bound", {}).get("attr_item_source_ok_ratio", 0.0) or 0.0)
        row["runtime_attr_modality_ok_ratio"] = float(branches.get("runtime_tool_binding", {}).get("attr_item_modality_ok_ratio", 0.0) or 0.0)
        row["runtime_attr_source_ok_ratio"] = float(branches.get("runtime_tool_binding", {}).get("attr_item_source_ok_ratio", 0.0) or 0.0)
        rows.append(row)
    return rows


def summarize(case_rows: list[dict[str, Any]], family_rows: list[dict[str, Any]]) -> dict[str, Any]:
    family_count = len(family_rows)
    all_ok = sum(int(row.get("all_ok", 0) or 0) for row in family_rows)
    summary: dict[str, Any] = {
        "experiment_id": "E16",
        "family_count": family_count,
        "case_count": len(case_rows),
        "all_ok_family_count": all_ok,
        "all_ok_ratio": round(all_ok / max(1, family_count), 8),
        "all_ok_sign_p": sign_test_p_value(all_ok, family_count - all_ok),
        "case_ok_ratio": round(sum(int(row.get("case_ok", 0) or 0) for row in case_rows) / max(1, len(case_rows)), 8),
    }
    for key in [
        "packet_multimodal_pass",
        "packet_wrong_anchor_pass",
        "packet_folded_control_pass",
        "runtime_tool_binding_pass",
        "runtime_wrong_target_pass",
        "runtime_invalid_role_pass",
    ]:
        summary[f"{key}_ratio"] = round(sum(int(row.get(key, 0) or 0) for row in family_rows) / max(1, family_count), 8)
    for key in [
        "packet_attr_item_present_ratio",
        "packet_attr_modality_ok_ratio",
        "packet_attr_source_ok_ratio",
        "runtime_attr_modality_ok_ratio",
        "runtime_attr_source_ok_ratio",
    ]:
        summary[f"{key}_mean"] = mean_or_zero([float(row.get(key, 0.0) or 0.0) for row in family_rows])
    summary["support_level"] = (
        "strong_evidence"
        if family_count >= 12
        and summary["all_ok_ratio"] >= 1.0
        and summary["case_ok_ratio"] >= 1.0
        and summary["all_ok_sign_p"] <= 0.001
        else "insufficient"
    )
    return summary


def make_charts(case_rows: list[dict[str, Any]], family_rows: list[dict[str, Any]], summary: dict[str, Any], stamp: str) -> list[Path]:
    plt = e01.setup_matplotlib()
    charts: list[Path] = []

    pass_path = CHART_DIR / f"e16_branch_pass_rates_{stamp}.png"
    fig, ax = plt.subplots(figsize=(11.2, 5.4), dpi=160)
    labels = ["packet绑定", "错锚对照", "折叠对照", "runtime绑定", "错目标对照", "非法角色"]
    keys = [
        "packet_multimodal_pass_ratio",
        "packet_wrong_anchor_pass_ratio",
        "packet_folded_control_pass_ratio",
        "runtime_tool_binding_pass_ratio",
        "runtime_wrong_target_pass_ratio",
        "runtime_invalid_role_pass_ratio",
    ]
    values = [float(summary.get(key, 0.0)) for key in keys]
    ax.bar(labels, values, color=["#2563eb", "#7c3aed", "#64748b", "#0891b2", "#f59e0b", "#94a3b8"], alpha=0.86)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("family 级通过比例")
    ax.set_title("E16 多来源属性接地入口的分支通过比例")
    ax.grid(axis="y", alpha=0.22)
    for idx, val in enumerate(values):
        ax.text(idx, val + 0.025, f"{val:.3f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(pass_path)
    plt.close(fig)
    charts.append(pass_path)

    matrix_path = CHART_DIR / f"e16_family_pass_matrix_{stamp}.png"
    fig, ax = plt.subplots(figsize=(11.4, 5.2), dpi=160)
    fields = [f"{branch}_case_ok" for branch in BRANCH_ORDER]
    matrix = [[int(row.get(field, 0) or 0) for field in fields] for row in family_rows]
    ax.imshow(matrix, vmin=0, vmax=1, cmap="YlGnBu", aspect="auto")
    ax.set_yticks(list(range(len(family_rows))))
    ax.set_yticklabels([row["family"] for row in family_rows])
    ax.set_xticks(list(range(len(fields))))
    ax.set_xticklabels(["packet", "错锚", "折叠", "runtime", "错目标", "拒绝"], rotation=25, ha="right")
    ax.set_title("E16 family 级强证据判据矩阵")
    for y, row in enumerate(matrix):
        for x, val in enumerate(row):
            ax.text(x, y, "1" if val else "0", ha="center", va="center", fontsize=8, color="#0f172a")
    fig.tight_layout()
    fig.savefig(matrix_path)
    plt.close(fig)
    charts.append(matrix_path)

    integrity_path = CHART_DIR / f"e16_attribute_integrity_{stamp}.png"
    fig, ax = plt.subplots(figsize=(10.8, 5.4), dpi=160)
    labels = ["packet入池", "packet模态", "packet来源", "runtime模态", "runtime来源"]
    values = [
        float(summary.get("packet_attr_item_present_ratio_mean", 0.0)),
        float(summary.get("packet_attr_modality_ok_ratio_mean", 0.0)),
        float(summary.get("packet_attr_source_ok_ratio_mean", 0.0)),
        float(summary.get("runtime_attr_modality_ok_ratio_mean", 0.0)),
        float(summary.get("runtime_attr_source_ok_ratio_mean", 0.0)),
    ]
    ax.bar(labels, values, color=["#2563eb", "#0d9488", "#16a34a", "#0891b2", "#65a30d"], alpha=0.86)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("属性完整性比例")
    ax.set_title("E16 属性对象的入池、模态与来源保真")
    ax.grid(axis="y", alpha=0.22)
    for idx, val in enumerate(values):
        ax.text(idx, val + 0.025, f"{val:.3f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(integrity_path)
    plt.close(fig)
    charts.append(integrity_path)

    anchor_path = CHART_DIR / f"e16_anchor_isolation_{stamp}.png"
    fig, ax = plt.subplots(figsize=(11.2, 5.4), dpi=160)
    branch_rows = [row for row in case_rows if row.get("family") == "F01"]
    labels = [BRANCH_LABELS[str(row["branch"])] for row in branch_rows]
    target_pollution = [int(row.get("target_pollution_quiet", row.get("runtime_quiet_ok", 0)) or 0) for row in branch_rows]
    case_ok = [int(row.get("case_ok", 0) or 0) for row in branch_rows]
    x = list(range(len(branch_rows)))
    ax.bar([i - 0.18 for i in x], case_ok, width=0.34, label="分支判据", color="#2563eb", alpha=0.82)
    ax.bar([i + 0.18 for i in x], target_pollution, width=0.34, label="非目标静默", color="#f59e0b", alpha=0.82)
    ax.set_ylim(0, 1.12)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("通过=1")
    ax.set_title("E16 F01 锚点隔离与非目标静默样例")
    ax.legend()
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    fig.savefig(anchor_path)
    plt.close(fig)
    charts.append(anchor_path)
    return charts


def write_design_note(path: Path) -> None:
    lines = [
        "# E16 多模态/符号接地入口实验设计说明",
        "",
        "## 最小可证明命题",
        "",
        "本实验验证当前 AP 原型中的多来源属性化接地入口：非文本来源的属性信号可以以属性刺激元进入状态池，保留 modality、source、attribute_name、attribute_value 与锚点关系；同一属性既可以来自 stimulus_packet，也可以通过运行态属性绑定进入目标对象；错误锚点或非法角色不会污染目标对象。",
        "",
        "## 因果设计",
        "",
        "- 每个 family 同时创建一个目标对象和一个干扰对象。",
        "- packet 分支只改变属性刺激元的 parent_ids 与是否将属性 SA 作为 state_item 存储。",
        "- runtime 分支只改变 bind_attribute_node_to_object 的目标对象或属性 SA 的 role。",
        "- 判据要求属性对象、目标对象快照、运行态绑定映射和错误目标静默同时成立。",
        "",
        "## 边界",
        "",
        "本实验不证明低层视觉、触觉或工具理解算法已经完成，只证明当前 AP 原型具有把不同来源信号接入统一刺激元和状态池体系的白箱入口，并能维持来源、模态、强度和锚点的可审计结构。",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    *,
    family_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    charts: list[Path],
    stamp: str,
) -> Path:
    lines = [
        "# E16 多模态/符号接地入口实验报告",
        "",
        "## 结论摘要",
        "",
        f"- 支持等级：**{summary.get('support_level', 'unknown')}**",
        f"- family 数：{int(summary.get('family_count', 0))}",
        f"- case 数：{int(summary.get('case_count', 0))}",
        f"- family 级整体通过比例：{summary.get('all_ok_ratio', 0.0):.3f}",
        f"- case 级通过比例：{summary.get('case_ok_ratio', 0.0):.3f}",
        f"- family 级符号检验 p 值：{summary.get('all_ok_sign_p', 1.0):.8f}",
        "",
        "## 正文可使用的最小命题",
        "",
        "当前 AP 原型已经提供多来源属性化接地入口。属性刺激元可以来自 vision/tactile/tool 等非文本来源，进入同一状态池；锚点对象能够获得 packet 属性或 runtime 绑定属性的可复查视图；错误锚点和非法角色对照保持静默。该结论不扩写为完整视觉理解能力。",
        "",
        "## family 判据矩阵",
        "",
        "| family | packet绑定 | 错锚对照 | 折叠对照 | runtime绑定 | 错目标对照 | 非法角色 | 全部通过 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in family_rows:
        lines.append(
            f"| {row['family']} | {int(row['packet_multimodal_pass'])} | {int(row['packet_wrong_anchor_pass'])} | "
            f"{int(row['packet_folded_control_pass'])} | {int(row['runtime_tool_binding_pass'])} | "
            f"{int(row['runtime_wrong_target_pass'])} | {int(row['runtime_invalid_role_pass'])} | {int(row['all_ok'])} |"
        )
    lines.extend(["", "## 图表", ""])
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    report = REPORT_DIR / f"E16_multimodal_symbol_grounding_report_{stamp}.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def run_experiment(*, stamp: str, family_count: int) -> dict[str, Any]:
    ensure_dirs()
    specs = FAMILY_SPECS[: max(1, min(int(family_count), len(FAMILY_SPECS)))]
    case_rows: list[dict[str, Any]] = []
    whitebox: dict[str, Any] = {}
    for spec in specs:
        for branch in BRANCH_ORDER:
            row = run_case(spec, branch)
            wb = row.pop("whitebox", {})
            case_rows.append(row)
            if spec.family == "F01":
                whitebox[branch] = wb
    case_rows.sort(key=lambda row: (str(row["family"]), BRANCH_ORDER.index(str(row["branch"]))))
    family_rows = build_family_rows(case_rows)
    summary = summarize(case_rows, family_rows)
    summary["stamp"] = stamp
    charts = make_charts(case_rows=case_rows, family_rows=family_rows, summary=summary, stamp=stamp)
    design_note = REPORT_DIR / "E16_multimodal_symbol_grounding_design_logic.md"
    write_design_note(design_note)
    report = write_report(family_rows=family_rows, summary=summary, charts=charts, stamp=stamp)

    case_csv = TABLE_DIR / f"e16_multimodal_symbol_grounding_case_rows_{stamp}.csv"
    family_csv = TABLE_DIR / f"e16_multimodal_symbol_grounding_family_rows_{stamp}.csv"
    summary_json = TABLE_DIR / f"e16_multimodal_symbol_grounding_summary_{stamp}.json"
    whitebox_json = TABLE_DIR / f"e16_multimodal_symbol_grounding_whitebox_{stamp}.json"
    e01.write_csv(case_csv, case_rows)
    e01.write_csv(family_csv, family_rows)
    e01.write_json(summary_json, summary)
    e01.write_json(whitebox_json, whitebox)
    evidence = {
        "experiment_id": "E16",
        "stamp": stamp,
        "support_level": summary.get("support_level", "unknown"),
        "summary": summary,
        "artifacts": {
            "case_rows": str(case_csv),
            "family_rows": str(family_csv),
            "summary": str(summary_json),
            "whitebox": str(whitebox_json),
            "report": str(report),
            "design_note": str(design_note),
            "charts": [str(path) for path in charts],
        },
    }
    e01.write_json(MANIFEST_DIR / f"E16_multimodal_symbol_grounding_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E16_multimodal_symbol_grounding_latest.json", evidence)
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AP paper E16 multimodal/symbol grounding entrance experiment.")
    parser.add_argument("--stamp", default=STAMP_DEFAULT)
    parser.add_argument("--family-count", type=int, default=12)
    args = parser.parse_args()
    evidence = run_experiment(stamp=args.stamp, family_count=args.family_count)
    print(
        json.dumps(
            {
                "stamp": args.stamp,
                "support": evidence["support_level"],
                "report": evidence["artifacts"]["report"],
                "summary": evidence["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
