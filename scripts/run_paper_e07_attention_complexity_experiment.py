# -*- coding: utf-8 -*-
"""Run paper E07 attention-complexity experiment.

Paper-facing E07 claim
----------------------
This experiment intentionally narrows E07 to a white-box claim that the
current AP prototype can already support with strong, auditable evidence:

1. under controlled runtime-state construction, changing effective candidate
   count changes `complexity_score` / `core_complexity_score` in a stable and
   monotonic way;
2. the complexity signal is translated by IESM into mode actions:
   low-complexity branches trigger `attention_diverge_mode`, mid branches stay
   quiet, and high-complexity branches trigger `attention_focus_mode`;
3. the resulting mode modulation is then injected into the next tick of a
   standardized probe pool, where it produces reproducible differences in
   `top_n`, `cam_item_count`, and `attention_energy_budget`.

The experiment does not try to prove that "complex text is more human-like".
It only proves the narrower causal chain that is already visible in the
implementation:

    complexity state -> complexity CFS -> attention mode action
    -> next-tick attention modulation -> probe-pool CAM difference
"""

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
from observatory._app import ObservatoryApp
from observatory.experiment.runner import apply_experiment_default_app_overrides


ARTIFACT_ROOT = ROOT / "docs" / "paper_artifacts_2026-05-11"
E07_ROOT = ARTIFACT_ROOT / "E07_attention_complexity"
TABLE_DIR = E07_ROOT / "tables"
CHART_DIR = E07_ROOT / "charts"
REPORT_DIR = E07_ROOT / "reports"
MANIFEST_DIR = E07_ROOT / "manifests"

STAMP_DEFAULT = "e07_final_v1"
PROBE_POOL_COUNT = 24


@dataclass(frozen=True)
class SourceSpec:
    case_id: str
    label: str
    item_count: int
    expected_mode: str  # diverge / neutral / focus


SOURCE_SPECS: list[SourceSpec] = [
    SourceSpec("S04", "low_4", 4, "diverge"),
    SourceSpec("S08", "low_8", 8, "diverge"),
    SourceSpec("S10", "mid_10", 10, "neutral"),
    SourceSpec("S12", "high_12", 12, "focus"),
    SourceSpec("S16", "high_16", 16, "focus"),
]

PAIR_FAMILIES: list[str] = [
    "ALF",
    "BRV",
    "CRN",
    "DLT",
    "ECH",
    "FOX",
    "GLF",
    "HZN",
    "IVY",
    "JDE",
    "KAI",
    "LUX",
]


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


def mean_or_zero(values: list[float]) -> float:
    clean = [float(x) for x in values if math.isfinite(float(x))]
    return round(statistics.fmean(clean), 8) if clean else 0.0


def make_runtime_structure(*, ref_id: str, display: str, er: float, ev: float) -> dict[str, Any]:
    return {
        "id": ref_id,
        "object_type": "st",
        "sub_type": "stimulus_sequence_structure",
        "content": {
            "raw": display,
            "display": display,
            "normalized": display,
        },
        "energy": {"er": float(er), "ev": float(ev)},
        "structure": {
            "display_text": display,
            "flat_tokens": list(display),
        },
    }


def build_app() -> tuple[ObservatoryApp, dict[str, Any]]:
    app = ObservatoryApp(
        config_override={
            "export_html": False,
            "export_json": False,
            "history_limit": 1,
            "input_chunking_enabled": False,
            "sensor_enable_echo": False,
            "sensor_include_echoes_in_packet": False,
        }
    )
    alignment = apply_experiment_default_app_overrides(app, source="paper_e07_whitebox")
    app.emotion._config["enabled"] = False
    return app, alignment


def seed_pool(
    app: ObservatoryApp,
    *,
    prefix: str,
    count: int,
    er: float = 1.0,
    ev: float = 1.0,
) -> None:
    for index in range(int(count)):
        display = f"{prefix}{index:02d}"
        runtime_object = make_runtime_structure(
            ref_id=f"st_{prefix}_{index:02d}",
            display=display,
            er=er,
            ev=ev,
        )
        result = app.pool.insert_runtime_node(
            runtime_object,
            trace_id=f"seed_{prefix}_{index:02d}",
            source_module="paper_e07_probe",
            allow_merge=False,
        )
        if not result.get("success", False):
            raise RuntimeError(f"seed_pool failed: {result}")


