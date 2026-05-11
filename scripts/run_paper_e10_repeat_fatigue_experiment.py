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

ROOT = Path(__file__).resolve().parent
AP_ROOT = ROOT / "Artificial-PsyArch"
if str(AP_ROOT) not in sys.path:
    sys.path.insert(0, str(AP_ROOT))

import run_paper_e01_experiment as e01
from attention.main import AttentionFilter
from innate_script._rules_engine import evaluate_rules, normalize_rules_doc


ARTIFACT_ROOT = ROOT / "docs" / "paper_artifacts_2026-05-11"
E10_ROOT = ARTIFACT_ROOT / "E10_repeat_fatigue"
TABLE_DIR = E10_ROOT / "tables"
CHART_DIR = E10_ROOT / "charts"
REPORT_DIR = E10_ROOT / "reports"
MANIFEST_DIR = E10_ROOT / "manifests"

STAMP_DEFAULT = "e10_final_v1"


@dataclass(frozen=True)
class FamilySpec:
    family: str
    a_er: float
    a_ev: float
    b_er: float
    b_ev: float
    fatigue_on: float


FAMILY_SPECS: list[FamilySpec] = [
    FamilySpec("F01", 0.60, 0.40, 0.55, 0.35, 0.22),
    FamilySpec("F02", 0.61, 0.39, 0.54, 0.36, 0.21),
    FamilySpec("F03", 0.62, 0.38, 0.53, 0.37, 0.20),
    FamilySpec("F04", 0.63, 0.37, 0.52, 0.38, 0.19),
    FamilySpec("F05", 0.64, 0.36, 0.51, 0.39, 0.18),
    FamilySpec("F06", 0.58, 0.42, 0.56, 0.34, 0.23),
    FamilySpec("F07", 0.57, 0.43, 0.55, 0.35, 0.24),
    FamilySpec("F08", 0.59, 0.41, 0.54, 0.36, 0.25),
    FamilySpec("F09", 0.60, 0.40, 0.53, 0.37, 0.26),
    FamilySpec("F10", 0.61, 0.39, 0.52, 0.38, 0.27),
    FamilySpec("F11", 0.62, 0.38, 0.51, 0.39, 0.28),
    FamilySpec("F12", 0.63, 0.37, 0.50, 0.40, 0.30),
]


