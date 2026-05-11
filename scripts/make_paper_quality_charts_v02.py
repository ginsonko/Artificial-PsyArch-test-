from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import run_paper_e01_experiment as e01


ROOT = Path(__file__).resolve().parent
ARTIFACT_ROOT = ROOT / "docs" / "paper_artifacts_2026-05-11"
OUT_DIR = ARTIFACT_ROOT / "paper_quality_charts_v02"
DATA_DIR = OUT_DIR / "data"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def fnum(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        out = float(value)
        if math.isfinite(out):
            return out
        return default
    except Exception:
        return default


def mean(values: list[float]) -> float:
    clean = [float(v) for v in values if math.isfinite(float(v))]
    return sum(clean) / len(clean) if clean else 0.0


def count_rows(path: Path) -> int:
    return len(read_csv(path))


def summary_value(data: dict[str, Any], keys: list[str], default: float = 0.0) -> float:
    for key in keys:
        if key in data:
            return fnum(data.get(key), default)
    return default


def load_final_summaries(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {
        "E01": read_json(paths["E01_SUMMARY"]),
        "E02": read_json(paths["E02_SUMMARY"]),
        "E03": read_json(paths["E03_SUMMARY"]),
        "E06": read_json(paths["E06_SUMMARY"]),
        "E07": read_json(paths["E07_SUMMARY"]),
    }
    for eid in range(4, 18):
        if f"E{eid:02d}" in out:
            continue
        candidates = sorted(ARTIFACT_ROOT.glob(f"E{eid:02d}_*/tables/*summary*final_v*.json"))
        if eid == 12:
            candidates = [p for p in candidates if "final_v2" in p.name]
        if candidates:
            out[f"E{eid:02d}"] = read_json(candidates[-1])
    return out


def experiment_overview_rows(paths: dict[str, Path]) -> list[dict[str, Any]]:
    summaries = load_final_summaries(paths)
    return [
        {
            "id": "E01",
            "domain": "结构学习",
            "claim": "历史顺序改变后续同序输入的结构复用成本",
            "n": int(fnum(summaries["E01"].get("n"), 0)),
            "effect": fnum(summaries["E01"].get("ordered_probe_advantage_mean")),
            "effect_label": "同序 probe 存储优势",
            "control": "同字符乱序历史",
            "support": summaries["E01"].get("support_level", ""),
        },
        {
            "id": "E02",
            "domain": "结构学习",
            "claim": "稳定句壳中的局部替换会触发可测结构生长",
            "n": int(fnum(summaries["E02"].get("pair_count"), count_rows(paths["E02_PAIR"]))),
            "effect": fnum(summaries["E02"].get("metrics", {}).get("hdb_structure_count", {}).get("mean_diff")),
            "effect_label": "结构数差",
            "control": "完全重复句壳",
            "support": summaries["E02"].get("support_level", ""),
        },
        {
            "id": "E03",
            "domain": "反馈与行动",
            "claim": "教师奖惩能写入局部上下文并在弱 probe 中重放",
            "n": int(fnum(summaries["E03"].get("pair_count"), count_rows(paths["E03_PAIR"]))),
            "effect": fnum(summaries["E03"].get("reward_bonus_effect_mean")),
            "effect_label": "奖励局部效应",
            "control": "中性历史",
            "support": summaries["E03"].get("support_level", ""),
        },
        {
            "id": "E04",
            "domain": "反馈与行动",
            "claim": "先惩罚错误目标、再奖励正确目标会形成双向纠偏",
            "n": int(fnum(summaries["E04"].get("pair_count"), count_rows(paths["E04_PAIR"]))),
            "effect": fnum(summaries["E04"].get("corrected_total_local_signal_mean")),
            "effect_label": "纠偏局部信号",
            "control": "中性目标",
            "support": summaries["E04"].get("support_level", ""),
        },
        {
            "id": "E05",
            "domain": "反馈与行动",
            "claim": "真实执行过的行动会留下可复用行动准备痕迹",
            "n": int(fnum(summaries["E05"].get("pair_count"), count_rows(paths["E05_PAIR"]))),
            "effect": fnum(summaries["E05"].get("probe_drive_advantage_mean")),
            "effect_label": "弱 probe drive 优势",
            "control": "只见过弱文本",
            "support": summaries["E05"].get("support_level", ""),
        },
        {
            "id": "E06",
            "domain": "时间与注意",
            "claim": "时间间隔感受可注册、到期并回投到目标对象",
            "n": int(fnum(summaries["E06"].get("integrated_pair_count"), count_rows(paths["E06_PAIR"]))),
            "effect": fnum(summaries["E06"].get("integrated_pair_contrast_ratio")),
            "effect_label": "成对闭环通过率",
            "control": "关闭延迟通道",
            "support": summaries["E06"].get("support_level", ""),
        },
        {
            "id": "E07",
            "domain": "时间与注意",
            "claim": "复杂度状态能调制下一拍注意力容量与预算",
            "n": int(fnum(summaries["E07"].get("probe_case_count"), count_rows(paths["E07_PAIR"]))),
            "effect": fnum(summaries["E07"].get("probe_high_low_budget_gap_mean")),
            "effect_label": "高低预算差",
            "control": "低/中复杂度分支",
            "support": summaries["E07"].get("support_level", ""),
        },
        {
            "id": "E08",
            "domain": "时间与注意",
            "claim": "时间显影下残差记忆只在种子和线索同时满足时晋升",
            "n": int(fnum(summaries["E08"].get("case_count"), count_rows(paths["E08_PAIR"]))),
            "effect": fnum(summaries["E08"].get("on_matched_selected_promoted_ratio")),
            "effect_label": "匹配晋升率",
            "control": "无种子/无线索/关闭通道",
            "support": summaries["E08"].get("support_level", ""),
        },
        {
            "id": "E09",
            "domain": "自我状态",
            "claim": "恢复类认知感受能按条件分层出现",
            "n": int(fnum(summaries["E09"].get("case_count"), count_rows(paths["E09_PAIR"]))),
            "effect": fnum(summaries["E09"].get("relief_strength_mean")),
            "effect_label": "缓解信号强度",
            "control": "高复杂/高惩罚/低把握阻断",
            "support": summaries["E09"].get("support_level", ""),
        },
        {
            "id": "E10",
            "domain": "自我状态",
            "claim": "重复调节区分短期疲劳、变体和恢复后再出现",
            "n": int(fnum(summaries["E10"].get("family_count"), count_rows(paths["E10_PAIR"]))),
            "effect": fnum(summaries["E10"].get("same_penalty_mean")),
            "effect_label": "同项重复惩罚",
            "control": "变体/恢复/低重复",
            "support": summaries["E10"].get("support_level", ""),
        },
        {
            "id": "E11",
            "domain": "能量图景",
            "claim": "感应能量会形成有限深度扩散并受阈值剪枝约束",
            "n": int(fnum(summaries["E11"].get("case_count"), count_rows(paths["E11_PAIR"]))),
            "effect": fnum(summaries["E11"].get("deep_depth_mean")),
            "effect_label": "深扩散最大深度",
            "control": "单轮/高阈值/宽度上限",
            "support": summaries["E11"].get("support_level", ""),
        },
        {
            "id": "E12",
            "domain": "能量图景",
            "claim": "结构承担过程态，记忆承担目标态与审计锚点",
            "n": int(fnum(summaries["E12"].get("case_count"), count_rows(paths["E12_PAIR"]))),
            "effect": fnum(summaries["E12"].get("converge_hit_count_mean")),
            "effect_label": "记忆汇聚命中数",
            "control": "分离记忆/衰减分支",
            "support": summaries["E12"].get("support_level", ""),
        },
        {
            "id": "E13",
            "domain": "Agent 接入",
            "claim": "AP 投影比摘要/RAG更能保留可审计上下文字段",
            "n": int(fnum(summaries["E13"].get("family_count"), count_rows(paths["E13_FAMILY"]))),
            "effect": fnum(summaries["E13"].get("ap_advantage_vs_rag_mean")),
            "effect_label": "AP 对 RAG 优势",
            "control": "摘要与关键词检索",
            "support": summaries["E13"].get("support_level", ""),
        },
        {
            "id": "E14",
            "domain": "行动调制",
            "claim": "奖惩状态改变全局阈值，局部奖惩改变目标驱动力",
            "n": int(fnum(summaries["E14"].get("case_count"), count_rows(paths["E14_FAMILY"]))),
            "effect": abs(fnum(summaries["E14"].get("reward_threshold_delta_vs_baseline_mean"))),
            "effect_label": "奖励阈值下降幅度",
            "control": "固定阈值/局部关闭",
            "support": summaries["E14"].get("support_level", ""),
        },
        {
            "id": "E15",
            "domain": "自适应调参",
            "claim": "自适应调参器按运行状态给出方向稳定的参数调整",
            "n": int(fnum(summaries["E15"].get("case_count"), count_rows(paths["E15_FAMILY"]))),
            "effect": fnum(summaries["E15"].get("cam_delta_overheat_mean")),
            "effect_label": "过热 CAM 预算调整",
            "control": "健康静默/禁用调参",
            "support": summaries["E15"].get("support_level", ""),
        },
        {
            "id": "E16",
            "domain": "接地入口",
            "claim": "多来源属性能作为可审计对象进入状态池并保持锚点隔离",
            "n": int(fnum(summaries["E16"].get("case_count"), count_rows(paths["E16_FAMILY"]))),
            "effect": fnum(summaries["E16"].get("packet_attr_item_present_ratio_mean")),
            "effect_label": "属性入池保真率",
            "control": "错误锚点/折叠属性/非法角色",
            "support": summaries["E16"].get("support_level", ""),
        },
        {
            "id": "E17",
            "domain": "内部叙事链",
            "claim": "上一拍高能候选能承接为下一拍 source 并推动候选链续写",
            "n": int(fnum(summaries["E17"].get("step_count"), count_rows(paths["E17_FAMILY"]))),
            "effect": fnum(summaries["E17"].get("chain_carry_ratio_mean")),
            "effect_label": "跨拍承接率",
            "control": "错误种子/低预算/无承接/终端记忆",
            "support": summaries["E17"].get("support_level", ""),
        },
    ]


def setup_axes():
    plt = e01.setup_matplotlib()
    plt.rcParams["axes.titleweight"] = "bold"
    plt.rcParams["axes.labelcolor"] = "#334155"
    plt.rcParams["xtick.color"] = "#334155"
    plt.rcParams["ytick.color"] = "#334155"
    plt.rcParams["axes.edgecolor"] = "#cbd5e1"
    plt.rcParams["figure.facecolor"] = "white"
    return plt


def save_json(name: str, data: Any) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def final_paths() -> dict[str, Path]:
    r = ARTIFACT_ROOT
    return {
        "E01_SUMMARY": r / "E01_lexical_abstraction/strong_reuse_v4_crossover_probe/tables/e01_v4_crossover_evidence_summary_smoke3_20260511_e01_v4_crossover_f2.json",
        "E01_FAMILY": r / "E01_lexical_abstraction/strong_reuse_v4_crossover_probe/tables/e01_v4_crossover_family_evidence_smoke3_20260511_e01_v4_crossover_f2.csv",
        "E02_SUMMARY": r / "E02_label_switch_sensitivity/tables/e02_label_switch_summary_e02_label_switch_holdout_confirm_v1.json",
        "E02_PAIR": r / "E02_label_switch_sensitivity/tables/e02_label_switch_pair_rows_e02_label_switch_holdout_confirm_v1.csv",
        "E03_SUMMARY": r / "E03_reward_shaping/tables/e03_reward_shaping_summary_e03_final_v1.json",
        "E03_PAIR": r / "E03_reward_shaping/tables/e03_reward_shaping_pair_rows_e03_final_v1.csv",
        "E04_PAIR": r / "E04_punish_correction/tables/e04_punish_correction_pair_rows_e04_final_v1.csv",
        "E05_PAIR": r / "E05_action_closure/tables/e05_action_closure_pair_rows_e05_final_v1.csv",
        "E06_SUMMARY": r / "E06_time_interval_closure/tables/e06_time_interval_summary_e06_final_v1.json",
        "E06_PAIR": r / "E06_time_interval_closure/tables/e06_time_interval_pair_rows_e06_final_v1.csv",
        "E07_SUMMARY": r / "E07_attention_complexity/tables/e07_attention_complexity_summary_e07_final_v1.json",
        "E07_PAIR": r / "E07_attention_complexity/tables/e07_attention_complexity_pair_rows_e07_final_v1.csv",
        "E08_PAIR": r / "E08_time_like_residual_promotion/tables/e08_time_like_residual_promotion_pair_rows_e08_final_v1.csv",
        "E09_PAIR": r / "E09_conflict_relief/tables/e09_conflict_relief_pair_rows_e09_final_v1.csv",
        "E10_PAIR": r / "E10_repeat_fatigue/tables/e10_repeat_fatigue_pair_rows_e10_final_v1.csv",
        "E11_PAIR": r / "E11_energy_graph/tables/e11_energy_graph_pair_rows_e11_final_v1.csv",
        "E12_PAIR": r / "E12_process_memory_state/tables/e12_process_memory_pair_rows_e12_final_v2.csv",
        "E13_FAMILY": r / "E13_agent_memory_projection/tables/e13_agent_memory_projection_family_rows_e13_final_v1.csv",
        "E14_FAMILY": r / "E14_action_threshold_modulation/tables/e14_action_threshold_modulation_family_rows_e14_final_v1.csv",
        "E15_FAMILY": r / "E15_auto_tuner_stability/tables/e15_auto_tuner_stability_family_rows_e15_final_v1.csv",
        "E16_FAMILY": r / "E16_multimodal_symbol_grounding/tables/e16_multimodal_symbol_grounding_family_rows_e16_final_v1.csv",
        "E17_FAMILY": r / "E17_internal_narrative_chain/tables/e17_internal_narrative_chain_family_rows_e17_final_v1.csv",
    }


def chart_evidence_map(plt, paths: dict[str, Path]) -> Path:
    rows = experiment_overview_rows(paths)
    domain_order = ["结构学习", "反馈与行动", "时间与注意", "自我状态", "能量图景", "Agent 接入", "行动调制", "自适应调参", "接地入口", "内部叙事链"]
    colors = {
        "结构学习": "#2563eb",
        "反馈与行动": "#16a34a",
        "时间与注意": "#0f766e",
        "自我状态": "#8b5cf6",
        "能量图景": "#f59e0b",
        "Agent 接入": "#64748b",
        "行动调制": "#dc2626",
        "自适应调参": "#0891b2",
        "接地入口": "#7c3aed",
        "内部叙事链": "#1d4ed8",
    }
    fig = plt.figure(figsize=(13.8, 10.4))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 2.4], width_ratios=[1.15, 0.85])
    ax0 = fig.add_subplot(gs[0, 0])
    ax0b = fig.add_subplot(gs[0, 1])
    ax1 = fig.add_subplot(gs[1, :])

    domain_counts = {domain: 0 for domain in domain_order}
    domain_cases = {domain: 0 for domain in domain_order}
    for row in rows:
        domain_counts[row["domain"]] += 1
        domain_cases[row["domain"]] += int(row["n"])
    domains = [d for d in domain_order if domain_counts[d]]
    top_domains = list(reversed(domains))
    ax0.barh(top_domains, [domain_counts[d] for d in top_domains], color=[colors[d] for d in top_domains], height=0.58)
    ax0.set_xlabel("实验数")
    ax0.set_title("机制覆盖")
    ax0.grid(axis="x", alpha=0.22)
    ax0.set_xlim(0, max(domain_counts.values()) + 0.8)
    for y_idx, d in enumerate(top_domains):
        ax0.text(domain_counts[d] + 0.06, y_idx, f"{domain_counts[d]} 项", ha="left", va="center", fontsize=9, color="#334155")

    ax0b.barh(top_domains, [domain_cases[d] for d in top_domains], color=[colors[d] for d in top_domains], height=0.58)
    ax0b.set_title("判据记录规模")
    ax0b.set_xlabel("family/case/pair/step 数")
    ax0b.grid(axis="x", alpha=0.22)
    for y_idx, d in enumerate(top_domains):
        ax0b.text(domain_cases[d] + max(domain_cases.values()) * 0.015, y_idx, f"{domain_cases[d]}", va="center", fontsize=8.8, color="#334155")

    display_rows = list(reversed(rows))
    y_pos = list(range(len(display_rows)))
    sample_sizes = [max(1, int(r["n"])) for r in display_rows]
    sample_log = [math.log10(v + 1) for v in sample_sizes]
    ax1.barh(y_pos, sample_log, color=[colors[r["domain"]] for r in display_rows], height=0.64, alpha=0.88)
    ax1.set_yticks(y_pos, [f"{r['id']}  {r['domain']}" for r in display_rows])
    ax1.set_xlabel("判据记录规模（log10 后显示，避免少量大样本压扁小样本）")
    ax1.set_title("强证据实验目录：每一行对应一个机制命题、一个对照设计和一个代表性结果")
    ax1.grid(axis="x", alpha=0.18)
    max_x = max(sample_log) if sample_log else 1.0
    ax1.set_xlim(0, max_x + 1.95)
    for y, row, width, raw_n in zip(y_pos, display_rows, sample_log, sample_sizes):
        effect = row["effect"]
        effect_text = f"{row['effect_label']}={effect:.3g}"
        ax1.text(width + 0.04, y, f"n={raw_n}；{effect_text}；对照：{row['control']}", va="center", fontsize=8.3, color="#334155")
        ax1.text(0.03, y, row["id"], va="center", ha="left", fontsize=8.8, color="white", fontweight="bold")
    fig.suptitle("E01-E17 定向实验总览：从机制预测到可复现证据", fontsize=16, fontweight="bold", color="#0f172a", y=0.985)
    fig.tight_layout()
    path = OUT_DIR / "pq_00_evidence_map.png"
    fig.savefig(path, dpi=230, bbox_inches="tight")
    plt.close(fig)
    save_json("pq_00_evidence_map.json", rows)
    return path