def build_source_report(attention_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "attention": attention_report,
        "stimulus_level": {
            "result": {
                "metrics": {
                    "grasp_score": 0.85,
                    "best_match_score": 0.85,
                }
            }
        },
        "retrieval": {
            "stimulus": {
                "grasp_score": 0.85,
                "best_match_score": 0.85,
            }
        },
        "emotion": {"pun": 0.0, "rwd": 0.0},
        "memory_activation": {
            "snapshot": {
                "summary": {"count": 0, "total_ev": 0.0},
                "items": [],
            }
        },
    }


def strongest_signal(cfs_signals: list[dict[str, Any]], kind: str) -> float:
    strengths = [
        float(item.get("strength", 0.0) or 0.0)
        for item in cfs_signals
        if isinstance(item, dict) and str(item.get("kind", "") or "") == kind
    ]
    return round(max(strengths), 8) if strengths else 0.0


def first_mode_action(action_triggers: list[dict[str, Any]]) -> str:
    for row in action_triggers:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("action_kind", "") or "")
        if kind in {"attention_diverge_mode", "attention_focus_mode"}:
            return kind
    return ""


def expected_mode_pass(expected_mode: str, observed_mode: str) -> int:
    expected = str(expected_mode or "").strip().lower()
    observed = str(observed_mode or "").strip().lower()
    normalize = {
        "diverge": "attention_diverge_mode",
        "focus": "attention_focus_mode",
        "neutral": "",
    }
    expected = normalize.get(expected, expected)
    if expected == "neutral":
        return int(observed == "")
    return int(expected == observed)


def run_source_case(*, family: str, spec: SourceSpec) -> tuple[dict[str, Any], dict[str, Any]]:
    app, alignment = build_app()
    try:
        app.clear_all()
        seed_pool(app, prefix=f"{family}{spec.case_id}", count=spec.item_count, er=1.0, ev=1.0)
        _cam_snapshot, attention_report = app._build_attention_memory_stub(
            trace_id=f"paper_e07_source_{family}_{spec.case_id}",
            tick_id="cycle_source_0001",
        )
        context = app._build_innate_rules_context(
            report=build_source_report(attention_report),
            pool_snapshot=None,
            emotion_state={"pun": 0.0, "rwd": 0.0},
            cfs_signals=[],
            trace_id=f"paper_e07_ctx_{family}_{spec.case_id}",
            tick_id="cycle_source_0001",
        )
        rules_result = app.iesm.run_tick_rules(
            trace_id=f"paper_e07_rules_{family}_{spec.case_id}",
            tick_id="cycle_source_0001",
            tick_index=1,
            cfs_signals=[],
            state_windows=[],
            context=context,
            dry_run=False,
            allowed_phases=["cfs", "directives"],
        )
        rules_data = rules_result.get("data", {}) or {}
        directives = rules_data.get("directives", {}) or {}
        cfs_signals = list(directives.get("cfs_signals", []) or [])
        action_triggers = list(directives.get("action_triggers", []) or [])
        action_result = app.action.run_action_cycle(
            trace_id=f"paper_e07_action_{family}_{spec.case_id}",
            tick_id="cycle_source_0001",
            tick_index=1,
            cfs_signals=cfs_signals,
            emotion_state={},
            innate_focus_directives=[],
            innate_action_triggers=action_triggers,
            memory_activation_snapshot={},
            local_reward_punish_map={},
        )
        action_data = action_result.get("data", {}) or {}
        modulation = dict(action_data.get("modulation_out", {}) or {})
        mode_action = first_mode_action(action_triggers)
        attention_mod = modulation.get("attention", {}) if isinstance(modulation.get("attention", {}), dict) else {}
        pool_summary = context.get("pool", {}) if isinstance(context.get("pool", {}), dict) else {}
        row = {
            "family": family,
            "case_id": spec.case_id,
            "label": spec.label,
            "item_count": int(spec.item_count),
            "expected_mode": spec.expected_mode,
            "baseline_conforms": int(bool(alignment.get("baseline_conforms_to_growth_cs_off", False))),
            "pool_item_count": int(pool_summary.get("item_count", 0) or 0),
            "pool_total_er": round(float(pool_summary.get("total_er", 0.0) or 0.0), 8),
            "pool_total_ev": round(float(pool_summary.get("total_ev", 0.0) or 0.0), 8),
            "pool_total_cp_abs": round(float(pool_summary.get("total_cp_abs", 0.0) or 0.0), 8),
            "effective_peak_count": round(float(pool_summary.get("effective_peak_count", 0.0) or 0.0), 8),
            "complexity_score": round(float(pool_summary.get("complexity_score", 0.0) or 0.0), 8),
            "core_complexity_score": round(float(pool_summary.get("core_complexity_score", 0.0) or 0.0), 8),
            "attention_top_n_current_tick": int(attention_report.get("top_n", 0) or 0),
            "cam_item_count_current_tick": int(
                ((attention_report.get("cam_snapshot_summary", {}) or {}).get("active_item_count", 0) or 0)
            ),
            "complexity_signal_strength": strongest_signal(cfs_signals, "complexity"),
            "simplicity_signal_strength": strongest_signal(cfs_signals, "simplicity"),
            "mode_action_kind": mode_action,
            "mode_action_triggered": int(bool(mode_action)),
            "mode_expected_pass": expected_mode_pass(spec.expected_mode, mode_action),
            "modulation_top_n": int(attention_mod.get("top_n", 0) or 0),
            "modulation_attention_energy_budget": round(
                float(attention_mod.get("attention_energy_budget", 0.0) or 0.0),
                8,
            ),
            "modulation_reason": str(attention_mod.get("reason", "") or ""),
        }
        return row, modulation
    finally:
        app.close()