ATTENTION_STAGES = ("first", "same", "variant", "skip", "recovered")
Boredom_BRANCHES = (
    "fatigue_low_quiet",
    "boredom_on",
    "boredom_block_high_nov",
    "boredom_block_high_reward",
    "boredom_block_high_complexity",
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


class DummyPool:
    def __init__(self, items: list[dict[str, Any]]):
        self._items = items

    def get_state_snapshot(self, *, trace_id: str, tick_id: str | None = None, top_k=None):
        return {
            "success": True,
            "data": {
                "snapshot": {
                    "summary": {"active_item_count": len(self._items)},
                    "top_items": list(self._items),
                }
            },
        }

    def apply_energy_update(self, **kwargs):
        return {"success": True, "data": {"after": {"er": 0.0, "ev": 0.0}}}


def make_attention_row(
    *,
    item_id: str,
    ref_object_id: str,
    display: str,
    semantic_context_key: str,
    er: float,
    ev: float,
) -> dict[str, Any]:
    return {
        "item_id": str(item_id),
        "ref_object_id": str(ref_object_id),
        "ref_object_type": "st",
        "display": str(display),
        "er": float(er),
        "ev": float(ev),
        "cp_abs": abs(float(er) - float(ev)),
        "salience_score": max(float(er), float(ev)),
        "fatigue": 0.0,
        "recency_gain": 1.0,
        "updated_at": 1,
        "ref_snapshot": {"content_display": str(display), "token_count": 2},
        "ref_alias_ids": [],
        "runtime_attribute_names": [],
        "packet_attribute_names": [],
        "all_attribute_names": [],
        "bound_attribute_names": [],
        "runtime_bound_attribute_units": [],
        "semantic_context_key": str(semantic_context_key),
    }


def load_default_rules_doc() -> dict[str, Any]:
    raw = yaml.safe_load((AP_ROOT / "innate_script" / "config" / "innate_rules.yaml").read_text(encoding="utf-8"))
    doc, errors, _warnings = normalize_rules_doc(raw)
    if errors:
        raise RuntimeError(f"normalize_rules_doc failed: {errors}")
    return doc


def boredom_context(*, fatigue: float, nov: float, reward: float, complexity: float) -> dict[str, Any]:
    return {
        "pool": {
            "total_er": 0.7,
            "total_ev": 0.4,
            "total_energy": 1.1,
            "item_count": 3,
            "total_cp_abs": 0.3,
            "energy_concentration": 0.62,
            "effective_peak_count": 2.0,
            "complexity_score": float(complexity),
            "core_complexity_score": float(complexity),
        },
        "pool_items": [
            {
                "item_id": "spi_repeat",
                "ref_object_id": "st_repeat",
                "ref_object_type": "st",
                "display": "repeat target",
                "er": 0.6,
                "ev": 0.4,
                "cp_delta": 0.3,
                "cp_abs": 0.3,
                "total_energy": 1.0,
                "fatigue": float(fatigue),
            }
        ],
        "cam": {"size": 3, "energy_concentration": 0.62},
        "memory_activation": {"item_count": 0, "total_ev": 0.0},
        "emotion": {"nt": {"NOV": float(nov)}, "rwd": float(reward), "pun": 0.0},
        "stimulus": {"residual_ratio": 0.2, "input_is_empty": 0, "input_has_text": 1},
        "retrieval": {"stimulus": {"best_match_score": 0.0, "grasp_score": 0.0}, "structure": {"best_match_score": 0.0}},
    }


def signal_strengths(out: dict[str, Any]) -> dict[str, float]:
    signals = ((out.get("directives") or {}).get("cfs_signals") or [])
    result: dict[str, float] = {}
    for row in signals:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind", "") or "").strip()
        if kind:
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


def nt_updates_for_signal(doc: dict[str, Any], *, kind: str, strength: float) -> dict[str, float]:
    out = evaluate_rules(
        doc=doc,
        trace_id="paper_e10_nt_probe",
        tick_id=f"paper_e10_nt_{kind}",
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


def run_attention_sequence(spec: FamilySpec) -> list[dict[str, Any]]:
    attention = AttentionFilter(
        config_override={
            "top_n": 4,
            "consume_energy": False,
            "attention_repeat_fatigue_enabled": True,
            "attention_repeat_fatigue_penalty_gain": 0.5,
            "attention_repeat_fatigue_recovery_per_call": 0.5,
            "attention_repeat_fatigue_selected_gain": 1.0,
            "attention_repeat_fatigue_window_calls": 6,
        }
    )

    def pool_for(stage: str) -> DummyPool:
        if stage == "first":
            return DummyPool(
                [
                    make_attention_row(
                        item_id=f"spi_{spec.family}_a1",
                        ref_object_id=f"st_{spec.family}_a",
                        display=f"{spec.family}A",
                        semantic_context_key=f"ctx:{spec.family}:A",
                        er=spec.a_er,
                        ev=spec.a_ev,
                    ),
                    make_attention_row(
                        item_id=f"spi_{spec.family}_b1",
                        ref_object_id=f"st_{spec.family}_b",
                        display=f"{spec.family}B",
                        semantic_context_key=f"ctx:{spec.family}:B",
                        er=spec.b_er,
                        ev=spec.b_ev,
                    ),
                ]
            )
        if stage == "same":
            return DummyPool(
                [
                    make_attention_row(
                        item_id=f"spi_{spec.family}_a2",
                        ref_object_id=f"st_{spec.family}_a",
                        display=f"{spec.family}A",
                        semantic_context_key=f"ctx:{spec.family}:A",
                        er=spec.a_er,
                        ev=spec.a_ev,
                    ),
                    make_attention_row(
                        item_id=f"spi_{spec.family}_b2",
                        ref_object_id=f"st_{spec.family}_b",
                        display=f"{spec.family}B",
                        semantic_context_key=f"ctx:{spec.family}:B",
                        er=spec.b_er,
                        ev=spec.b_ev,
                    ),
                ]
            )
        if stage == "variant":
            return DummyPool(
                [
                    make_attention_row(
                        item_id=f"spi_{spec.family}_a3",
                        ref_object_id=f"st_{spec.family}_a",
                        display=f"{spec.family}A*",
                        semantic_context_key=f"ctx:{spec.family}:A_variant",
                        er=spec.a_er,
                        ev=spec.a_ev,
                    ),
                    make_attention_row(
                        item_id=f"spi_{spec.family}_b3",
                        ref_object_id=f"st_{spec.family}_b",
                        display=f"{spec.family}B",
                        semantic_context_key=f"ctx:{spec.family}:B",
                        er=spec.b_er,
                        ev=spec.b_ev,
                    ),
                ]
            )
        if stage == "skip":
            return DummyPool(
                [
                    make_attention_row(
                        item_id=f"spi_{spec.family}_c1",
                        ref_object_id=f"st_{spec.family}_c",
                        display=f"{spec.family}C",
                        semantic_context_key=f"ctx:{spec.family}:C",
                        er=spec.a_er + 0.02,
                        ev=max(0.0, spec.a_ev - 0.02),
                    ),
                    make_attention_row(
                        item_id=f"spi_{spec.family}_d1",
                        ref_object_id=f"st_{spec.family}_d",
                        display=f"{spec.family}D",
                        semantic_context_key=f"ctx:{spec.family}:D",
                        er=spec.b_er + 0.03,
                        ev=max(0.0, spec.b_ev - 0.01),
                    ),
                ]
            )
        if stage == "recovered":
            return pool_for("same")
        raise ValueError(f"unknown stage: {stage}")

    rows: list[dict[str, Any]] = []
    for stage in ATTENTION_STAGES:
        pool = pool_for(stage)
        result = attention.build_cam_from_pool(pool, trace_id=f"paper_e10_{spec.family}_{stage}", tick_id=f"{spec.family}_{stage}")
        if not result.get("success", False):
            raise RuntimeError(f"attention build failed for {spec.family}/{stage}: {result}")
        report = ((result.get("data") or {}).get("attention_report") or {})
        top_items = list(report.get("top_items", []) or [])
        focus_row = next((row for row in top_items if str(row.get("ref_object_id", "")) == f"st_{spec.family}_a"), None)
        if focus_row is None:
            rows.append(
                {
                    "family": spec.family,
                    "stage": stage,
                    "has_focus_object": 0,
                    "repeat_attention_penalty": 0.0,
                    "attention_priority": 0.0,
                    "semantic_context_key": "",
                    "repeat_key": "",
                    "gap_calls": 0,
                    "carried_strength": 0.0,
                    "state_pool_candidate_count": int(report.get("state_pool_candidate_count", 0) or 0),
                    "repeat_penalty_selected_count": int(report.get("repeat_attention_penalty_selected_count", 0) or 0),
                    "repeat_penalty_total": round(float(report.get("repeat_attention_penalty_total", 0.0) or 0.0), 8),
                }
            )
            continue
        detail = dict(focus_row.get("repeat_attention_penalty_detail", {}) or {})
        rows.append(
            {
                "family": spec.family,
                "stage": stage,
                "has_focus_object": 1,
                "repeat_attention_penalty": round(float(focus_row.get("repeat_attention_penalty", 0.0) or 0.0), 8),
                "attention_priority": round(float(focus_row.get("attention_priority", 0.0) or 0.0), 8),
                "semantic_context_key": str(focus_row.get("semantic_context_key", "") or ""),
                "repeat_key": str(detail.get("key", "") or ""),
                "gap_calls": int(detail.get("gap_calls", 0) or 0),
                "carried_strength": round(float(detail.get("carried_strength", 0.0) or 0.0), 8),
                "state_pool_candidate_count": int(report.get("state_pool_candidate_count", 0) or 0),
                "repeat_penalty_selected_count": int(report.get("repeat_attention_penalty_selected_count", 0) or 0),
                "repeat_penalty_total": round(float(report.get("repeat_attention_penalty_total", 0.0) or 0.0), 8),
            }
        )
    return rows


def run_boredom_branch(doc: dict[str, Any], *, spec: FamilySpec, branch: str) -> dict[str, Any]:
    if branch == "fatigue_low_quiet":
        context = boredom_context(fatigue=0.10, nov=0.10, reward=0.05, complexity=0.20)
    elif branch == "boredom_on":
        context = boredom_context(fatigue=spec.fatigue_on, nov=0.10, reward=0.05, complexity=0.20)
    elif branch == "boredom_block_high_nov":
        context = boredom_context(fatigue=spec.fatigue_on, nov=0.30, reward=0.05, complexity=0.20)
    elif branch == "boredom_block_high_reward":
        context = boredom_context(fatigue=spec.fatigue_on, nov=0.10, reward=0.35, complexity=0.20)
    elif branch == "boredom_block_high_complexity":
        context = boredom_context(fatigue=spec.fatigue_on, nov=0.10, reward=0.05, complexity=0.50)
    else:
        raise ValueError(f"unknown boredom branch: {branch}")

    out = evaluate_rules(
        doc=doc,
        trace_id="paper_e10_boredom",
        tick_id=f"{spec.family}_{branch}",
        tick_index=1,
        cfs_signals=[],
        state_windows=[],
        context=context,
        now_ms=100,
        runtime_state={},
        allow_timer=True,
        allowed_phases=["cfs", "directives"],
    )
    kinds = signal_strengths(out)
    attrs = pool_bind_attribute_names(out)
    row: dict[str, Any] = {
        "family": spec.family,
        "branch": branch,
        "fatigue": round(float(context["pool_items"][0]["fatigue"]), 8),
        "nov_state": round(float(context["emotion"]["nt"]["NOV"]), 8),
        "reward_state": round(float(context["emotion"]["rwd"]), 8),
        "core_complexity_score": round(float(context["pool"]["core_complexity_score"]), 8),
        "has_repetition": int("repetition" in kinds),
        "has_boredom": int("boredom" in kinds),
        "repetition_strength": round(float(kinds.get("repetition", 0.0)), 8),
        "boredom_strength": round(float(kinds.get("boredom", 0.0)), 8),
        "bind_cfs_repetition": int("cfs_repetition" in attrs),
        "bind_cfs_boredom": int("cfs_boredom" in attrs),
        "attrs": "|".join(sorted(set(attrs))),
    }

    if "repetition" in kinds:
        nt_rep = nt_updates_for_signal(doc, kind="repetition", strength=float(kinds["repetition"]))
        row["nt_repetition_cor_positive"] = int(float(nt_rep.get("COR", 0.0)) > 0.0)
        row["nt_repetition_end_positive"] = int(float(nt_rep.get("END", 0.0)) > 0.0)
        row["nt_repetition_ser_negative"] = int(float(nt_rep.get("SER", 0.0)) < 0.0)
        row["nt_repetition_nov_negative"] = int(float(nt_rep.get("NOV", 0.0)) < 0.0)
        row["nt_repetition_cor_delta"] = round(float(nt_rep.get("COR", 0.0)), 8)
        row["nt_repetition_end_delta"] = round(float(nt_rep.get("END", 0.0)), 8)
        row["nt_repetition_ser_delta"] = round(float(nt_rep.get("SER", 0.0)), 8)
        row["nt_repetition_nov_delta"] = round(float(nt_rep.get("NOV", 0.0)), 8)
    else:
        row["nt_repetition_cor_positive"] = 0
        row["nt_repetition_end_positive"] = 0
        row["nt_repetition_ser_negative"] = 0
        row["nt_repetition_nov_negative"] = 0
        row["nt_repetition_cor_delta"] = 0.0
        row["nt_repetition_end_delta"] = 0.0
        row["nt_repetition_ser_delta"] = 0.0
        row["nt_repetition_nov_delta"] = 0.0

    if "boredom" in kinds:
        nt_boredom = nt_updates_for_signal(doc, kind="boredom", strength=float(kinds["boredom"]))
        row["nt_boredom_nov_negative"] = int(float(nt_boredom.get("NOV", 0.0)) < 0.0)
        row["nt_boredom_da_negative"] = int(float(nt_boredom.get("DA", 0.0)) < 0.0)
        row["nt_boredom_foc_negative"] = int(float(nt_boredom.get("FOC", 0.0)) < 0.0)
        row["nt_boredom_ser_negative"] = int(float(nt_boredom.get("SER", 0.0)) < 0.0)
        row["nt_boredom_end_positive"] = int(float(nt_boredom.get("END", 0.0)) > 0.0)
        row["nt_boredom_nov_delta"] = round(float(nt_boredom.get("NOV", 0.0)), 8)
        row["nt_boredom_da_delta"] = round(float(nt_boredom.get("DA", 0.0)), 8)
        row["nt_boredom_foc_delta"] = round(float(nt_boredom.get("FOC", 0.0)), 8)
        row["nt_boredom_ser_delta"] = round(float(nt_boredom.get("SER", 0.0)), 8)
        row["nt_boredom_end_delta"] = round(float(nt_boredom.get("END", 0.0)), 8)
    else:
        row["nt_boredom_nov_negative"] = 0
        row["nt_boredom_da_negative"] = 0
        row["nt_boredom_foc_negative"] = 0
        row["nt_boredom_ser_negative"] = 0
        row["nt_boredom_end_positive"] = 0
        row["nt_boredom_nov_delta"] = 0.0
        row["nt_boredom_da_delta"] = 0.0
        row["nt_boredom_foc_delta"] = 0.0
        row["nt_boredom_ser_delta"] = 0.0
        row["nt_boredom_end_delta"] = 0.0
    return row


def build_pair_rows(attention_rows: list[dict[str, Any]], boredom_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    att_by_family: dict[str, dict[str, dict[str, Any]]] = {}
    for row in attention_rows:
        att_by_family.setdefault(str(row["family"]), {})[str(row["stage"])] = row
    boredom_by_family: dict[str, dict[str, dict[str, Any]]] = {}
    for row in boredom_rows:
        boredom_by_family.setdefault(str(row["family"]), {})[str(row["branch"])] = row

    pair_rows: list[dict[str, Any]] = []
    for family in sorted(set(att_by_family) | set(boredom_by_family)):
        att = att_by_family.get(family, {})
        bor = boredom_by_family.get(family, {})
        first = att.get("first", {})
        same = att.get("same", {})
        variant = att.get("variant", {})
        recovered = att.get("recovered", {})

        fatigue_low = bor.get("fatigue_low_quiet", {})
        boredom_on = bor.get("boredom_on", {})
        high_nov = bor.get("boredom_block_high_nov", {})
        high_reward = bor.get("boredom_block_high_reward", {})
        high_complexity = bor.get("boredom_block_high_complexity", {})

        row = {
            "family": family,
            "attention_first_zero": int(int(first.get("has_focus_object", 0) or 0) == 1 and abs(float(first.get("repeat_attention_penalty", 0.0) or 0.0)) <= 1e-9),
            "attention_same_positive": int(float(same.get("repeat_attention_penalty", 0.0) or 0.0) > 0.0),
            "attention_variant_zero": int(int(variant.get("has_focus_object", 0) or 0) == 1 and abs(float(variant.get("repeat_attention_penalty", 0.0) or 0.0)) <= 1e-9),
            "attention_variant_key_changed": int(
                str(first.get("repeat_key", "") or "") != ""
                and str(variant.get("repeat_key", "") or "") != ""
                and str(first.get("repeat_key", "") or "") != str(variant.get("repeat_key", "") or "")
            ),
            "attention_recovered_positive": int(float(recovered.get("repeat_attention_penalty", 0.0) or 0.0) > 0.0),
            "attention_recovered_lower_than_same": int(
                float(recovered.get("repeat_attention_penalty", 0.0) or 0.0) < float(same.get("repeat_attention_penalty", 0.0) or 0.0)
            ),
            "boredom_low_fatigue_quiet": int(
                int(fatigue_low.get("has_repetition", 0) or 0) == 0
                and int(fatigue_low.get("has_boredom", 0) or 0) == 0
            ),
            "boredom_on_pass": int(
                int(boredom_on.get("has_repetition", 0) or 0) == 1
                and int(boredom_on.get("has_boredom", 0) or 0) == 1
                and int(boredom_on.get("bind_cfs_repetition", 0) or 0) == 1
                and int(boredom_on.get("bind_cfs_boredom", 0) or 0) == 1
            ),
            "boredom_block_high_nov_quiet": int(
                int(high_nov.get("has_repetition", 0) or 0) == 1
                and int(high_nov.get("has_boredom", 0) or 0) == 0
            ),
            "boredom_block_high_reward_quiet": int(
                int(high_reward.get("has_repetition", 0) or 0) == 1
                and int(high_reward.get("has_boredom", 0) or 0) == 0
            ),
            "boredom_block_high_complexity_quiet": int(
                int(high_complexity.get("has_repetition", 0) or 0) == 1
                and int(high_complexity.get("has_boredom", 0) or 0) == 0
            ),
            "repetition_nt_ok": int(
                int(boredom_on.get("nt_repetition_cor_positive", 0) or 0) == 1
                and int(boredom_on.get("nt_repetition_end_positive", 0) or 0) == 1
                and int(boredom_on.get("nt_repetition_ser_negative", 0) or 0) == 1
                and int(boredom_on.get("nt_repetition_nov_negative", 0) or 0) == 1
            ),
            "boredom_nt_ok": int(
                int(boredom_on.get("nt_boredom_nov_negative", 0) or 0) == 1
                and int(boredom_on.get("nt_boredom_da_negative", 0) or 0) == 1
                and int(boredom_on.get("nt_boredom_foc_negative", 0) or 0) == 1
                and int(boredom_on.get("nt_boredom_ser_negative", 0) or 0) == 1
                and int(boredom_on.get("nt_boredom_end_positive", 0) or 0) == 1
            ),
            "same_penalty": round(float(same.get("repeat_attention_penalty", 0.0) or 0.0), 8),
            "variant_penalty": round(float(variant.get("repeat_attention_penalty", 0.0) or 0.0), 8),
            "recovered_penalty": round(float(recovered.get("repeat_attention_penalty", 0.0) or 0.0), 8),
            "boredom_on_repetition_strength": round(float(boredom_on.get("repetition_strength", 0.0) or 0.0), 8),
            "boredom_on_strength": round(float(boredom_on.get("boredom_strength", 0.0) or 0.0), 8),
            "boredom_on_nov_state": round(float(boredom_on.get("nov_state", 0.0) or 0.0), 8),
            "high_nov_state": round(float(high_nov.get("nov_state", 0.0) or 0.0), 8),
            "boredom_on_reward_state": round(float(boredom_on.get("reward_state", 0.0) or 0.0), 8),
            "high_reward_state": round(float(high_reward.get("reward_state", 0.0) or 0.0), 8),
            "boredom_on_complexity": round(float(boredom_on.get("core_complexity_score", 0.0) or 0.0), 8),
            "high_complexity_state": round(float(high_complexity.get("core_complexity_score", 0.0) or 0.0), 8),
        }
        row["all_ok"] = int(
            int(row["attention_first_zero"]) == 1
            and int(row["attention_same_positive"]) == 1
            and int(row["attention_variant_zero"]) == 1
            and int(row["attention_variant_key_changed"]) == 1
            and int(row["attention_recovered_positive"]) == 1
            and int(row["attention_recovered_lower_than_same"]) == 1
            and int(row["boredom_low_fatigue_quiet"]) == 1
            and int(row["boredom_on_pass"]) == 1
            and int(row["boredom_block_high_nov_quiet"]) == 1
            and int(row["boredom_block_high_reward_quiet"]) == 1
            and int(row["boredom_block_high_complexity_quiet"]) == 1
            and int(row["repetition_nt_ok"]) == 1
            and int(row["boredom_nt_ok"]) == 1
        )
        pair_rows.append(row)
    return pair_rows


def summarize_evidence(*, attention_rows: list[dict[str, Any]], boredom_rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]]) -> dict[str, Any]:
    def attention_stage(stage: str) -> list[dict[str, Any]]:
        return [row for row in attention_rows if str(row.get("stage", "")) == stage]

    def boredom_branch(branch: str) -> list[dict[str, Any]]:
        return [row for row in boredom_rows if str(row.get("branch", "")) == branch]

    first_rows = attention_stage("first")
    same_rows = attention_stage("same")
    variant_rows = attention_stage("variant")
    recovered_rows = attention_stage("recovered")

    low_rows = boredom_branch("fatigue_low_quiet")
    on_rows = boredom_branch("boredom_on")
    high_nov_rows = boredom_branch("boredom_block_high_nov")
    high_reward_rows = boredom_branch("boredom_block_high_reward")
    high_complexity_rows = boredom_branch("boredom_block_high_complexity")

    summary: dict[str, Any] = {
        "attention_case_count": int(len(attention_rows)),
        "boredom_case_count": int(len(boredom_rows)),
        "family_count": int(len(pair_rows)),
        "attention_first_zero_ratio": round(safe_ratio(sum(int(row.get("attention_first_zero", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "attention_same_positive_ratio": round(safe_ratio(sum(int(row.get("attention_same_positive", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "attention_variant_zero_ratio": round(safe_ratio(sum(int(row.get("attention_variant_zero", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "attention_variant_key_changed_ratio": round(safe_ratio(sum(int(row.get("attention_variant_key_changed", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "attention_recovered_positive_ratio": round(safe_ratio(sum(int(row.get("attention_recovered_positive", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "attention_recovered_lower_ratio": round(safe_ratio(sum(int(row.get("attention_recovered_lower_than_same", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "same_penalty_mean": mean_or_zero([num(row, "repeat_attention_penalty") for row in same_rows]),
        "variant_penalty_mean": mean_or_zero([num(row, "repeat_attention_penalty") for row in variant_rows]),
        "recovered_penalty_mean": mean_or_zero([num(row, "repeat_attention_penalty") for row in recovered_rows]),
        "same_priority_mean": mean_or_zero([num(row, "attention_priority") for row in same_rows]),
        "variant_priority_mean": mean_or_zero([num(row, "attention_priority") for row in variant_rows]),
        "boredom_low_fatigue_quiet_ratio": round(safe_ratio(sum(int(row.get("boredom_low_fatigue_quiet", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "boredom_on_pass_ratio": round(safe_ratio(sum(int(row.get("boredom_on_pass", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "boredom_block_high_nov_quiet_ratio": round(safe_ratio(sum(int(row.get("boredom_block_high_nov_quiet", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "boredom_block_high_reward_quiet_ratio": round(safe_ratio(sum(int(row.get("boredom_block_high_reward_quiet", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "boredom_block_high_complexity_quiet_ratio": round(safe_ratio(sum(int(row.get("boredom_block_high_complexity_quiet", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "repetition_nt_ok_ratio": round(safe_ratio(sum(int(row.get("repetition_nt_ok", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "boredom_nt_ok_ratio": round(safe_ratio(sum(int(row.get("boredom_nt_ok", 0) or 0) for row in pair_rows), len(pair_rows) or 1), 6),
        "fatigue_low_repetition_ratio": round(safe_ratio(sum(int(row.get("has_repetition", 0) or 0) for row in low_rows), len(low_rows) or 1), 6),
        "boredom_on_repetition_ratio": round(safe_ratio(sum(int(row.get("has_repetition", 0) or 0) for row in on_rows), len(on_rows) or 1), 6),
        "boredom_on_boredom_ratio": round(safe_ratio(sum(int(row.get("has_boredom", 0) or 0) for row in on_rows), len(on_rows) or 1), 6),
        "high_nov_boredom_ratio": round(safe_ratio(sum(int(row.get("has_boredom", 0) or 0) for row in high_nov_rows), len(high_nov_rows) or 1), 6),
        "high_reward_boredom_ratio": round(safe_ratio(sum(int(row.get("has_boredom", 0) or 0) for row in high_reward_rows), len(high_reward_rows) or 1), 6),
        "high_complexity_boredom_ratio": round(safe_ratio(sum(int(row.get("has_boredom", 0) or 0) for row in high_complexity_rows), len(high_complexity_rows) or 1), 6),
        "boredom_on_strength_mean": mean_or_zero([num(row, "boredom_strength") for row in on_rows]),
        "boredom_on_repetition_strength_mean": mean_or_zero([num(row, "repetition_strength") for row in on_rows]),
    }

    wins = int(sum(int(row.get("all_ok", 0) or 0) for row in pair_rows))
    losses = int(len(pair_rows) - wins)
    summary["all_ok_ratio"] = round(safe_ratio(wins, len(pair_rows) or 1), 6)
    summary["all_ok_sign_p"] = sign_test_p_value(wins, losses)

    support_level = "not_supported"
    if (
        len(pair_rows) >= 8
        and summary["attention_first_zero_ratio"] >= 0.999
        and summary["attention_same_positive_ratio"] >= 0.999
        and summary["attention_variant_zero_ratio"] >= 0.999
        and summary["attention_variant_key_changed_ratio"] >= 0.999
        and summary["attention_recovered_positive_ratio"] >= 0.999
        and summary["attention_recovered_lower_ratio"] >= 0.999
        and summary["boredom_low_fatigue_quiet_ratio"] >= 0.999
        and summary["boredom_on_pass_ratio"] >= 0.999
        and summary["boredom_block_high_nov_quiet_ratio"] >= 0.999
        and summary["boredom_block_high_reward_quiet_ratio"] >= 0.999
        and summary["boredom_block_high_complexity_quiet_ratio"] >= 0.999
        and summary["repetition_nt_ok_ratio"] >= 0.999
        and summary["boredom_nt_ok_ratio"] >= 0.999
        and summary["all_ok_ratio"] >= 0.999
        and summary["all_ok_sign_p"] <= 0.01
    ):
        support_level = "strong_evidence"
    elif (
        len(pair_rows) >= 4
        and summary["attention_same_positive_ratio"] >= 0.80
        and summary["attention_variant_zero_ratio"] >= 0.80
        and summary["boredom_on_pass_ratio"] >= 0.80
    ):
        support_level = "useful_but_not_strong"
    summary["support_level"] = support_level
    return summary


def make_charts(*, attention_rows: list[dict[str, Any]], boredom_rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]], stamp: str) -> list[Path]:
    plt = e01.setup_matplotlib()
    paths: list[Path] = []

    stage_order = ["first", "same", "variant", "recovered"]
    stage_labels = {"first": "首次", "same": "立刻重复", "variant": "上下文变体", "recovered": "跳过后恢复"}
    penalty_means = [mean_or_zero([num(row, "repeat_attention_penalty") for row in attention_rows if str(row.get("stage", "")) == stage]) for stage in stage_order]
    priority_means = [mean_or_zero([num(row, "attention_priority") for row in attention_rows if str(row.get("stage", "")) == stage]) for stage in stage_order]
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.2))
    xs = list(range(len(stage_order)))
    axes[0].bar(xs, penalty_means, color="#dc2626", alpha=0.88)
    axes[0].set_xticks(xs, [stage_labels[s] for s in stage_order], rotation=10)
    axes[0].set_title("重复注意力惩罚均值")
    axes[0].grid(axis="y", alpha=0.22)
    axes[1].bar(xs, priority_means, color="#2563eb", alpha=0.88)
    axes[1].set_xticks(xs, [stage_labels[s] for s in stage_order], rotation=10)
    axes[1].set_title("目标对象注意力优先级均值")
    axes[1].grid(axis="y", alpha=0.22)
    fig.suptitle("E10 同语义上下文重复入选的抑制与恢复")
    fig.tight_layout()
    path = CHART_DIR / f"e10_repeat_fatigue_attention_contrast_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    branch_order = [
        "fatigue_low_quiet",
        "boredom_on",
        "boredom_block_high_nov",
        "boredom_block_high_reward",
        "boredom_block_high_complexity",
    ]
    branch_labels = {
        "fatigue_low_quiet": "低疲劳",
        "boredom_on": "低新奇+低奖+低复杂",
        "boredom_block_high_nov": "高NOV阻断",
        "boredom_block_high_reward": "高奖励阻断",
        "boredom_block_high_complexity": "高复杂阻断",
    }
    repetition_means = [mean_or_zero([num(row, "has_repetition") for row in boredom_rows if str(row.get("branch", "")) == branch]) for branch in branch_order]
    boredom_means = [mean_or_zero([num(row, "has_boredom") for row in boredom_rows if str(row.get("branch", "")) == branch]) for branch in branch_order]
    fig, ax = plt.subplots(figsize=(10.8, 4.4))
    xs = list(range(len(branch_order)))
    width = 0.34
    ax.bar([x - width / 2 for x in xs], repetition_means, width=width, color="#2563eb", label="出现 repetition")
    ax.bar([x + width / 2 for x in xs], boredom_means, width=width, color="#16a34a", label="出现 boredom")
    ax.set_xticks(xs, [branch_labels[b] for b in branch_order], rotation=12)
    ax.set_ylim(0.0, 1.05)
    ax.set_ylabel("比例")
    ax.set_title("E10 repetition 与 boredom 的门控分离")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False)
    fig.tight_layout()
    path = CHART_DIR / f"e10_repeat_fatigue_boredom_gating_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    family_labels = [str(row.get("family", "")) for row in pair_rows]
    family_ok = [int(row.get("all_ok", 0) or 0) for row in pair_rows]
    fig, ax = plt.subplots(figsize=(9.4, 4.2))
    ax.bar(family_labels, family_ok, color=["#16a34a" if v else "#dc2626" for v in family_ok])
    ax.set_ylim(0.0, 1.1)
    ax.set_ylabel("all_ok")
    ax.set_title("E10 family 级双层重复调节链是否全部通过")
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = CHART_DIR / f"e10_repeat_fatigue_family_pass_{stamp}.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)
    return paths


def write_design_note(path: Path) -> None:
    lines = [
        "# E10 设计逻辑",
        "",
        "本实验把 E10 从“系统会不会觉得新鲜”收窄为两条当前实现已经能白箱复查的重复调节链：",
        "",
        "1. 注意力层：同语义上下文对象若连续多拍都进入 CAM，应在 `repeat_attention_penalty` 上表现为即时抑制；若中间跳过若干拍，则惩罚应衰减恢复；若对象改成新的语义上下文键，即便 ref_object_id 相同，也不应直接继承旧惩罚。",
        "2. 全局感受层：高 fatigue 应转成 repetition；但 boredom 不是“只要重复就出现”，而要求 repetition 已经存在，且 NOV、奖励、核心复杂度三项都处在较低区间。任意拉高其中一项，boredom 就应熄灭。",
        "",
        "这个设计的好处是，它分别对应“重复被抑制”和“仍然缺少新鲜收益”两个不同层次，不会把所有重复相关现象揉成一个模糊标签。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    *,
    attention_rows: list[dict[str, Any]],
    boredom_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    charts: list[Path],
    whitebox: dict[str, Any],
    stamp: str,
) -> Path:
    lines: list[str] = []
    lines.append(f"# E10 重复疲劳与门控新鲜度报告（{stamp}）")
    lines.append("")
    lines.append("## 核心结论")
    lines.append("")
    lines.append(f"- 支持等级：**{summary.get('support_level', 'unknown')}**")
    lines.append(f"- family 数：{int(summary.get('family_count', 0))}")
    lines.append(f"- 整体通过比例：{summary.get('all_ok_ratio', 0.0):.3f}")
    lines.append(f"- 符号检验 p 值：{summary.get('all_ok_sign_p', 1.0):.8f}")
    lines.append(f"- 注意力层立刻重复抑制比例：{summary.get('attention_same_positive_ratio', 0.0):.3f}")
    lines.append(f"- 注意力层变体免继承比例：{summary.get('attention_variant_zero_ratio', 0.0):.3f}")
    lines.append(f"- 注意力层跳过后恢复比例：{summary.get('attention_recovered_lower_ratio', 0.0):.3f}")
    lines.append(f"- boredom 显影比例：{summary.get('boredom_on_pass_ratio', 0.0):.3f}")
    lines.append(f"- 高 NOV / 高奖励 / 高复杂度阻断比例：{summary.get('boredom_block_high_nov_quiet_ratio', 0.0):.3f} / {summary.get('boredom_block_high_reward_quiet_ratio', 0.0):.3f} / {summary.get('boredom_block_high_complexity_quiet_ratio', 0.0):.3f}")
    lines.append("")
    lines.append("## 正文可使用的最小命题")
    lines.append("")
    lines.append(
        "在当前 AP 原型中，重复调节并不是一个单层开关，而是至少包含两层白箱链路："
        "一方面，同语义上下文对象若连续入选，会在注意力层被 `repeat_attention_penalty` 即时压低，"
        "而跳过若干拍或改成新的语义上下文键后，这个惩罚会分别表现为恢复或不继承；"
        "另一方面，高 fatigue 会转成全局 repetition，但 boredom 只有在低 NOV、低奖励、低复杂度同时满足时才会显影。"
    )
    lines.append("")
    lines.append("## 强证据边界")
    lines.append("")
    lines.append("- 本实验不主张“AP 已经具备完整的人类新颖体验”。")
    lines.append("- 本实验只主张：当前实现中的重复抑制与门控新鲜度链已经白箱成立。")
    lines.append("")
    lines.append("## family 级通过情况")
    lines.append("")
    lines.append("| family | same_penalty | variant_zero | recovered_lower | boredom_on | high_nov_block | high_reward_block | high_complexity_block | all_ok |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in pair_rows:
        lines.append(
            f"| {row['family']} | {int(row['attention_same_positive'])} | {int(row['attention_variant_zero'])} | "
            f"{int(row['attention_recovered_lower_than_same'])} | {int(row['boredom_on_pass'])} | "
            f"{int(row['boredom_block_high_nov_quiet'])} | {int(row['boredom_block_high_reward_quiet'])} | "
            f"{int(row['boredom_block_high_complexity_quiet'])} | {int(row['all_ok'])} |"
        )
    lines.append("")
    lines.append("## 白箱样例")
    lines.append("")
    attention_whitebox = dict((whitebox.get("attention_row", {}) or {}))
    boredom_whitebox = dict((whitebox.get("boredom_row", {}) or {}))
    lines.append(f"- 注意力样例 family：`{attention_whitebox.get('family', '')}`；stage：`{attention_whitebox.get('stage', '')}`")
    lines.append(
        f"- attention penalty：`{attention_whitebox.get('repeat_attention_penalty', 0.0)}`；"
        f" repeat_key：`{attention_whitebox.get('repeat_key', '')}`；gap_calls：`{attention_whitebox.get('gap_calls', 0)}`"
    )
    lines.append(f"- boredom 样例 family：`{boredom_whitebox.get('family', '')}`；branch：`{boredom_whitebox.get('branch', '')}`")
    lines.append(
        f"- repetition 强度：`{boredom_whitebox.get('repetition_strength', 0.0)}`；"
        f" boredom 强度：`{boredom_whitebox.get('boredom_strength', 0.0)}`；"
        f" attrs：`{boredom_whitebox.get('attrs', '')}`"
    )
    lines.append("")
    lines.append("## 图表")
    lines.append("")
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    lines.append("## 备注")
    lines.append("")
    lines.append("- 注意力层和 boredom 层故意分开建模，以避免把“重复惩罚”和“缺少新鲜收益”混成同一件事。")
    lines.append("- 这比直接跑一组自然语言重复课程更窄，但因果也更干净。")
    lines.append("")
    path = REPORT_DIR / f"E10_repeat_fatigue_report_{stamp}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_experiment(*, stamp: str, family_count: int) -> dict[str, Any]:
    ensure_dirs()
    doc = load_default_rules_doc()
    specs = FAMILY_SPECS[: max(1, min(int(family_count), len(FAMILY_SPECS)))]
    attention_rows: list[dict[str, Any]] = []
    boredom_rows: list[dict[str, Any]] = []
    for spec in specs:
        attention_rows.extend(run_attention_sequence(spec))
        for branch in Boredom_BRANCHES:
            boredom_rows.append(run_boredom_branch(doc, spec=spec, branch=branch))
    attention_rows.sort(key=lambda row: (str(row["family"]), str(row["stage"])))
    boredom_rows.sort(key=lambda row: (str(row["family"]), str(row["branch"])))
    pair_rows = build_pair_rows(attention_rows, boredom_rows)
    summary = summarize_evidence(attention_rows=attention_rows, boredom_rows=boredom_rows, pair_rows=pair_rows)
    charts = make_charts(attention_rows=attention_rows, boredom_rows=boredom_rows, pair_rows=pair_rows, stamp=stamp)
    design_note = REPORT_DIR / "E10_repeat_fatigue_design_logic.md"
    write_design_note(design_note)
    whitebox = {
        "attention_row": next((row for row in attention_rows if str(row.get("stage", "")) == "recovered"), {}),
        "boredom_row": next((row for row in boredom_rows if str(row.get("branch", "")) == "boredom_on"), {}),
    }
    report = write_report(
        attention_rows=attention_rows,
        boredom_rows=boredom_rows,
        pair_rows=pair_rows,
        summary=summary,
        charts=charts,
        whitebox=whitebox,
        stamp=stamp,
    )
    attention_csv = TABLE_DIR / f"e10_repeat_fatigue_attention_rows_{stamp}.csv"
    boredom_csv = TABLE_DIR / f"e10_repeat_fatigue_boredom_rows_{stamp}.csv"
    pair_csv = TABLE_DIR / f"e10_repeat_fatigue_pair_rows_{stamp}.csv"
    summary_json = TABLE_DIR / f"e10_repeat_fatigue_summary_{stamp}.json"
    whitebox_json = TABLE_DIR / f"e10_repeat_fatigue_whitebox_{stamp}.json"
    e01.write_csv(attention_csv, attention_rows)
    e01.write_csv(boredom_csv, boredom_rows)
    e01.write_csv(pair_csv, pair_rows)
    e01.write_json(summary_json, summary)
    e01.write_json(whitebox_json, whitebox)
    evidence = {
        "experiment_id": "E10",
        "stamp": stamp,
        "support_level": summary.get("support_level", "unknown"),
        "summary": summary,
        "artifacts": {
            "attention_rows": str(attention_csv),
            "boredom_rows": str(boredom_csv),
            "pair_rows": str(pair_csv),
            "summary": str(summary_json),
            "whitebox": str(whitebox_json),
            "report": str(report),
            "design_note": str(design_note),
            "charts": [str(path) for path in charts],
        },
    }
    e01.write_json(MANIFEST_DIR / f"E10_repeat_fatigue_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E10_repeat_fatigue_latest.json", evidence)
    return evidence


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper E10 repeat fatigue experiment.")
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
