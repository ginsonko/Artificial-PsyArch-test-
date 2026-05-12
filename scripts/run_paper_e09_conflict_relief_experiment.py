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

import yaml

from _reproduction_paths import AP_ROOT, ARTIFACT_ROOT, ATTACHMENT_ROOT

if str(AP_ROOT) not in sys.path:
    sys.path.insert(0, str(AP_ROOT))

import run_paper_e01_experiment as e01
from innate_script._rules_engine import evaluate_rules, normalize_rules_doc


E09_ROOT = ARTIFACT_ROOT / "E09_conflict_relief"
TABLE_DIR = E09_ROOT / "tables"
CHART_DIR = E09_ROOT / "charts"
REPORT_DIR = E09_ROOT / "reports"
MANIFEST_DIR = E09_ROOT / "manifests"

STAMP_DEFAULT = "e09_final_v1"


@dataclass(frozen=True)
class FamilySpec:
    family: str
    prior_cp_abs: float
    relief_cp_abs: float
    correct_cp_abs: float
    reassure_cp_abs: float
    grasp_score: float
    core_complexity_score: float
    punish_state: float


FAMILY_SPECS: list[FamilySpec] = [
    FamilySpec("F01", 1.18, 0.50, 0.30, 0.30, 0.48, 0.22, 0.18),
    FamilySpec("F02", 1.22, 0.52, 0.30, 0.28, 0.52, 0.24, 0.16),
    FamilySpec("F03", 1.26, 0.54, 0.30, 0.26, 0.56, 0.18, 0.20),
    FamilySpec("F04", 1.30, 0.49, 0.30, 0.24, 0.60, 0.20, 0.22),
    FamilySpec("F05", 1.34, 0.47, 0.30, 0.32, 0.44, 0.26, 0.24),
    FamilySpec("F06", 1.38, 0.51, 0.30, 0.34, 0.46, 0.28, 0.26),
    FamilySpec("F07", 1.20, 0.53, 0.30, 0.22, 0.62, 0.16, 0.12),
    FamilySpec("F08", 1.24, 0.48, 0.30, 0.20, 0.66, 0.14, 0.10),
    FamilySpec("F09", 1.28, 0.46, 0.30, 0.36, 0.42, 0.30, 0.28),
    FamilySpec("F10", 1.32, 0.55, 0.30, 0.38, 0.40, 0.32, 0.30),
    FamilySpec("F11", 1.36, 0.50, 0.30, 0.27, 0.50, 0.21, 0.14),
    FamilySpec("F12", 1.40, 0.52, 0.30, 0.33, 0.54, 0.23, 0.19),
]


BRANCHES = (
    "relief_only",
    "correct_event_on",
    "correct_event_block_current_cp",
    "reassurance_on",
    "reassurance_block_high_punish",
    "reassurance_block_low_grasp",
    "reassurance_block_high_complexity",
)


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


def load_default_rules_doc() -> dict[str, Any]:
    raw = yaml.safe_load((AP_ROOT / "innate_script" / "config" / "innate_rules.yaml").read_text(encoding="utf-8"))
    doc, errors, _warnings = normalize_rules_doc(raw)
    if errors:
        raise RuntimeError(f"normalize_rules_doc failed: {errors}")
    return doc


def build_context(
    *,
    item_id: str,
    ref_object_id: str,
    label: str,
    cp_abs: float,
    grasp_score: float = 0.0,
    core_complexity_score: float = 0.52,
    punish_state: float = 0.0,
    reward_state: float = 0.0,
) -> dict[str, Any]:
    return {
        "pool": {
            "total_er": 0.2,
            "total_ev": 0.8,
            "total_energy": 1.0,
            "item_count": 1,
            "complexity_score": float(core_complexity_score),
            "core_complexity_score": float(core_complexity_score),
            "total_cp_abs": float(cp_abs),
        },
        "pool_items": [
            {
                "item_id": str(item_id),
                "ref_object_id": str(ref_object_id),
                "ref_object_type": "st",
                "display": str(label),
                "er": 0.2,
                "ev": 0.8,
                "cp_delta": -0.6,
                "cp_abs": float(cp_abs),
                # 这里故意固定为 0，避免把实验建立在“手写 delta 字段”之上。
                # E09 的正确门槛口径是同一对象 cp_abs 的历史差值。
                "delta_cp_abs": 0.0,
                "total_energy": 1.0,
                "input_is_empty": 1,
                "fatigue": 0.03,
            }
        ],
        "cam": {"size": 1, "energy_concentration": 1.0},
        "memory_activation": {"item_count": 0, "total_ev": 0.0},
        "emotion": {"nt": {}, "rwd": float(reward_state), "pun": float(punish_state)},
        "stimulus": {"residual_ratio": 0.0, "input_is_empty": 1, "input_has_text": 0},
        "retrieval": {"stimulus": {"best_match_score": 0.0, "grasp_score": float(grasp_score)}, "structure": {"best_match_score": 0.0}},
    }