def run_probe_case(*, family: str, branch: str, modulation: dict[str, Any]) -> dict[str, Any]:
    app, alignment = build_app()
    try:
        app.clear_all()
        # Probe pool should survive maintenance. Balanced ER=EV objects are
        # fully neutralized and pruned at tick start, which would turn this
        # experiment into an empty-pool artifact rather than a clean next-tick
        # attention comparison. Use a stable asymmetric pool shared by all
        # branches so the only changing factor is next-tick modulation.
        seed_pool(app, prefix=f"{family}P{branch[:1].upper()}", count=PROBE_POOL_COUNT, er=0.5, ev=1.0)
        app._last_modulation = dict(modulation or {})
        report = app.run_cycle(text=None)
        attention = report.get("attention", {}) or {}
        attention_resource = attention.get("attention_energy_resource", {}) or {}
        cam_budget = attention.get("cam_resource_budget", {}) or {}
        mod_in = (report.get("modulation_inputs", {}) or {}).get("attention", {}) or {}
        row = {
            "family": family,
            "branch": branch,
            "baseline_conforms": int(bool(alignment.get("baseline_conforms_to_growth_cs_off", False))),
            "modulation_input_reason": str(mod_in.get("reason", "") or ""),
            "modulation_input_top_n": int(mod_in.get("top_n", 0) or 0),
            "modulation_input_attention_energy_budget": round(
                float(mod_in.get("attention_energy_budget", 0.0) or 0.0),
                8,
            ),
            "attention_top_n": int(attention.get("top_n", 0) or 0),
            "cam_item_count": int(((attention.get("cam_snapshot_summary", {}) or {}).get("active_item_count", 0) or 0)),
            "cam_budget_used": int(cam_budget.get("used", 0) or 0),
            "cam_budget_cap": int(cam_budget.get("cap", 0) or 0),
            "attention_energy_budget": round(float(attention_resource.get("budget", 0.0) or 0.0), 8),
            "attention_net_delta_energy": round(float(attention_resource.get("net_delta_energy", 0.0) or 0.0), 8),
        }
        return row
    finally:
        app.close()