def chart_experiment_logic_flow(plt, paths: dict[str, Path]) -> Path:
    rows = experiment_overview_rows(paths)
    fig, ax = plt.subplots(figsize=(13.4, 4.6))
    ax.axis("off")
    steps = [
        ("机制预测", "先从 AP 闭环推出一个可观察差异"),
        ("最小数据集", "只保留能触发该机制的必要变量"),
        ("对照与消融", "让输入文本、起点或参数尽量可比"),
        ("真实模块运行", "调用原型中的状态池、HDB、行动或调参链路"),
        ("判据", "结果必须方向一致、可追溯、可复现"),
        ("正文准入", "只保留强证据，pilot 与失败扫描进入附件"),
    ]
    x0, y0, w, h, gap = 0.03, 0.48, 0.14, 0.28, 0.025
    for idx, (title, subtitle) in enumerate(steps):
        x = x0 + idx * (w + gap)
        box = plt.Rectangle((x, y0), w, h, facecolor="#f8fafc", edgecolor="#20324A", linewidth=1.25, transform=ax.transAxes)
        ax.add_patch(box)
        ax.text(x + w / 2, y0 + h * 0.64, title, transform=ax.transAxes, ha="center", va="center", fontsize=12, color="#20324A", fontweight="bold")
        ax.text(x + w / 2, y0 + h * 0.32, subtitle, transform=ax.transAxes, ha="center", va="center", fontsize=8.7, color="#475569", wrap=True)
        if idx < len(steps) - 1:
            ax.annotate("", xy=(x + w + gap * 0.72, y0 + h / 2), xytext=(x + w + gap * 0.12, y0 + h / 2), xycoords=ax.transAxes, arrowprops=dict(arrowstyle="->", color="#334155", linewidth=1.4))
    domain_lines = [
        "结构学习：E01-E02",
        "反馈与行动：E03-E05",
        "时间与注意：E06-E08",
        "自我状态与能量图景：E09-E12",
        "Agent、行动、接地、内部候选链：E13-E17",
    ]
    ax.text(0.03, 0.26, "本组实验不是把一组通用日志反复作图，而是把 17 个机制命题分别压缩成最小可检验链路。", transform=ax.transAxes, ha="left", va="center", fontsize=11.2, color="#0f172a")
    ax.text(0.03, 0.13, "；".join(domain_lines), transform=ax.transAxes, ha="left", va="center", fontsize=10, color="#334155")
    ax.text(0.03, 0.03, f"最终纳入正文的判据对象合计约 {sum(int(r['n']) for r in rows)} 条 family/case/pair/step 记录；详细 CSV、JSON、报告与图表均在附件仓库中逐项归档。", transform=ax.transAxes, ha="left", va="center", fontsize=9.4, color="#475569")
    path = OUT_DIR / "pq_00b_experiment_logic_flow.png"
    fig.savefig(path, dpi=230, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_e01_e02(plt, paths: dict[str, Path]) -> Path:
    e01s = read_json(paths["E01_SUMMARY"])
    e02s = read_json(paths["E02_SUMMARY"])
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.8))
    labels1 = ["同序历史\n存储节省", "乱序 probe\n反向优势", "历史特异性\n通过率"]
    vals1 = [
        fnum(e01s.get("ordered_probe_advantage_mean")),
        fnum(e01s.get("permuted_probe_advantage_mean")),
        fnum(e01s.get("pass_history_specificity_rate")),
    ]
    colors1 = ["#2563eb", "#64748b", "#16a34a"]
    ax1.bar(labels1, vals1, color=colors1)
    ax1.set_title("E01：历史结构复用不是泛化错觉")
    ax1.set_ylabel("节省量 / 通过率")
    ax1.grid(axis="y", alpha=0.22)
    metrics = e02s.get("metrics", {})
    labels2 = ["新 identity", "结构数", "残差写入", "记忆引用"]
    vals2 = [
        fnum(metrics.get("induction_growth_identity_created_count", {}).get("mean_diff")),
        fnum(metrics.get("hdb_structure_count", {}).get("mean_diff")),
        fnum(metrics.get("hdb_residual_diff_entry_count", {}).get("mean_diff")),
        fnum(metrics.get("hdb_diff_entry_with_memory_ref_count", {}).get("mean_diff")),
    ]
    ax2.bar(labels2, vals2, color="#f59e0b")
    ax2.set_title("E02：标签替换带来可测结构生长成本")
    ax2.set_ylabel("switch - repeat 均值差")
    ax2.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = OUT_DIR / "pq_01_structure_reuse_and_growth.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_reward_action(plt, paths: dict[str, Path]) -> Path:
    e03 = read_csv(paths["E03_PAIR"])
    e04 = read_csv(paths["E04_PAIR"])
    e05 = read_csv(paths["E05_PAIR"])
    fig, axes = plt.subplots(1, 3, figsize=(14.4, 4.8))
    e03_vals = [
        mean([fnum(r.get("reward_probe_drive")) for r in e03]),
        mean([fnum(r.get("neutral_probe_drive")) for r in e03]),
        mean([fnum(r.get("punish_probe_drive")) for r in e03]),
    ]
    axes[0].bar(["奖励历史", "中性", "惩罚历史"], e03_vals, color=["#16a34a", "#94a3b8", "#dc2626"])
    axes[0].set_title("E03：教师反馈改变后续行动准备")
    axes[0].set_ylabel("弱 probe 驱动力均值")
    e04_vals = [
        mean([fnum(r.get("corrected_right_reward_bonus")) for r in e04]),
        mean([fnum(r.get("corrected_wrong_punish_penalty")) for r in e04]),
        mean([fnum(r.get("neutral_right_reward_bonus")) for r in e04]),
    ]
    axes[1].bar(["正确目标\n奖励", "错误目标\n惩罚", "中性对照"], e04_vals, color=["#16a34a", "#dc2626", "#94a3b8"])
    axes[1].set_title("E04：纠偏把奖惩绑定到局部目标")
    axes[1].set_ylabel("局部信号均值")
    e05_vals = [
        mean([fnum(r.get("executed_probe_drive")) for r in e05]),
        mean([fnum(r.get("weak_probe_drive")) for r in e05]),
        mean([fnum(r.get("probe_drive_advantage")) for r in e05]),
    ]
    axes[2].bar(["执行历史", "弱历史", "优势"], e05_vals, color=["#2563eb", "#94a3b8", "#0f766e"])
    axes[2].set_title("E05：行动闭环留下可复用痕迹")
    axes[2].set_ylabel("probe 驱动力")
    for ax in axes:
        ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = OUT_DIR / "pq_02_feedback_action_chain.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_time_attention_memory(plt, paths: dict[str, Path]) -> Path:
    e06 = read_json(paths["E06_SUMMARY"])
    e07 = read_json(paths["E07_SUMMARY"])
    e08 = read_csv(paths["E08_PAIR"])
    fig, axes = plt.subplots(1, 3, figsize=(14.8, 4.8))
    axes[0].bar(["注册", "到期", "执行", "off静默"], [
        fnum(e06.get("integrated_on_registration_ratio")),
        fnum(e06.get("integrated_on_due3_ratio")),
        fnum(e06.get("integrated_on_exec3_ratio")),
        fnum(e06.get("integrated_off_quiet_ratio")),
    ], color=["#2563eb", "#0f766e", "#16a34a", "#64748b"])
    axes[0].set_title("E06：时间间隔到延迟回投")
    axes[0].set_ylim(0, 1.12)
    axes[1].bar(["低复杂度\n容量", "中复杂度\n容量", "高复杂度\n容量"], [
        fnum(e07.get("probe_low_branch_top_n_mean")),
        fnum(e07.get("probe_mid_branch_top_n_mean")),
        fnum(e07.get("probe_high_branch_top_n_mean")),
    ], color=["#38bdf8", "#94a3b8", "#1d4ed8"])
    ax1b = axes[1].twinx()
    ax1b.plot(["低复杂度\n容量", "中复杂度\n容量", "高复杂度\n容量"], [
        fnum(e07.get("probe_low_branch_budget_mean")),
        fnum(e07.get("probe_mid_branch_budget_mean")),
        fnum(e07.get("probe_high_branch_budget_mean")),
    ], marker="o", color="#dc2626", linewidth=2.0)
    axes[1].set_title("E07：复杂度调制下一拍注意")
    axes[1].set_ylabel("top_n")
    ax1b.set_ylabel("注意力预算")
    axes[2].bar(["匹配+seed+cue", "关闭晋升", "无seed", "无cue"], [
        mean([fnum(r.get("on_matched_selected_promoted_count")) for r in e08]),
        mean([fnum(r.get("off_matched_promoted_count")) for r in e08]),
        mean([fnum(r.get("on_no_seed_promoted_count")) for r in e08]),
        mean([fnum(r.get("on_no_cue_promoted_count")) for r in e08]),
    ], color=["#16a34a", "#64748b", "#f59e0b", "#dc2626"])
    axes[2].set_title("E08：残差记忆只在完整条件下晋升")
    axes[2].set_ylabel("晋升候选数均值")
    for ax in axes:
        ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = OUT_DIR / "pq_03_time_attention_memory.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_feeling_fatigue_energy(plt, paths: dict[str, Path]) -> Path:
    e09 = read_csv(paths["E09_PAIR"])
    e10 = read_csv(paths["E10_PAIR"])
    e11 = read_csv(paths["E11_PAIR"])
    fig, axes = plt.subplots(1, 3, figsize=(15.2, 4.8))
    axes[0].bar(["缓解", "正确感", "安心"], [
        mean([fnum(r.get("relief_strength")) for r in e09]),
        mean([fnum(r.get("correct_event_strength")) for r in e09]),
        mean([fnum(r.get("reassurance_strength")) for r in e09]),
    ], color=["#38bdf8", "#16a34a", "#0f766e"])
    axes[0].set_title("E09：恢复类认知感受分层出现")
    axes[0].set_ylabel("信号强度均值")
    axes[1].bar(["立刻重复", "上下文变体", "跳过恢复", "boredom"], [
        mean([fnum(r.get("same_penalty")) for r in e10]),
        mean([fnum(r.get("variant_penalty")) for r in e10]),
        mean([fnum(r.get("recovered_penalty")) for r in e10]),
        mean([fnum(r.get("boredom_on_strength")) for r in e10]),
    ], color=["#dc2626", "#94a3b8", "#f59e0b", "#8b5cf6"])
    axes[1].set_title("E10：重复调节区分疲劳与无聊")
    axes[1].set_ylabel("惩罚/感受强度")
    axes[2].bar(["多轮扩散", "单轮截断", "高前沿阈值", "高预算阈值"], [
        mean([fnum(r.get("deep_depth_max")) for r in e11]),
        mean([fnum(r.get("single_depth_max")) for r in e11]),
        mean([fnum(r.get("high_frontier_depth_max")) for r in e11]),
        mean([fnum(r.get("high_budget_depth_max")) for r in e11]),
    ], color=["#2563eb", "#64748b", "#f59e0b", "#dc2626"])
    axes[2].set_title("E11：能量扩散有深度也有边界")
    axes[2].set_ylabel("最大深度均值")
    for ax in axes:
        ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = OUT_DIR / "pq_04_feeling_fatigue_energy.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_memory_agent_tuning(plt, paths: dict[str, Path]) -> Path:
    e12 = read_csv(paths["E12_PAIR"])
    e13 = read_csv(paths["E13_FAMILY"])
    e15 = read_csv(paths["E15_FAMILY"])
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.8))
    axes[0].bar(["记忆汇聚\n命中", "来源数", "过程目标", "分离记忆"], [
        mean([fnum(r.get("converge_hit_count")) for r in e12]),
        mean([fnum(r.get("converge_source_count")) for r in e12]),
        mean([fnum(r.get("process_target_count")) for r in e12]),
        mean([fnum(r.get("split_memory_count")) for r in e12]),
    ], color=["#16a34a", "#0f766e", "#2563eb", "#f59e0b"])
    axes[0].set_title("E12：过程结构与记忆目标分工")
    axes[0].set_ylabel("条目数均值")
    axes[1].bar(["AP投影", "摘要", "关键词检索"], [
        mean([fnum(r.get("mean_ap_field_score")) for r in e13]),
        mean([fnum(r.get("mean_summary_field_score")) for r in e13]),
        mean([fnum(r.get("mean_rag_field_score")) for r in e13]),
    ], color=["#2563eb", "#94a3b8", "#f59e0b"])
    axes[1].set_title("E13：AP 作为 Agent 可审计上下文")
    axes[1].set_ylabel("字段覆盖均值")
    axes[2].bar(["沉寂\nER保留", "沉寂\nEV保留", "过热\nCAM", "EV传播", "ER诱发"], [
        mean([fnum(r.get("er_decay_delta")) for r in e15]),
        mean([fnum(r.get("ev_decay_delta_silent")) for r in e15]),
        mean([fnum(r.get("cam_delta_overheat")) for r in e15]),
        mean([fnum(r.get("ev_prop_delta")) for r in e15]),
        mean([fnum(r.get("er_induction_delta")) for r in e15]),
    ], color=["#16a34a", "#0f766e", "#dc2626", "#2563eb", "#8b5cf6"])
    axes[2].set_title("E15：调参方向不是随机抖动")
    axes[2].set_ylabel("参数变化均值")
    for ax in axes:
        ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = OUT_DIR / "pq_05_memory_agent_tuning.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_action_grounding_narrative(plt, paths: dict[str, Path]) -> Path:
    e14 = read_csv(paths["E14_FAMILY"])
    e16 = read_csv(paths["E16_FAMILY"])
    e17 = read_csv(paths["E17_FAMILY"])
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.8))
    axes[0].bar(["中性阈值", "奖励阈值", "压力阈值"], [
        mean([fnum(r.get("baseline_threshold")) for r in e14]),
        mean([fnum(r.get("reward_threshold")) for r in e14]),
        mean([fnum(r.get("pressure_threshold")) for r in e14]),
    ], color=["#94a3b8", "#16a34a", "#dc2626"])
    axes[0].set_title("E14：奖惩状态改变行动阈值")
    axes[0].set_ylabel("有效阈值均值")
    axes[1].bar(["packet入池", "packet模态", "packet来源", "runtime模态", "runtime来源"], [
        mean([fnum(r.get("packet_attr_item_present_ratio")) for r in e16]),
        mean([fnum(r.get("packet_attr_modality_ok_ratio")) for r in e16]),
        mean([fnum(r.get("packet_attr_source_ok_ratio")) for r in e16]),
        mean([fnum(r.get("runtime_attr_modality_ok_ratio")) for r in e16]),
        mean([fnum(r.get("runtime_attr_source_ok_ratio")) for r in e16]),
    ], color=["#2563eb", "#0f766e", "#16a34a", "#8b5cf6", "#f59e0b"])
    axes[1].set_ylim(0, 1.12)
    axes[1].set_title("E16：多来源属性以可审计对象进入")
    axes[1].set_ylabel("保真比例")
    seq_labels = ["承接", "无承接", "终端后目标"]
    seq_vals = [
        mean([fnum(r.get("chain_carry_ratio")) for r in e17]),
        mean([fnum(r.get("no_carry_ratio")) for r in e17]),
        mean([fnum(r.get("terminal_followup_target_count")) for r in e17]),
    ]
    axes[2].bar(seq_labels, seq_vals, color=["#2563eb", "#64748b", "#dc2626"])
    axes[2].set_title("E17：内部候选链需要跨拍承接")
    axes[2].set_ylabel("比例 / 目标数")
    for ax in axes:
        ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    path = OUT_DIR / "pq_06_action_grounding_narrative.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def write_manifest(paths: list[Path]) -> None:
    lines = [
        "# Paper-quality chart manifest",
        "",
        "These charts are derived only from final strong-evidence CSV/JSON files. Pilot, smoke, and parameter-search artifacts are intentionally excluded from this presentation layer.",
        "",
        "| file | purpose |",
        "|---|---|",
    ]
    purposes = {
        "pq_00_evidence_map.png": "E01-E17 evidence overview: mechanism domains, sample scale, and representative contrast effects.",
        "pq_00b_experiment_logic_flow.png": "Reader-facing logic flow from mechanism prediction to controlled dataset, contrast, and paper admission.",
        "pq_01_structure_reuse_and_growth.png": "Structure reuse and growth cost for E01-E02.",
        "pq_02_feedback_action_chain.png": "Teacher feedback, correction, and action closure for E03-E05.",
        "pq_03_time_attention_memory.png": "Time interval, attention modulation, and residual memory promotion for E06-E08.",
        "pq_04_feeling_fatigue_energy.png": "Cognitive feelings, repetition regulation, and finite energy graph for E09-E11.",
        "pq_05_memory_agent_tuning.png": "Memory targets, Agent context projection, and auto-tuning for E12-E15.",
        "pq_06_action_grounding_narrative.png": "Action threshold, multimodal grounding entrance, and internal candidate chain for E14/E16/E17.",
    }
    for path in paths:
        lines.append(f"| `{path.name}` | {purposes.get(path.name, '')} |")
    (OUT_DIR / "paper_quality_charts_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    plt = setup_axes()
    paths = final_paths()
    outputs = [
        chart_evidence_map(plt, paths),
        chart_experiment_logic_flow(plt, paths),
        chart_e01_e02(plt, paths),
        chart_reward_action(plt, paths),
        chart_time_attention_memory(plt, paths),
        chart_feeling_fatigue_energy(plt, paths),
        chart_memory_agent_tuning(plt, paths),
        chart_action_grounding_narrative(plt, paths),
    ]
    write_manifest(outputs)
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