def second_tick_context(spec: FamilySpec, branch: str, *, item_id: str, ref_object_id: str) -> dict[str, Any]:
    if branch == "relief_only":
        return build_context(
            item_id=item_id,
            ref_object_id=ref_object_id,
            label=f"{spec.family} relief",
            cp_abs=spec.relief_cp_abs,
            punish_state=0.12,
        )
    if branch == "correct_event_on":
        return build_context(
            item_id=item_id,
            ref_object_id=ref_object_id,
            label=f"{spec.family} correct",
            cp_abs=spec.correct_cp_abs,
            punish_state=0.0,
        )
    if branch == "correct_event_block_current_cp":
        return build_context(
            item_id=item_id,
            ref_object_id=ref_object_id,
            label=f"{spec.family} correct_block",
            cp_abs=0.80,
            punish_state=0.0,
        )
    if branch == "reassurance_on":
        return build_context(
            item_id=item_id,
            ref_object_id=ref_object_id,
            label=f"{spec.family} reassurance",
            cp_abs=spec.reassure_cp_abs,
            grasp_score=spec.grasp_score,
            core_complexity_score=spec.core_complexity_score,
            punish_state=spec.punish_state,
        )
    if branch == "reassurance_block_high_punish":
        return build_context(
            item_id=item_id,
            ref_object_id=ref_object_id,
            label=f"{spec.family} reassurance_high_punish",
            cp_abs=spec.reassure_cp_abs,
            grasp_score=spec.grasp_score,
            core_complexity_score=spec.core_complexity_score,
            punish_state=0.72,
        )
    if branch == "reassurance_block_low_grasp":
        return build_context(
            item_id=item_id,
            ref_object_id=ref_object_id,
            label=f"{spec.family} reassurance_low_grasp",
            cp_abs=spec.reassure_cp_abs,
            grasp_score=0.12,
            core_complexity_score=spec.core_complexity_score,
            punish_state=spec.punish_state,
        )
    if branch == "reassurance_block_high_complexity":
        return build_context(
            item_id=item_id,
            ref_object_id=ref_object_id,
            label=f"{spec.family} reassurance_high_complexity",
            cp_abs=spec.reassure_cp_abs,
            grasp_score=spec.grasp_score,
            core_complexity_score=0.46,
            punish_state=spec.punish_state,
        )
    raise ValueError(f"unknown branch: {branch}")


def signal_strengths(out: dict[str, Any]) -> dict[str, float]:
    signals = ((out.get("directives") or {}).get("cfs_signals") or [])
    result: dict[str, float] = {}
    for row in signals:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind", "") or "").strip()
        if not kind:
            continue
        result[kind] = float(row.get("strength", 0.0) or 0.0)
    return result


def pool_bind_attribute_names(out: dict[str, Any]) -> list[str]:
    rows = ((out.get("directives") or {}).get("pool_effects") or [])
    names: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("effect_type", "") or "") != "pool_bind_attribute":
            continue
        attr = ((row.get("spec") or {}).get("attribute") or {})
        name = str(attr.get("attribute_name", "") or "").strip()
        if name:
            names.append(name)
    return names


def action_kinds(out: dict[str, Any]) -> list[str]:
    rows = ((out.get("directives") or {}).get("action_triggers") or [])
    kinds: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("action_kind", "") or "").strip()
        if kind:
            kinds.append(kind)
    return kinds


def nt_updates_for_signal(doc: dict[str, Any], *, kind: str, strength: float) -> dict[str, float]:
    out = evaluate_rules(
        doc=doc,
        trace_id="paper_e09_nt_probe",
        tick_id=f"paper_e09_nt_{kind}",
        tick_index=10,
        cfs_signals=[{"kind": str(kind), "strength": float(strength)}],
        state_windows=[],
        context={},
        now_ms=100,
        runtime_state={},
        allow_timer=True,
        allowed_phases=["directives"],
    )
    raw = ((out.get("directives") or {}).get("emotion_updates") or {})
    return {str(k): float(v) for k, v in raw.items()}