def summarize_evidence(*, source_rows: list[dict[str, Any]], probe_rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]]) -> dict[str, Any]:
    low_rows = [row for row in source_rows if str(row.get("expected_mode", "")) == "diverge"]
    mid_rows = [row for row in source_rows if str(row.get("expected_mode", "")) == "neutral"]
    high_rows = [row for row in source_rows if str(row.get("expected_mode", "")) == "focus"]

    low_pairs = [row for row in pair_rows if int(row.get("low_probe_ok", 0) or 0) == 1]
    mid_pairs = [row for row in pair_rows if int(row.get("mid_probe_ok", 0) or 0) == 1]
    high_pairs = [row for row in pair_rows if int(row.get("high_probe_ok", 0) or 0) == 1]
    ordered_capacity = [row for row in pair_rows if int(row.get("ordered_capacity_ok", 0) or 0) == 1]
    ordered_budget = [row for row in pair_rows if int(row.get("ordered_budget_ok", 0) or 0) == 1]
    all_ok = [row for row in pair_rows if int(row.get("all_ok", 0) or 0) == 1]

    summary: dict[str, Any] = {
        "source_case_count": int(len(source_rows)),
        "source_low_diverge_ratio": round(safe_ratio(sum(int(row.get("mode_expected_pass", 0) or 0) for row in low_rows), len(low_rows) or 1), 6),
        "source_mid_quiet_ratio": round(safe_ratio(sum(int(row.get("mode_expected_pass", 0) or 0) for row in mid_rows), len(mid_rows) or 1), 6),
        "source_high_focus_ratio": round(safe_ratio(sum(int(row.get("mode_expected_pass", 0) or 0) for row in high_rows), len(high_rows) or 1), 6),
        "source_baseline_conforms_ratio": round(
            safe_ratio(sum(int(row.get("baseline_conforms", 0) or 0) for row in source_rows), len(source_rows) or 1),
            6,
        ),
        "source_complexity_low_mean": mean_or_zero([num(row, "complexity_score") for row in low_rows]),
        "source_complexity_mid_mean": mean_or_zero([num(row, "complexity_score") for row in mid_rows]),
        "source_complexity_high_mean": mean_or_zero([num(row, "complexity_score") for row in high_rows]),
        "source_complexity_signal_low_mean": mean_or_zero([num(row, "complexity_signal_strength") for row in low_rows]),
        "source_complexity_signal_mid_mean": mean_or_zero([num(row, "complexity_signal_strength") for row in mid_rows]),
        "source_complexity_signal_high_mean": mean_or_zero([num(row, "complexity_signal_strength") for row in high_rows]),
        "probe_case_count": int(len(probe_rows)),
        "probe_pair_count": int(len(pair_rows)),
        "probe_low_branch_ratio": round(safe_ratio(len(low_pairs), len(pair_rows) or 1), 6),
        "probe_mid_branch_ratio": round(safe_ratio(len(mid_pairs), len(pair_rows) or 1), 6),
        "probe_high_branch_ratio": round(safe_ratio(len(high_pairs), len(pair_rows) or 1), 6),
        "probe_ordered_capacity_ratio": round(safe_ratio(len(ordered_capacity), len(pair_rows) or 1), 6),
        "probe_ordered_budget_ratio": round(safe_ratio(len(ordered_budget), len(pair_rows) or 1), 6),
        "probe_all_ok_ratio": round(safe_ratio(len(all_ok), len(pair_rows) or 1), 6),
        "probe_low_high_top_n_gap_mean": mean_or_zero([num(row, "low_high_top_n_gap") for row in pair_rows]),
        "probe_low_high_cam_gap_mean": mean_or_zero([num(row, "low_high_cam_gap") for row in pair_rows]),
        "probe_high_low_budget_gap_mean": mean_or_zero([num(row, "high_low_budget_gap") for row in pair_rows]),
        "probe_low_branch_top_n_mean": mean_or_zero(
            [num(row, "attention_top_n") for row in probe_rows if str(row.get("branch", "")) == "low"]
        ),
        "probe_mid_branch_top_n_mean": mean_or_zero(
            [num(row, "attention_top_n") for row in probe_rows if str(row.get("branch", "")) == "mid"]
        ),
        "probe_high_branch_top_n_mean": mean_or_zero(
            [num(row, "attention_top_n") for row in probe_rows if str(row.get("branch", "")) == "high"]
        ),
        "probe_low_branch_budget_mean": mean_or_zero(
            [num(row, "attention_energy_budget") for row in probe_rows if str(row.get("branch", "")) == "low"]
        ),
        "probe_mid_branch_budget_mean": mean_or_zero(
            [num(row, "attention_energy_budget") for row in probe_rows if str(row.get("branch", "")) == "mid"]
        ),
        "probe_high_branch_budget_mean": mean_or_zero(
            [num(row, "attention_energy_budget") for row in probe_rows if str(row.get("branch", "")) == "high"]
        ),
    }

    wins_all = int(len(all_ok))
    losses_all = int(len(pair_rows) - len(all_ok))
    wins_capacity = int(len(ordered_capacity))
    losses_capacity = int(len(pair_rows) - len(ordered_capacity))
    wins_budget = int(len(ordered_budget))
    losses_budget = int(len(pair_rows) - len(ordered_budget))
    summary["probe_all_ok_sign_p"] = sign_test_p_value(wins_all, losses_all)
    summary["probe_capacity_sign_p"] = sign_test_p_value(wins_capacity, losses_capacity)
    summary["probe_budget_sign_p"] = sign_test_p_value(wins_budget, losses_budget)

    support_level = "not_supported"
    if (
        len(source_rows) >= 40
        and summary["source_baseline_conforms_ratio"] >= 0.999
        and summary["source_low_diverge_ratio"] >= 0.999
        and summary["source_mid_quiet_ratio"] >= 0.999
        and summary["source_high_focus_ratio"] >= 0.999
        and summary["source_complexity_low_mean"] < summary["source_complexity_mid_mean"] < summary["source_complexity_high_mean"]
        and len(pair_rows) >= 8
        and summary["probe_low_branch_ratio"] >= 0.999
        and summary["probe_mid_branch_ratio"] >= 0.999
        and summary["probe_high_branch_ratio"] >= 0.999
        and summary["probe_ordered_capacity_ratio"] >= 0.999
        and summary["probe_ordered_budget_ratio"] >= 0.999
        and summary["probe_all_ok_ratio"] >= 0.999
        and summary["probe_all_ok_sign_p"] <= 0.01
    ):
        support_level = "strong_evidence"
    elif (
        len(source_rows) >= 15
        and summary["source_low_diverge_ratio"] >= 0.80
        and summary["source_high_focus_ratio"] >= 0.80
        and len(pair_rows) >= 6
        and summary["probe_ordered_capacity_ratio"] >= 0.80
        and summary["probe_ordered_budget_ratio"] >= 0.80
    ):
        support_level = "useful_but_not_strong"
    summary["support_level"] = support_level
    return summary


def make_charts(*, source_rows: list[dict[str, Any]], probe_rows: list[dict[str, Any]], stamp: str) -> list[Path]:
    plt = e01.setup_matplotlib()
    paths: list[Path] = []

    order = [4, 8, 10, 12, 16]
    x_values: list[int] = []
    complexity_means: list[float] = []
    signal_means: list[float] = []
    for count in order:
        rows = [row for row in source_rows if int(row.get("item_count", 0) or 0) == count]
        if not rows:
            continue
        x_values.append(count)
        complexity_means.append(mean_or_zero([num(row, "complexity_score") for row in rows]))
        signal_means.append(mean_or_zero([num(row, "complexity_signal_strength") for row in rows]))
    if x_values:
        fig, ax = plt.subplots(figsize=(7.2, 4.6))
        ax.plot(x_values, complexity_means, marker="o", linewidth=2.2, color="#2563eb", label="complexity_score")
        ax.plot(x_values, signal_means, marker="s", linewidth=2.2, color="#dc2626", label="complexity CFS 强度")
        ax.axhline(0.35, color="#6b7280", linestyle="--", linewidth=1.2, label="发散模式上界")
        ax.axhline(0.65, color="#111827", linestyle=":", linewidth=1.2, label="聚焦模式下界")
        ax.set_xlabel("源状态对象数")
        ax.set_ylabel("分数 / 强度")
        ax.set_title("E07 复杂度状态到 complexity 信号的白箱过渡")
        ax.set_xticks(x_values)
        ax.set_ylim(0.0, 1.05)
        ax.grid(alpha=0.22)
        ax.legend(loc="best", frameon=False)
        fig.tight_layout()
        path = CHART_DIR / f"e07_attention_complexity_source_transition_{stamp}.png"
        fig.savefig(path, dpi=180, bbox_inches="tight")
        plt.close(fig)
        paths.append(path)

    branch_order = ["low", "mid", "high"]
    branch_labels = {"low": "低复杂分支", "mid": "中间静默分支", "high": "高复杂分支"}
    top_n_means = []
    cam_means = []
    budget_means = []
    for branch in branch_order:
        rows = [row for row in probe_rows if str(row.get("branch", "")) == branch]
        top_n_means.append(mean_or_zero([num(row, "attention_top_n") for row in rows]))
        cam_means.append(mean_or_zero([num(row, "cam_item_count") for row in rows]))
        budget_means.append(mean_or_zero([num(row, "attention_energy_budget") for row in rows]))
    if any(top_n_means):
        fig, axes = plt.subplots(1, 3, figsize=(11.6, 4.1))
        x = range(len(branch_order))
        labels = [branch_labels[key] for key in branch_order]
        for ax, values, title, color in [
            (axes[0], top_n_means, "下一拍 attention.top_n", "#2563eb"),
            (axes[1], cam_means, "下一拍 CAM 条目数", "#16a34a"),
            (axes[2], budget_means, "下一拍注意力能量预算", "#dc2626"),
        ]:
            ax.bar(list(x), values, color=color, alpha=0.88)
            ax.set_xticks(list(x), labels, rotation=12)
            ax.set_title(title)
            ax.grid(axis="y", alpha=0.22)
        fig.suptitle("E07 统一 probe 池上的下一拍注意力差异", fontsize=12)
        fig.tight_layout()
        path = CHART_DIR / f"e07_attention_complexity_probe_contrast_{stamp}.png"
        fig.savefig(path, dpi=180, bbox_inches="tight")
        plt.close(fig)
        paths.append(path)

    return paths