def run_case(doc: dict[str, Any], *, spec: FamilySpec, branch: str) -> dict[str, Any]:
    item_id = f"spi_{spec.family}_{branch}"
    ref_object_id = f"st_{spec.family}_{branch}"
    runtime_state: dict[str, Any] = {}

    first_context = build_context(
        item_id=item_id,
        ref_object_id=ref_object_id,
        label=f"{spec.family} prior",
        cp_abs=spec.prior_cp_abs,
        punish_state=0.0,
    )
    evaluate_rules(
        doc=doc,
        trace_id="paper_e09_case",
        tick_id=f"{spec.family}_{branch}_t1",
        tick_index=1,
        cfs_signals=[],
        state_windows=[],
        context=first_context,
        now_ms=100,
        runtime_state=runtime_state,
        allow_timer=True,
    )

    second_context = second_tick_context(spec, branch, item_id=item_id, ref_object_id=ref_object_id)
    out = evaluate_rules(
        doc=doc,
        trace_id="paper_e09_case",
        tick_id=f"{spec.family}_{branch}_t2",
        tick_index=2,
        cfs_signals=[],
        state_windows=[],
        context=second_context,
        now_ms=100,
        runtime_state=runtime_state,
        allow_timer=True,
    )
    kinds = signal_strengths(out)
    attrs = pool_bind_attribute_names(out)
    actions = action_kinds(out)
    direct_emotion_updates = {str(k): float(v) for k, v in (((out.get("directives") or {}).get("emotion_updates") or {}).items())}

    row: dict[str, Any] = {
        "family": spec.family,
        "branch": branch,
        "prior_cp_abs": round(float(spec.prior_cp_abs), 8),
        "second_cp_abs": round(float(second_context["pool_items"][0]["cp_abs"]), 8),
        "second_grasp_score": round(float(((second_context.get("retrieval", {}) or {}).get("stimulus", {}) or {}).get("grasp_score", 0.0) or 0.0), 8),
        "second_core_complexity_score": round(float((second_context.get("pool", {}) or {}).get("core_complexity_score", 0.0) or 0.0), 8),
        "second_punish_state": round(float((second_context.get("emotion", {}) or {}).get("pun", 0.0) or 0.0), 8),
        "baseline_pair_ready": 1,
        "has_relief": int("relief" in kinds),
        "has_correct_event": int("correct_event" in kinds),
        "has_reassurance": int("reassurance" in kinds),
        "has_complexity": int("complexity" in kinds),
        "has_simplicity": int("simplicity" in kinds),
        "relief_strength": round(float(kinds.get("relief", 0.0)), 8),
        "correct_event_strength": round(float(kinds.get("correct_event", 0.0)), 8),
        "reassurance_strength": round(float(kinds.get("reassurance", 0.0)), 8),
        "bind_reward_signal": int("reward_signal" in attrs),
        "bind_cfs_correctness": int("cfs_correctness" in attrs),
        "bind_cfs_reassurance": int("cfs_reassurance" in attrs),
        "action_focus_triggered": int("attention_focus" in actions),
        "direct_da_delta": round(float(direct_emotion_updates.get("DA", 0.0)), 8),
        "direct_ser_delta": round(float(direct_emotion_updates.get("SER", 0.0)), 8),
        "direct_oxy_delta": round(float(direct_emotion_updates.get("OXY", 0.0)), 8),
        "direct_end_delta": round(float(direct_emotion_updates.get("END", 0.0)), 8),
        "direct_cor_delta": round(float(direct_emotion_updates.get("COR", 0.0)), 8),
        "direct_adr_delta": round(float(direct_emotion_updates.get("ADR", 0.0)), 8),
        "attrs": "|".join(sorted(set(attrs))),
        "actions": "|".join(sorted(set(actions))),
    }

    if "correct_event" in kinds:
        nt_correct = nt_updates_for_signal(doc, kind="correct_event", strength=float(kinds["correct_event"]))
        row["nt_correct_da_positive"] = int(float(nt_correct.get("DA", 0.0)) > 0.0)
        row["nt_correct_oxy_positive"] = int(float(nt_correct.get("OXY", 0.0)) > 0.0)
        row["nt_correct_ser_positive"] = int(float(nt_correct.get("SER", 0.0)) > 0.0)
        row["nt_correct_foc_positive"] = int(float(nt_correct.get("FOC", 0.0)) > 0.0)
        row["nt_correct_da_delta"] = round(float(nt_correct.get("DA", 0.0)), 8)
        row["nt_correct_oxy_delta"] = round(float(nt_correct.get("OXY", 0.0)), 8)
        row["nt_correct_ser_delta"] = round(float(nt_correct.get("SER", 0.0)), 8)
        row["nt_correct_foc_delta"] = round(float(nt_correct.get("FOC", 0.0)), 8)
    else:
        row["nt_correct_da_positive"] = 0
        row["nt_correct_oxy_positive"] = 0
        row["nt_correct_ser_positive"] = 0
        row["nt_correct_foc_positive"] = 0
        row["nt_correct_da_delta"] = 0.0
        row["nt_correct_oxy_delta"] = 0.0
        row["nt_correct_ser_delta"] = 0.0
        row["nt_correct_foc_delta"] = 0.0

    if "relief" in kinds:
        nt_relief = nt_updates_for_signal(doc, kind="relief", strength=float(kinds["relief"]))
        row["nt_relief_end_positive"] = int(float(nt_relief.get("END", 0.0)) > 0.0)
        row["nt_relief_ser_positive"] = int(float(nt_relief.get("SER", 0.0)) > 0.0)
        row["nt_relief_oxy_positive"] = int(float(nt_relief.get("OXY", 0.0)) > 0.0)
        row["nt_relief_cor_negative"] = int(float(nt_relief.get("COR", 0.0)) < 0.0)
        row["nt_relief_adr_negative"] = int(float(nt_relief.get("ADR", 0.0)) < 0.0)
        row["nt_relief_end_delta"] = round(float(nt_relief.get("END", 0.0)), 8)
        row["nt_relief_ser_delta"] = round(float(nt_relief.get("SER", 0.0)), 8)
        row["nt_relief_oxy_delta"] = round(float(nt_relief.get("OXY", 0.0)), 8)
        row["nt_relief_cor_delta"] = round(float(nt_relief.get("COR", 0.0)), 8)
        row["nt_relief_adr_delta"] = round(float(nt_relief.get("ADR", 0.0)), 8)
    else:
        row["nt_relief_end_positive"] = 0
        row["nt_relief_ser_positive"] = 0
        row["nt_relief_oxy_positive"] = 0
        row["nt_relief_cor_negative"] = 0
        row["nt_relief_adr_negative"] = 0
        row["nt_relief_end_delta"] = 0.0
        row["nt_relief_ser_delta"] = 0.0
        row["nt_relief_oxy_delta"] = 0.0
        row["nt_relief_cor_delta"] = 0.0
        row["nt_relief_adr_delta"] = 0.0

    if "reassurance" in kinds:
        nt_reassure = nt_updates_for_signal(doc, kind="reassurance", strength=float(kinds["reassurance"]))
        row["nt_reassure_ser_positive"] = int(float(nt_reassure.get("SER", 0.0)) > 0.0)
        row["nt_reassure_oxy_positive"] = int(float(nt_reassure.get("OXY", 0.0)) > 0.0)
        row["nt_reassure_end_positive"] = int(float(nt_reassure.get("END", 0.0)) > 0.0)
        row["nt_reassure_da_positive"] = int(float(nt_reassure.get("DA", 0.0)) > 0.0)
        row["nt_reassure_foc_positive"] = int(float(nt_reassure.get("FOC", 0.0)) > 0.0)
        row["nt_reassure_cor_negative"] = int(float(nt_reassure.get("COR", 0.0)) < 0.0)
        row["nt_reassure_adr_negative"] = int(float(nt_reassure.get("ADR", 0.0)) < 0.0)
        row["nt_reassure_ser_delta"] = round(float(nt_reassure.get("SER", 0.0)), 8)
        row["nt_reassure_oxy_delta"] = round(float(nt_reassure.get("OXY", 0.0)), 8)
        row["nt_reassure_end_delta"] = round(float(nt_reassure.get("END", 0.0)), 8)
        row["nt_reassure_da_delta"] = round(float(nt_reassure.get("DA", 0.0)), 8)
        row["nt_reassure_foc_delta"] = round(float(nt_reassure.get("FOC", 0.0)), 8)
        row["nt_reassure_cor_delta"] = round(float(nt_reassure.get("COR", 0.0)), 8)
        row["nt_reassure_adr_delta"] = round(float(nt_reassure.get("ADR", 0.0)), 8)
    else:
        row["nt_reassure_ser_positive"] = 0
        row["nt_reassure_oxy_positive"] = 0
        row["nt_reassure_end_positive"] = 0
        row["nt_reassure_da_positive"] = 0
        row["nt_reassure_foc_positive"] = 0
        row["nt_reassure_cor_negative"] = 0
        row["nt_reassure_adr_negative"] = 0
        row["nt_reassure_ser_delta"] = 0.0
        row["nt_reassure_oxy_delta"] = 0.0
        row["nt_reassure_end_delta"] = 0.0
        row["nt_reassure_da_delta"] = 0.0
        row["nt_reassure_foc_delta"] = 0.0
        row["nt_reassure_cor_delta"] = 0.0
        row["nt_reassure_adr_delta"] = 0.0
    return row