def write_design_note(path: Path) -> None:
    lines = [
        "# E07 设计逻辑",
        "",
        "本实验把 E07 收窄为一条当前实现已经具备的白箱闭环，并按两个层次验证：",
        "",
        "1. 源状态层：直接在状态池插入平衡 ER/EV 的运行态结构，控制对象数而不引入额外奖惩与高认知压干扰；",
        "2. 下一拍 probe 层：把源状态生成的 `modulation_out.attention` 原样注入统一 probe 池，观察下一拍 CAM 容量与注意力预算差异。",
        "",
        "源状态层使用 4 / 8 / 10 / 12 / 16 个对象的五档构型，形成“低复杂 -> 中间静默 -> 高复杂”的过渡区间。",
        "低复杂分支应稳定触发 `attention_diverge_mode`，高复杂分支应稳定触发 `attention_focus_mode`，中间分支应保持静默。",
        "",
        "probe 层不再依赖自然语言内容差异，而是只比较下一拍注意力模式本身的作用，从而把因果链收窄到：",
        "",
        "    complexity 状态 -> complexity CFS -> attention mode -> next-tick CAM 差异",
        "",
        "这个设计避免把“复杂文本是否更像人”与“复杂度调制链路是否存在”混写在一起，便于复核与反驳。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    *,
    source_rows: list[dict[str, Any]],
    probe_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    charts: list[Path],
    stamp: str,
) -> Path:
    lines: list[str] = []
    lines.append(f"# E07 复杂度与注意力调制报告（{stamp}）")
    lines.append("")
    lines.append("## 核心结论")
    lines.append("")
    lines.append(f"- 支持等级：**{summary.get('support_level', 'unknown')}**")
    lines.append(f"- 源状态样本数：{int(summary.get('source_case_count', 0))}")
    lines.append(f"- 低复杂分支触发发散模式比例：{summary.get('source_low_diverge_ratio', 0.0):.3f}")
    lines.append(f"- 中间分支保持静默比例：{summary.get('source_mid_quiet_ratio', 0.0):.3f}")
    lines.append(f"- 高复杂分支触发聚焦模式比例：{summary.get('source_high_focus_ratio', 0.0):.3f}")
    lines.append(
        "- 源状态复杂度均值（低/中/高）："
        f"{summary.get('source_complexity_low_mean', 0.0):.4f} / "
        f"{summary.get('source_complexity_mid_mean', 0.0):.4f} / "
        f"{summary.get('source_complexity_high_mean', 0.0):.4f}"
    )
    lines.append(f"- probe pair 数：{int(summary.get('probe_pair_count', 0))}")
    lines.append(f"- 统一 probe 池容量顺序通过比例：{summary.get('probe_ordered_capacity_ratio', 0.0):.3f}")
    lines.append(f"- 统一 probe 池预算顺序通过比例：{summary.get('probe_ordered_budget_ratio', 0.0):.3f}")
    lines.append(f"- 统一 probe 池整体通过比例：{summary.get('probe_all_ok_ratio', 0.0):.3f}")
    lines.append(f"- 统一 probe 池整体符号检验 p 值：{summary.get('probe_all_ok_sign_p', 1.0):.8f}")
    lines.append("")
    lines.append("## 正文可使用的最小命题")
    lines.append("")
    lines.append(
        "在受控白箱条件下，AP 当前原型中的复杂度状态已经可以稳定沿着 "
        "`complexity_score -> complexity CFS -> attention_focus_mode / attention_diverge_mode "
        "-> 下一拍注意力调制` 这条链传播，并在统一 probe 池上表现为可复现的 "
        "`top_n`、`cam_item_count` 与 `attention_energy_budget` 差异。"
    )
    lines.append("")
    lines.append("## 关键均值")
    lines.append("")
    lines.append(
        "- 下一拍 top_n 均值（低/中/高）："
        f"{summary.get('probe_low_branch_top_n_mean', 0.0):.2f} / "
        f"{summary.get('probe_mid_branch_top_n_mean', 0.0):.2f} / "
        f"{summary.get('probe_high_branch_top_n_mean', 0.0):.2f}"
    )
    lines.append(
        "- 下一拍注意力预算均值（低/中/高）："
        f"{summary.get('probe_low_branch_budget_mean', 0.0):.2f} / "
        f"{summary.get('probe_mid_branch_budget_mean', 0.0):.2f} / "
        f"{summary.get('probe_high_branch_budget_mean', 0.0):.2f}"
    )
    lines.append(f"- 低高分支 top_n 均值差：{summary.get('probe_low_high_top_n_gap_mean', 0.0):.2f}")
    lines.append(f"- 低高分支 CAM 条目数均值差：{summary.get('probe_low_high_cam_gap_mean', 0.0):.2f}")
    lines.append(f"- 高低分支预算均值差：{summary.get('probe_high_low_budget_gap_mean', 0.0):.2f}")
    lines.append("")
    lines.append("## 图表")
    lines.append("")
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    lines.append("## 备注")
    lines.append("")
    lines.append("- 本实验故意不使用自然语言课程样本作为主要证据，因为那类样本会混入更多旁路机制。")
    lines.append("- 本实验也不把“复杂文本更像人”作为已证结论；正文只保留当前实现已经稳固支撑的最小白箱命题。")
    lines.append("")
    path = REPORT_DIR / f"E07_attention_complexity_report_{stamp}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_experiment(*, stamp: str, family_count: int) -> dict[str, Any]:
    ensure_dirs()
    families = PAIR_FAMILIES[: max(1, min(int(family_count), len(PAIR_FAMILIES)))]

    source_rows: list[dict[str, Any]] = []
    probe_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []

    for family in families:
        family_modulations: dict[str, dict[str, Any]] = {}
        family_source_rows: dict[str, dict[str, Any]] = {}
        for spec in SOURCE_SPECS:
            row, modulation = run_source_case(family=family, spec=spec)
            source_rows.append(row)
            family_source_rows[spec.case_id] = row
            family_modulations[spec.case_id] = dict(modulation)

        low_probe = run_probe_case(family=family, branch="low", modulation=family_modulations["S04"])
        mid_probe = run_probe_case(family=family, branch="mid", modulation=family_modulations["S10"])
        high_probe = run_probe_case(family=family, branch="high", modulation=family_modulations["S16"])
        probe_rows.extend([low_probe, mid_probe, high_probe])

        pair_rows.append(
            {
                "family": family,
                "baseline_conforms_source": int(
                    min(
                        int(family_source_rows["S04"].get("baseline_conforms", 0) or 0),
                        int(family_source_rows["S10"].get("baseline_conforms", 0) or 0),
                        int(family_source_rows["S16"].get("baseline_conforms", 0) or 0),
                    )
                ),
                "baseline_conforms_probe": int(
                    min(
                        int(low_probe.get("baseline_conforms", 0) or 0),
                        int(mid_probe.get("baseline_conforms", 0) or 0),
                        int(high_probe.get("baseline_conforms", 0) or 0),
                    )
                ),
                "low_source_ok": int(family_source_rows["S04"].get("mode_expected_pass", 0) or 0),
                "mid_source_ok": int(family_source_rows["S10"].get("mode_expected_pass", 0) or 0),
                "high_source_ok": int(family_source_rows["S16"].get("mode_expected_pass", 0) or 0),
                "low_probe_ok": int(
                    str(low_probe.get("modulation_input_reason", "") or "") == "attention_diverge_mode"
                    and int(low_probe.get("attention_top_n", 0) or 0) == 21
                    and int(low_probe.get("cam_item_count", 0) or 0) == 21
                    and abs(float(low_probe.get("attention_energy_budget", 0.0) or 0.0) - 6.0) <= 1e-6
                ),
                "mid_probe_ok": int(
                    str(mid_probe.get("modulation_input_reason", "") or "") == ""
                    and int(mid_probe.get("attention_top_n", 0) or 0) == 16
                    and int(mid_probe.get("cam_item_count", 0) or 0) == 16
                    and abs(float(mid_probe.get("attention_energy_budget", 0.0) or 0.0) - 8.0) <= 1e-6
                ),
                "high_probe_ok": int(
                    str(high_probe.get("modulation_input_reason", "") or "") == "attention_focus_mode"
                    and int(high_probe.get("attention_top_n", 0) or 0) == 11
                    and int(high_probe.get("cam_item_count", 0) or 0) == 11
                    and abs(float(high_probe.get("attention_energy_budget", 0.0) or 0.0) - 10.0) <= 1e-6
                ),
                "ordered_capacity_ok": int(
                    int(high_probe.get("cam_item_count", 0) or 0)
                    < int(mid_probe.get("cam_item_count", 0) or 0)
                    < int(low_probe.get("cam_item_count", 0) or 0)
                ),
                "ordered_budget_ok": int(
                    float(low_probe.get("attention_energy_budget", 0.0) or 0.0)
                    < float(mid_probe.get("attention_energy_budget", 0.0) or 0.0)
                    < float(high_probe.get("attention_energy_budget", 0.0) or 0.0)
                ),
                "low_high_top_n_gap": int(low_probe.get("attention_top_n", 0) or 0) - int(high_probe.get("attention_top_n", 0) or 0),
                "low_high_cam_gap": int(low_probe.get("cam_item_count", 0) or 0) - int(high_probe.get("cam_item_count", 0) or 0),
                "high_low_budget_gap": round(
                    float(high_probe.get("attention_energy_budget", 0.0) or 0.0)
                    - float(low_probe.get("attention_energy_budget", 0.0) or 0.0),
                    8,
                ),
            }
        )

    for row in pair_rows:
        row["all_ok"] = int(
            int(row.get("baseline_conforms_source", 0) or 0) == 1
            and int(row.get("baseline_conforms_probe", 0) or 0) == 1
            and int(row.get("low_source_ok", 0) or 0) == 1
            and int(row.get("mid_source_ok", 0) or 0) == 1
            and int(row.get("high_source_ok", 0) or 0) == 1
            and int(row.get("low_probe_ok", 0) or 0) == 1
            and int(row.get("mid_probe_ok", 0) or 0) == 1
            and int(row.get("high_probe_ok", 0) or 0) == 1
            and int(row.get("ordered_capacity_ok", 0) or 0) == 1
            and int(row.get("ordered_budget_ok", 0) or 0) == 1
        )

    source_rows.sort(key=lambda row: (str(row["family"]), int(row["item_count"])))
    probe_rows.sort(key=lambda row: (str(row["family"]), str(row["branch"])))
    pair_rows.sort(key=lambda row: str(row["family"]))

    summary = summarize_evidence(source_rows=source_rows, probe_rows=probe_rows, pair_rows=pair_rows)
    e01.write_csv(TABLE_DIR / f"e07_attention_complexity_source_rows_{stamp}.csv", source_rows)
    e01.write_csv(TABLE_DIR / f"e07_attention_complexity_probe_rows_{stamp}.csv", probe_rows)
    e01.write_csv(TABLE_DIR / f"e07_attention_complexity_pair_rows_{stamp}.csv", pair_rows)
    e01.write_json(TABLE_DIR / f"e07_attention_complexity_summary_{stamp}.json", summary)
    write_design_note(REPORT_DIR / "E07_attention_complexity_design_logic.md")
    charts = make_charts(source_rows=source_rows, probe_rows=probe_rows, stamp=stamp)
    report = write_report(
        source_rows=source_rows,
        probe_rows=probe_rows,
        pair_rows=pair_rows,
        summary=summary,
        charts=charts,
        stamp=stamp,
    )
    evidence = {
        "experiment_id": "E07",
        "stamp": stamp,
        "support_level": summary.get("support_level", "unknown"),
        "summary": summary,
        "artifacts": {
            "source_rows": str(TABLE_DIR / f"e07_attention_complexity_source_rows_{stamp}.csv"),
            "probe_rows": str(TABLE_DIR / f"e07_attention_complexity_probe_rows_{stamp}.csv"),
            "pair_rows": str(TABLE_DIR / f"e07_attention_complexity_pair_rows_{stamp}.csv"),
            "summary": str(TABLE_DIR / f"e07_attention_complexity_summary_{stamp}.json"),
            "report": str(report),
            "design_note": str(REPORT_DIR / "E07_attention_complexity_design_logic.md"),
            "charts": [str(path) for path in charts],
        },
    }
    e01.write_json(MANIFEST_DIR / f"E07_attention_complexity_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E07_attention_complexity_latest.json", evidence)
    return evidence


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper E07 attention-complexity experiment.")
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