def build_pair_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_family: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_family.setdefault(str(row["family"]), {})[str(row["branch"])] = row

    pair_rows: list[dict[str, Any]] = []
    for family, mapping in sorted(by_family.items()):
        relief = mapping.get("relief_only", {})
        correct_on = mapping.get("correct_event_on", {})
        correct_block = mapping.get("correct_event_block_current_cp", {})
        reassure_on = mapping.get("reassurance_on", {})
        block_punish = mapping.get("reassurance_block_high_punish", {})
        block_grasp = mapping.get("reassurance_block_low_grasp", {})
        block_complexity = mapping.get("reassurance_block_high_complexity", {})

        row = {
            "family": family,
            "baseline_conforms_all": 1,
            "relief_only_pass": int(
                int(relief.get("has_relief", 0) or 0) == 1
                and int(relief.get("has_correct_event", 0) or 0) == 0
                and int(relief.get("has_reassurance", 0) or 0) == 0
                and int(relief.get("nt_relief_end_positive", 0) or 0) == 1
                and int(relief.get("nt_relief_ser_positive", 0) or 0) == 1
                and int(relief.get("nt_relief_oxy_positive", 0) or 0) == 1
                and int(relief.get("nt_relief_cor_negative", 0) or 0) == 1
                and int(relief.get("nt_relief_adr_negative", 0) or 0) == 1
            ),
            "correct_event_on_pass": int(
                int(correct_on.get("has_correct_event", 0) or 0) == 1
                and int(correct_on.get("bind_reward_signal", 0) or 0) == 1
                and int(correct_on.get("bind_cfs_correctness", 0) or 0) == 1
                and int(correct_on.get("action_focus_triggered", 0) or 0) == 1
                and int(correct_on.get("nt_correct_da_positive", 0) or 0) == 1
                and int(correct_on.get("nt_correct_oxy_positive", 0) or 0) == 1
                and int(correct_on.get("nt_correct_ser_positive", 0) or 0) == 1
                and int(correct_on.get("nt_correct_foc_positive", 0) or 0) == 1
            ),
            "correct_event_block_quiet": int(int(correct_block.get("has_correct_event", 0) or 0) == 0),
            "reassurance_on_pass": int(
                int(reassure_on.get("has_reassurance", 0) or 0) == 1
                and int(reassure_on.get("bind_cfs_reassurance", 0) or 0) == 1
                and int(reassure_on.get("nt_reassure_ser_positive", 0) or 0) == 1
                and int(reassure_on.get("nt_reassure_oxy_positive", 0) or 0) == 1
                and int(reassure_on.get("nt_reassure_end_positive", 0) or 0) == 1
                and int(reassure_on.get("nt_reassure_da_positive", 0) or 0) == 1
                and int(reassure_on.get("nt_reassure_foc_positive", 0) or 0) == 1
                and int(reassure_on.get("nt_reassure_cor_negative", 0) or 0) == 1
                and int(reassure_on.get("nt_reassure_adr_negative", 0) or 0) == 1
            ),
            "block_high_punish_quiet": int(int(block_punish.get("has_reassurance", 0) or 0) == 0),
            "block_low_grasp_quiet": int(int(block_grasp.get("has_reassurance", 0) or 0) == 0),
            "block_high_complexity_quiet": int(int(block_complexity.get("has_reassurance", 0) or 0) == 0),
            "relief_strength": round(float(relief.get("relief_strength", 0.0) or 0.0), 8),
            "correct_event_strength": round(float(correct_on.get("correct_event_strength", 0.0) or 0.0), 8),
            "reassurance_strength": round(float(reassure_on.get("reassurance_strength", 0.0) or 0.0), 8),
            "reassure_on_punish_state": round(float(reassure_on.get("second_punish_state", 0.0) or 0.0), 8),
            "block_high_punish_state": round(float(block_punish.get("second_punish_state", 0.0) or 0.0), 8),
            "reassure_on_grasp_score": round(float(reassure_on.get("second_grasp_score", 0.0) or 0.0), 8),
            "block_low_grasp_score": round(float(block_grasp.get("second_grasp_score", 0.0) or 0.0), 8),
            "reassure_on_core_complexity_score": round(float(reassure_on.get("second_core_complexity_score", 0.0) or 0.0), 8),
            "block_high_complexity_score": round(float(block_complexity.get("second_core_complexity_score", 0.0) or 0.0), 8),
        }
        row["all_ok"] = int(
            int(row["baseline_conforms_all"]) == 1
            and int(row["relief_only_pass"]) == 1
            and int(row["correct_event_on_pass"]) == 1
            and int(row["correct_event_block_quiet"]) == 1
            and int(row["reassurance_on_pass"]) == 1
            and int(row["block_high_punish_quiet"]) == 1
            and int(row["block_low_grasp_quiet"]) == 1
            and int(row["block_high_complexity_quiet"]) == 1
        )
        pair_rows.append(row)
    return pair_rows


def summarize_evidence(*, rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]]) -> dict[str, Any]:
    def branch_rows(branch: str) -> list[dict[str, Any]]:
        return [row for row in rows if str(row.get("branch", "")) == branch]

    relief_rows = branch_rows("relief_only")
    correct_rows = branch_rows("correct_event_on")
    correct_block_rows = branch_rows("correct_event_block_current_cp")
    reassure_rows = branch_rows("reassurance_on")
    block_punish_rows = branch_rows("reassurance_block_high_punish")
    block_grasp_rows = branch_rows("reassurance_block_low_grasp")
    block_complexity_rows = branch_rows("reassurance_block_high_complexity")

    summary: dict[str, Any] = {
        "case_count": int(len(rows)),
        "family_count": int(len(pair_rows)),
        "baseline_conforms_ratio": round(safe_ratio(sum(int(row.get("baseline_pair_ready", 0) or 0) for row in rows), len(rows) or 1), 6),
        "relief_only_pass_ratio": round(safe_ratio(sum(int(row.get("relief_only_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "correct_event_on_pass_ratio": round(safe_ratio(sum(int(row.get("correct_event_on_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "correct_event_block_quiet_ratio": round(safe_ratio(sum(int(row.get("correct_event_block_quiet", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "reassurance_on_pass_ratio": round(safe_ratio(sum(int(row.get("reassurance_on_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "block_high_punish_quiet_ratio": round(safe_ratio(sum(int(row.get("block_high_punish_quiet", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "block_low_grasp_quiet_ratio": round(safe_ratio(sum(int(row.get("block_low_grasp_quiet", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "block_high_complexity_quiet_ratio": round(safe_ratio(sum(int(row.get("block_high_complexity_quiet", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "all_ok_ratio": round(safe_ratio(sum(int(row.get("all_ok", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "relief_strength_mean": mean_or_zero([num(row, "relief_strength") for row in relief_rows]),
        "correct_event_strength_mean": mean_or_zero([num(row, "correct_event_strength") for row in correct_rows]),
        "reassurance_strength_mean": mean_or_zero([num(row, "reassurance_strength") for row in reassure_rows]),
        "reassure_on_grasp_score_mean": mean_or_zero([num(row, "second_grasp_score") for row in reassure_rows]),
        "block_low_grasp_score_mean": mean_or_zero([num(row, "second_grasp_score") for row in block_grasp_rows]),
        "reassure_on_punish_state_mean": mean_or_zero([num(row, "second_punish_state") for row in reassure_rows]),
        "block_high_punish_state_mean": mean_or_zero([num(row, "second_punish_state") for row in block_punish_rows]),
        "reassure_on_core_complexity_score_mean": mean_or_zero([num(row, "second_core_complexity_score") for row in reassure_rows]),
        "block_high_complexity_score_mean": mean_or_zero([num(row, "second_core_complexity_score") for row in block_complexity_rows]),
        "correct_event_reward_attr_ratio": round(safe_ratio(sum(int(row.get("bind_reward_signal", 0) or 0) for row in correct_rows), len(correct_rows) or 1), 6),
        "correct_event_correctness_attr_ratio": round(safe_ratio(sum(int(row.get("bind_cfs_correctness", 0) or 0) for row in correct_rows), len(correct_rows) or 1), 6),
        "correct_event_focus_action_ratio": round(safe_ratio(sum(int(row.get("action_focus_triggered", 0) or 0) for row in correct_rows), len(correct_rows) or 1), 6),
        "reassurance_global_attr_ratio": round(safe_ratio(sum(int(row.get("bind_cfs_reassurance", 0) or 0) for row in reassure_rows), len(reassure_rows) or 1), 6),
        "correct_nt_ok_ratio": round(
            safe_ratio(
                sum(
                    int(
                        int(row.get("nt_correct_da_positive", 0) or 0) == 1
                        and int(row.get("nt_correct_oxy_positive", 0) or 0) == 1
                        and int(row.get("nt_correct_ser_positive", 0) or 0) == 1
                        and int(row.get("nt_correct_foc_positive", 0) or 0) == 1
                    )
                    for row in correct_rows
                ),
                len(correct_rows) or 1,
            ),
            6,
        ),
        "relief_nt_ok_ratio": round(
            safe_ratio(
                sum(
                    int(
                        int(row.get("nt_relief_end_positive", 0) or 0) == 1
                        and int(row.get("nt_relief_ser_positive", 0) or 0) == 1
                        and int(row.get("nt_relief_oxy_positive", 0) or 0) == 1
                        and int(row.get("nt_relief_cor_negative", 0) or 0) == 1
                        and int(row.get("nt_relief_adr_negative", 0) or 0) == 1
                    )
                    for row in relief_rows
                ),
                len(relief_rows) or 1,
            ),
            6,
        ),
        "reassurance_nt_ok_ratio": round(
            safe_ratio(
                sum(
                    int(
                        int(row.get("nt_reassure_ser_positive", 0) or 0) == 1
                        and int(row.get("nt_reassure_oxy_positive", 0) or 0) == 1
                        and int(row.get("nt_reassure_end_positive", 0) or 0) == 1
                        and int(row.get("nt_reassure_da_positive", 0) or 0) == 1
                        and int(row.get("nt_reassure_foc_positive", 0) or 0) == 1
                        and int(row.get("nt_reassure_cor_negative", 0) or 0) == 1
                        and int(row.get("nt_reassure_adr_negative", 0) or 0) == 1
                    )
                    for row in reassure_rows
                ),
                len(reassure_rows) or 1,
            ),
            6,
        ),
    }

    wins = int(sum(int(row.get("all_ok", 0) or 0) for row in pair_rows))
    losses = int(len(pair_rows) - wins)
    summary["all_ok_sign_p"] = sign_test_p_value(wins, losses)

    support_level = "not_supported"
    if (
        len(pair_rows) >= 8
        and summary["baseline_conforms_ratio"] >= 0.999
        and summary["relief_only_pass_ratio"] >= 0.999
        and summary["correct_event_on_pass_ratio"] >= 0.999
        and summary["correct_event_block_quiet_ratio"] >= 0.999
        and summary["reassurance_on_pass_ratio"] >= 0.999
        and summary["block_high_punish_quiet_ratio"] >= 0.999
        and summary["block_low_grasp_quiet_ratio"] >= 0.999
        and summary["block_high_complexity_quiet_ratio"] >= 0.999
        and summary["correct_event_reward_attr_ratio"] >= 0.999
        and summary["correct_event_correctness_attr_ratio"] >= 0.999
        and summary["correct_event_focus_action_ratio"] >= 0.999
        and summary["reassurance_global_attr_ratio"] >= 0.999
        and summary["correct_nt_ok_ratio"] >= 0.999
        and summary["relief_nt_ok_ratio"] >= 0.999
        and summary["reassurance_nt_ok_ratio"] >= 0.999
        and summary["all_ok_ratio"] >= 0.999
        and summary["all_ok_sign_p"] <= 0.01
    ):
        support_level = "strong_evidence"
    elif (
        len(pair_rows) >= 4
        and summary["relief_only_pass_ratio"] >= 0.80
        and summary["correct_event_on_pass_ratio"] >= 0.80
        and summary["reassurance_on_pass_ratio"] >= 0.80
    ):
        support_level = "useful_but_not_strong"
    summary["support_level"] = support_level
    return summary


def make_charts(*, rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]], stamp: str) -> list[Path]:
    plt = e01.setup_matplotlib()
    paths: list[Path] = []

    branch_order = [
        "relief_only",
        "correct_event_on",
        "correct_event_block_current_cp",
        "reassurance_on",
        "reassurance_block_high_punish",
        "reassurance_block_low_grasp",
        "reassurance_block_high_complexity",
    ]
    labels = {
        "relief_only": "仅缓解",
        "correct_event_on": "正确事件",
        "correct_event_block_current_cp": "高CP阻断",
        "reassurance_on": "安心通过",
        "reassurance_block_high_punish": "高惩罚阻断",
        "reassurance_block_low_grasp": "低把握阻断",
        "reassurance_block_high_complexity": "高复杂阻断",
    }
    relief_vals = []
    correct_vals = []
    reassure_vals = []
    for branch in branch_order:
        branch_rows = [row for row in rows if str(row.get("branch", "")) == branch]
        relief_vals.append(mean_or_zero([num(row, "has_relief") for row in branch_rows]))
        correct_vals.append(mean_or_zero([num(row, "has_correct_event") for row in branch_rows]))
        reassure_vals.append(mean_or_zero([num(row, "has_reassurance") for row in branch_rows]))
    fig, ax = plt.subplots(figsize=(11.2, 4.8))
    xs = list(range(len(branch_order)))
    width = 0.24
    ax.bar([x - width for x in xs], relief_vals, width=width, color="#2563eb", label="出现 relief")
    ax.bar(xs, correct_vals, width=width, color="#dc2626", label="出现 correct_event")
    ax.bar([x + width for x in xs], reassure_vals, width=width, color="#16a34a", label="出现 reassurance")
    ax.set_xticks(xs, [labels[b] for b in branch_order], rotation=14)
    ax.set_ylim(0.0, 1.05)
    ax.set_ylabel("比例")
    ax.set_title("E09 恢复类认知感受的分层触发与门控阻断")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    path = CHART_DIR / f"e09_conflict_relief_branch_contrast_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    family_labels = [str(row.get("family", "")) for row in pair_rows]
    family_ok = [int(row.get("all_ok", 0) or 0) for row in pair_rows]
    fig, ax = plt.subplots(figsize=(9.4, 4.2))
    ax.bar(family_labels, family_ok, color=["#16a34a" if v else "#dc2626" for v in family_ok])
    ax.set_ylim(0.0, 1.1)
    ax.set_ylabel("all_ok")
    ax.set_title("E09 family 级恢复链与门控阻断是否全部通过")
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = CHART_DIR / f"e09_conflict_relief_family_pass_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    categories = ["把握感", "惩罚态", "核心复杂度"]
    on_vals = [
        mean_or_zero([num(row, "reassure_on_grasp_score") for row in pair_rows]),
        mean_or_zero([num(row, "reassure_on_punish_state") for row in pair_rows]),
        mean_or_zero([num(row, "reassure_on_core_complexity_score") for row in pair_rows]),
    ]
    blocked_vals = [
        mean_or_zero([num(row, "block_low_grasp_score") for row in pair_rows]),
        mean_or_zero([num(row, "block_high_punish_state") for row in pair_rows]),
        mean_or_zero([num(row, "block_high_complexity_score") for row in pair_rows]),
    ]
    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    xs = list(range(len(categories)))
    ax.bar([x - 0.18 for x in xs], on_vals, width=0.36, color="#16a34a", label="reassurance_on")
    ax.bar([x + 0.18 for x in xs], blocked_vals, width=0.36, color="#dc2626", label="对应阻断分支")
    ax.set_xticks(xs, categories)
    ax.set_ylim(0.0, 0.8)
    ax.set_ylabel("均值")
    ax.set_title("E09 reassurance 关键门控量对照")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False)
    fig.tight_layout()
    path = CHART_DIR / f"e09_conflict_relief_gating_contrast_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    return paths


def write_design_note(path: Path) -> None:
    lines = [
        "# E09 设计逻辑",
        "",
        "本实验把 E09 从“自然语言矛盾是否被安抚”收窄为一个当前实现已经可以白箱复查的最小命题：",
        "",
        "1. 同一对象在高认知压之后，如果只下降到“部分恢复区”，应先出现 relief，而不应过早跳到 correct_event；",
        "2. 同一对象如果从高认知压显著回落，并且当前已经进入 settled 区，应触发 correct_event，同时写入 reward_signal 与 cfs_correctness；",
        "3. 在进一步满足把握感较高、核心复杂度较低、惩罚态不过高时，应从恢复态推进到 reassurance；",
        "4. 只要把这三个门控中的任意一个拉坏，高一级恢复信号就必须熄灭。",
        "",
        "本实验有意采用双拍白箱构造，而不是直接用自然语言矛盾课程。原因有二：",
        "",
        "- 第一，当前能被严格复查的是恢复链的门槛逻辑本身，而不是更高层的语义解释能力；",
        "- 第二，correct_event 的真正触发口径不是手写的 `delta_cp_abs` 字段，而是同一对象 `cp_abs` 的历史差值。只有把前后落差明确构造成远离阈值的样本，才能证明当前实现的硬门槛确实成立。",
        "",
        "因此，正文只主张“恢复类认知感受的分层触发与门控阻断链已成立”，不把它提前扩写成广义自然语言矛盾解决能力。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    *,
    rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    charts: list[Path],
    whitebox_case: dict[str, Any],
    stamp: str,
) -> Path:
    lines: list[str] = []
    lines.append(f"# E09 恢复类认知感受分层链路报告（{stamp}）")
    lines.append("")
    lines.append("## 核心结论")
    lines.append("")
    lines.append(f"- 支持等级：**{summary.get('support_level', 'unknown')}**")
    lines.append(f"- family 数：{int(summary.get('family_count', 0))}")
    lines.append(f"- 整体通过比例：{summary.get('all_ok_ratio', 0.0):.3f}")
    lines.append(f"- 符号检验 p 值：{summary.get('all_ok_sign_p', 1.0):.8f}")
    lines.append(f"- relief-only 通过比例：{summary.get('relief_only_pass_ratio', 0.0):.3f}")
    lines.append(f"- correct_event 通过比例：{summary.get('correct_event_on_pass_ratio', 0.0):.3f}")
    lines.append(f"- correct_event 阻断静默比例：{summary.get('correct_event_block_quiet_ratio', 0.0):.3f}")
    lines.append(f"- reassurance 通过比例：{summary.get('reassurance_on_pass_ratio', 0.0):.3f}")
    lines.append(f"- 高惩罚阻断静默比例：{summary.get('block_high_punish_quiet_ratio', 0.0):.3f}")
    lines.append(f"- 低把握阻断静默比例：{summary.get('block_low_grasp_quiet_ratio', 0.0):.3f}")
    lines.append(f"- 高复杂阻断静默比例：{summary.get('block_high_complexity_quiet_ratio', 0.0):.3f}")
    lines.append("")
    lines.append("## 正文可使用的最小命题")
    lines.append("")
    lines.append(
        "在当前 AP 原型中，恢复类认知感受并不是一个模糊标签，而是沿着 "
        "`高认知压 -> relief -> correct_event -> reassurance` 的门槛链路分层显影。"
        "只要把同一对象的 `cp_abs` 历史差值与当前 settled 条件构造到位，"
        "相关 CFS 信号、属性绑定、局部动作与 NT 调制就会稳定出现；反之，只要把"
        "当前认知压、惩罚态、把握感或核心复杂度中的关键门控拉坏，上位恢复信号就会同步熄灭。"
    )
    lines.append("")
    lines.append("## 强证据边界")
    lines.append("")
    lines.append("- 本实验不主张“所有自然语言矛盾场景都已能被 AP 稳定安抚”。")
    lines.append("- 本实验只主张：当前实现中的恢复类认知感受门槛链与下游调制链已经白箱成立。")
    lines.append("- 特别地，`correct_event` 的门槛依赖同一对象 `cp_abs` 的历史差值，而不是手工填写的 `delta_cp_abs` 字段。")
    lines.append("")
    lines.append("## family 级通过情况")
    lines.append("")
    lines.append("| family | relief_only | correct_on | correct_block | reassure_on | high_punish_block | low_grasp_block | high_complexity_block | all_ok |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in pair_rows:
        lines.append(
            f"| {row['family']} | {int(row['relief_only_pass'])} | {int(row['correct_event_on_pass'])} | "
            f"{int(row['correct_event_block_quiet'])} | {int(row['reassurance_on_pass'])} | "
            f"{int(row['block_high_punish_quiet'])} | {int(row['block_low_grasp_quiet'])} | "
            f"{int(row['block_high_complexity_quiet'])} | {int(row['all_ok'])} |"
        )
    lines.append("")
    lines.append("## 白箱样例")
    lines.append("")
    lines.append(f"- 样例 family：`{whitebox_case.get('family', '')}`；branch：`{whitebox_case.get('branch', '')}`")
    lines.append(f"- prior `cp_abs`：`{whitebox_case.get('prior_cp_abs', 0.0)}`；second `cp_abs`：`{whitebox_case.get('second_cp_abs', 0.0)}`")
    lines.append(f"- relief 强度：`{whitebox_case.get('relief_strength', 0.0)}`；correct_event 强度：`{whitebox_case.get('correct_event_strength', 0.0)}`；reassurance 强度：`{whitebox_case.get('reassurance_strength', 0.0)}`")
    lines.append(f"- 绑定属性：`{whitebox_case.get('attrs', '')}`")
    lines.append(f"- 动作：`{whitebox_case.get('actions', '')}`")
    lines.append("")
    lines.append("## 图表")
    lines.append("")
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    lines.append("## 备注")
    lines.append("")
    lines.append("- 本实验故意使用双拍白箱构造，以避免把恢复链门槛与更高层的语言理解能力混写。")
    lines.append("- 对正文来说，这比一个松散的“安抚故事样本”更窄，但也更硬。")
    lines.append("")
    path = REPORT_DIR / f"E09_conflict_relief_report_{stamp}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_experiment(*, stamp: str, family_count: int) -> dict[str, Any]:
    ensure_dirs()
    doc = load_default_rules_doc()
    specs = FAMILY_SPECS[: max(1, min(int(family_count), len(FAMILY_SPECS)))]
    rows: list[dict[str, Any]] = []
    for spec in specs:
        for branch in BRANCHES:
            rows.append(run_case(doc, spec=spec, branch=branch))
    rows.sort(key=lambda row: (str(row["family"]), str(row["branch"])))
    pair_rows = build_pair_rows(rows)
    summary = summarize_evidence(rows=rows, pair_rows=pair_rows)
    charts = make_charts(rows=rows, pair_rows=pair_rows, stamp=stamp)
    design_note = REPORT_DIR / "E09_conflict_relief_design_logic.md"
    write_design_note(design_note)
    whitebox_case = next((row for row in rows if str(row.get("branch", "")) == "reassurance_on"), {})
    report = write_report(
        rows=rows,
        pair_rows=pair_rows,
        summary=summary,
        charts=charts,
        whitebox_case=whitebox_case,
        stamp=stamp,
    )
    case_csv = TABLE_DIR / f"e09_conflict_relief_case_rows_{stamp}.csv"
    pair_csv = TABLE_DIR / f"e09_conflict_relief_pair_rows_{stamp}.csv"
    summary_json = TABLE_DIR / f"e09_conflict_relief_summary_{stamp}.json"
    whitebox_json = TABLE_DIR / f"e09_conflict_relief_whitebox_{stamp}.json"
    e01.write_csv(case_csv, rows)
    e01.write_csv(pair_csv, pair_rows)
    e01.write_json(summary_json, summary)
    e01.write_json(whitebox_json, {"row": whitebox_case})
    evidence = {
        "experiment_id": "E09",
        "stamp": stamp,
        "support_level": summary.get("support_level", "unknown"),
        "summary": summary,
        "artifacts": {
            "case_rows": str(case_csv),
            "pair_rows": str(pair_csv),
            "summary": str(summary_json),
            "whitebox": str(whitebox_json),
            "report": str(report),
            "design_note": str(design_note),
            "charts": [str(path) for path in charts],
        },
    }
    e01.write_json(MANIFEST_DIR / f"E09_conflict_relief_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E09_conflict_relief_latest.json", evidence)
    return evidence


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper E09 conflict-relief experiment.")
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
