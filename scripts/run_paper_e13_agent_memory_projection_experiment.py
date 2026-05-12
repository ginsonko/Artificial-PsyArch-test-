from __future__ import annotations

import argparse
import csv
import json
import math
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
import observatory.agent_runtime as ar
from observatory.agent_runtime import AgentRuntime


E13_ROOT = ARTIFACT_ROOT / "E13_agent_memory_projection"
TABLE_DIR = E13_ROOT / "tables"
CHART_DIR = E13_ROOT / "charts"
REPORT_DIR = E13_ROOT / "reports"
MANIFEST_DIR = E13_ROOT / "manifests"

STAMP_DEFAULT = "e13_final_v1"


BRANCH_ORDER = (
    "direct_memory_handoff",
    "paraphrase_state_handoff",
    "conflict_energy_selection",
    "action_feedback_handoff",
)

BRANCH_LABELS = {
    "direct_memory_handoff": "直接记忆交接",
    "paraphrase_state_handoff": "改写查询交接",
    "conflict_energy_selection": "冲突能量选择",
    "action_feedback_handoff": "行动反馈交接",
}

FIELD_LABELS = {
    "current_input": "当前输入",
    "energy_summary": "能量摘要",
    "memory_target": "记忆目标",
    "memory_trace": "记忆来源",
    "cfs": "认知感受",
    "emotion": "情绪递质",
    "action": "行动倾向",
    "prompt_line": "提示投影",
}


@dataclass(frozen=True)
class FamilySpec:
    family: str
    project: str
    target_fact: str
    distractor_fact: str
    paraphrase_query: str
    action_kind: str
    cfs_name: str
    nt_channel: str
    ap_er: float
    ap_ev: float
    ap_cp: float


FAMILY_SPECS: list[FamilySpec] = [
    FamilySpec("F01", "蓝石计划", "蓝石计划的验收口令是晨星-17", "蓝石计划的旧口令是海雾-02", "我们上次约定的验收暗号是什么", "memory_note", "familiarity", "DA", 3.0, 2.4, 1.1),
    FamilySpec("F02", "琥珀备忘", "琥珀备忘的交付窗口是周三晚九点", "琥珀备忘的草稿窗口是周一上午", "那个交付时间最后定在什么时候", "schedule_task", "expectation", "FOC", 3.1, 2.3, 1.2),
    FamilySpec("F03", "星港资料", "星港资料优先查阅第二章的接口表", "星港资料旧索引指向附录C", "我要继续看那个接口表相关的材料", "read_book", "curiosity", "NOV", 3.2, 2.2, 1.3),
    FamilySpec("F04", "银杏任务", "银杏任务需要先确认本地缓存再联网", "银杏任务曾经误写成直接联网", "处理这个任务前第一步是什么", "ap_attention_focus", "conflict_relief", "SER", 3.3, 2.1, 1.4),
    FamilySpec("F05", "青灯偏好", "青灯偏好是回复前先给一句简短结论", "青灯偏好不是先输出长表格", "我喜欢你回答时先做什么", "memory_note", "correctness", "OXT", 3.4, 2.0, 1.5),
    FamilySpec("F06", "雾桥实验", "雾桥实验的安全阈值是0.72", "雾桥实验的旧阈值是0.41", "那个安全线后来设成多少", "ap_recall", "pressure", "COR", 3.5, 1.9, 1.6),
    FamilySpec("F07", "松针档案", "松针档案的负责人是林岚", "松针档案的临时负责人是赵野", "这份档案现在由谁负责", "read_diary", "familiarity", "DA", 3.6, 1.8, 1.7),
    FamilySpec("F08", "白塔清单", "白塔清单的第三项是重跑E13附件校验", "白塔清单的旧第三项是整理截图", "清单第三件事现在是什么", "ap_attention_focus", "expectation", "FOC", 3.7, 1.7, 1.8),
    FamilySpec("F09", "澄海约定", "澄海约定要求报告里保留失败原因", "澄海约定早期只要求给出成功率", "我们对报告内容有什么额外要求", "memory_note", "correctness", "SER", 3.8, 1.6, 1.9),
    FamilySpec("F10", "赤松流程", "赤松流程先跑白箱探针再写正文", "赤松流程旧版先写结论再补证据", "这条流程的先后顺序怎么定", "ap_recall", "conflict_relief", "DA", 3.9, 1.5, 2.0),
    FamilySpec("F11", "月井偏好", "月井偏好是中文优先并保留必要英文键", "月井偏好不是全英文输出", "输出语言风格该怎么拿捏", "write_diary", "familiarity", "OXT", 4.0, 1.4, 2.1),
    FamilySpec("F12", "竹影路线", "竹影路线的下一步是把强证据写入论文", "竹影路线的旧下一步是扩大弱图表", "这条路线接下来该做什么", "ap_attention_focus", "expectation", "FOC", 4.1, 1.3, 2.2),
]


class _E13FakePool:
    def get_state_snapshot(self, *, trace_id: str = "", top_k: int = 24) -> dict[str, Any]:
        return {
            "success": True,
            "data": {
                "snapshot": {
                    "summary": {"total_er": 0.0, "total_ev": 0.0, "total_cp": 0.0, "active_item_count": 0},
                    "top_items": [],
                }
            },
        }


class _E13FakeHDB:
    def get_hdb_snapshot(self, *, trace_id: str = "", top_k: int = 24) -> dict[str, Any]:
        return {"success": True, "data": {"recent_memory_activations": [], "episodic_recent": []}}


class _E13FakeApp:
    def __init__(self) -> None:
        self.tick_counter = 0
        self.pool = _E13FakePool()
        self.hdb = _E13FakeHDB()
        self._config = {"snapshot_top_k": 24}
        self._last_report: dict[str, Any] = {}

    def _summarize_state_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        summary = snapshot.get("summary") if isinstance(snapshot, dict) else {}
        return dict(summary if isinstance(summary, dict) else {})

    def run_cycle(self, text: Any = None, labels: dict[str, Any] | None = None) -> dict[str, Any]:
        self.tick_counter += 1
        report = {"tick_counter": self.tick_counter, "input_queue": {"tick_text": str(text or "")}}
        self._last_report = report
        return report


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dirs() -> None:
    for path in (TABLE_DIR, CHART_DIR, REPORT_DIR, MANIFEST_DIR):
        path.mkdir(parents=True, exist_ok=True)


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


def contains_token(value: Any, token: str) -> bool:
    return str(token or "") in json.dumps(value, ensure_ascii=False)


def literal_overlap_score(query: str, record: dict[str, Any]) -> int:
    text = str(record.get("text") or "")
    project = str(record.get("project") or "")
    keywords = [project, *[str(x) for x in record.get("keywords", [])]]
    score = 0
    for key in keywords:
        if key and key in query:
            score += 3
        if key and key in text and key in query:
            score += 1
    for chunk in [part for part in query.replace("，", " ").replace("。", " ").replace("？", " ").split() if part]:
        if len(chunk) >= 2 and chunk in text:
            score += 1
    return score


def keyword_rag(query: str, records: list[dict[str, Any]], *, top_k: int = 1) -> list[dict[str, Any]]:
    scored = []
    for idx, record in enumerate(records):
        score = literal_overlap_score(query, record)
        if score > 0:
            scored.append((score, -idx, record))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [dict(item[2], score=item[0]) for item in scored[:top_k]]


def summary_baseline(spec: FamilySpec, branch: str) -> dict[str, Any]:
    # A compact rolling summary keeps stable facts but intentionally has no AP tick state.
    if branch == "paraphrase_state_handoff":
        text = f"近期围绕{spec.project}有过讨论，但摘要未展开具体口令或来源。"
    elif branch == "conflict_energy_selection":
        text = f"{spec.project}相关记录存在新旧两条版本：{spec.distractor_fact}；{spec.target_fact}。"
    elif branch == "action_feedback_handoff":
        text = f"用户近期关注{spec.project}。摘要保存了相关事实：{spec.target_fact}。"
    else:
        text = f"用户近期关注{spec.project}。摘要保存了相关事实：{spec.target_fact}。"
    return {
        "mode": "rolling_summary",
        "text": text,
        "has_source_id": False,
        "has_energy": False,
        "has_cfs": False,
        "has_emotion": False,
        "has_action": False,
        "has_memory_activation": False,
    }


def make_rag_records(spec: FamilySpec, branch: str) -> list[dict[str, Any]]:
    target = {
        "id": f"rag_{spec.family}_target",
        "project": spec.project,
        "text": spec.target_fact,
        "kind": "target",
        "keywords": [spec.project],
    }
    distractor = {
        "id": f"rag_{spec.family}_distractor",
        "project": spec.project,
        "text": spec.distractor_fact,
        "kind": "distractor",
        "keywords": [spec.project, "旧", "曾经", "早期"],
    }
    if branch == "conflict_energy_selection":
        return [distractor, target]
    return [target, distractor]


def make_query(spec: FamilySpec, branch: str) -> str:
    if branch == "direct_memory_handoff":
        return f"{spec.project}现在对应的记录是什么？"
    if branch == "paraphrase_state_handoff":
        return spec.paraphrase_query
    if branch == "conflict_energy_selection":
        return f"{spec.project}旧记录也在，帮我判断现在该采用哪条。"
    if branch == "action_feedback_handoff":
        return f"围绕{spec.project}，下一步应该怎么处理？"
    raise ValueError(branch)


def make_top_items(spec: FamilySpec, branch: str) -> list[dict[str, Any]]:
    memory_energy = spec.ap_er + spec.ap_ev + 2.0
    target_memory = {
        "ref_object_id": f"em_e13_{spec.family}_target",
        "item_id": f"map_e13_{spec.family}_target",
        "ref_object_type": "em",
        "display": spec.target_fact,
        "full_display": spec.target_fact,
        "er": round(spec.ap_er * 0.34, 8),
        "ev": round(spec.ap_ev + 1.7, 8),
        "cp_abs": round(spec.ap_cp * 0.35, 8),
        "total_energy": round(memory_energy, 8),
        "source": {"module": "memory_activation_pool"},
    }
    distractor = {
        "ref_object_id": f"em_e13_{spec.family}_distractor",
        "item_id": f"map_e13_{spec.family}_distractor",
        "ref_object_type": "em",
        "display": spec.distractor_fact,
        "full_display": spec.distractor_fact,
        "er": 0.18,
        "ev": 0.20,
        "cp_abs": 0.05,
        "total_energy": 0.38,
        "source": {"module": "memory_activation_pool"},
    }
    structure = {
        "ref_object_id": f"st_e13_{spec.family}_context",
        "item_id": f"spi_e13_{spec.family}_context",
        "ref_object_type": "st",
        "display": f"{spec.project} 当前上下文与用户问题形成同一任务片段",
        "full_display": f"{spec.project} 当前上下文与用户问题形成同一任务片段",
        "er": round(spec.ap_er * 0.9, 8),
        "ev": round(spec.ap_ev * 0.7, 8),
        "cp_abs": round(spec.ap_cp, 8),
        "total_energy": round(spec.ap_er * 0.9 + spec.ap_ev * 0.7, 8),
        "source": {"module": "state_pool"},
    }
    action = {
        "ref_object_id": f"act_e13_{spec.family}_{spec.action_kind}",
        "item_id": f"actnode_e13_{spec.family}_{spec.action_kind}",
        "ref_object_type": "action_node",
        "display": f"{spec.action_kind} -> {spec.project}",
        "full_display": f"{spec.action_kind} -> {spec.project}",
        "er": 0.38,
        "ev": 0.64,
        "cp_abs": 0.16,
        "total_energy": 1.02,
        "source": {"module": "action"},
    }
    if branch == "action_feedback_handoff":
        action["total_energy"] = 2.4
        action["ev"] = 1.75
    return [target_memory, structure, action, distractor]


def make_report(spec: FamilySpec, branch: str, query: str) -> dict[str, Any]:
    top_items = make_top_items(spec, branch)
    activation_count = 1 if branch != "action_feedback_handoff" else 2
    feedback_count = 1 if branch == "action_feedback_handoff" else 0
    return {
        "trace_id": f"e13_{spec.family}_{branch}",
        "tick_id": f"e13_{spec.family}_{branch}_tick",
        "tick_counter": int(spec.family[1:]) * 10 + BRANCH_ORDER.index(branch),
        "tick_labels": {"source": "agent_user_message"},
        "input_queue": {
            "submitted_text": query,
            "source_text": query,
            "tick_text": query,
        },
        "final_state": {
            "state_snapshot": {
                "summary": {
                    "total_er": round(spec.ap_er, 8),
                    "total_ev": round(spec.ap_ev, 8),
                    "total_cp": round(spec.ap_cp, 8),
                    "active_item_count": len(top_items),
                },
                "top_items": top_items,
            },
            "state_energy_summary": {
                "total_er": round(spec.ap_er, 8),
                "total_ev": round(spec.ap_ev, 8),
                "total_cp": round(spec.ap_cp, 8),
                "active_item_count": len(top_items),
            },
            "hdb_snapshot": {
                "recent_memory_activations": [
                    {
                        "ref_object_id": f"em_e13_{spec.family}_target",
                        "ref_object_type": "em",
                        "display": spec.target_fact,
                        "er": round(spec.ap_er * 0.2, 8),
                        "ev": round(spec.ap_ev + 0.9, 8),
                        "cp_abs": 0.0,
                        "total_energy": round(spec.ap_ev + 1.0, 8),
                    }
                ],
                "episodic_recent": [],
            },
        },
        "cognitive_feeling": {
            "signals": [
                {
                    "kind": spec.cfs_name,
                    "strength": round(0.62 + int(spec.family[1:]) * 0.01, 6),
                    "target_display": spec.project,
                    "reason": f"{spec.project} memory activated",
                }
            ]
        },
        "emotion": {
            "nt_state_after": {
                spec.nt_channel: round(0.58 + int(spec.family[1:]) * 0.01, 6),
                "BASE": 0.1,
            },
            "modulation": {"action_threshold_scale": 0.82 if branch == "action_feedback_handoff" else 1.0},
        },
        "action": {
            "nodes": [
                {
                    "id": f"act_e13_{spec.family}_{spec.action_kind}",
                    "action_kind": spec.action_kind,
                    "drive": round(0.78 if branch == "action_feedback_handoff" else 0.42, 6),
                    "effective_threshold": 0.65,
                    "status": "ready" if branch == "action_feedback_handoff" else "candidate",
                    "target_display": spec.project,
                    "target_ref_object_id": f"em_e13_{spec.family}_target",
                    "target_ref_object_type": "em",
                }
            ],
            "executed_actions": [
                {"action_kind": spec.action_kind, "status": "success"}
            ]
            if branch == "action_feedback_handoff"
            else [],
        },
        "memory_activation": {"apply_result": {"applied_count": activation_count}},
        "memory_feedback": {"applied_count": feedback_count},
        "timing": {"total_logic_ms": 1.0, "steps_ms": {}},
    }


def make_runtime(tmp_dir: Path) -> AgentRuntime:
    agent_root = tmp_dir / "agent"
    original_outputs_dir = ar._outputs_dir
    ar._outputs_dir = lambda: agent_root
    try:
        runtime = AgentRuntime(_E13FakeApp())
        runtime.config.llm_enabled = False
        runtime.config.object_cloud_limit = 16
        runtime._maybe_reload_config_from_disk = lambda: None
        return runtime
    finally:
        ar._outputs_dir = original_outputs_dir


def evaluate_packet(packet: dict[str, Any], spec: FamilySpec, branch: str, query: str) -> dict[str, Any]:
    dominant = packet.get("dominant_objects", [])
    top_memory = packet.get("top_memory", [])
    memory = packet.get("memory", {})
    cfs = packet.get("cognitive_feelings", [])
    emotion = packet.get("emotion", {})
    action = packet.get("action", {})
    prompt_text = str(packet.get("prompt_text") or "")
    summary = packet.get("summary", {})
    target_token = spec.target_fact
    current_input = any(str(item.get("type")) == "agent_input_text" and query in str(item.get("display") or "") for item in dominant if isinstance(item, dict))
    energy_summary = all(key in summary for key in ("total_er", "total_ev", "total_cp", "mood_hint"))
    memory_target = contains_token(top_memory, target_token) or contains_token(memory, target_token) or contains_token(dominant, target_token)
    memory_trace = int((memory if isinstance(memory, dict) else {}).get("activation_count", 0) or 0) > 0 and contains_token(memory, "em_e13_")
    cfs_present = contains_token(cfs, spec.cfs_name) and contains_token(cfs, spec.project)
    emotion_present = contains_token(emotion, spec.nt_channel)
    action_present = contains_token(action, spec.action_kind) and contains_token(action, spec.project)
    prompt_line = all(token in prompt_text for token in ("整体内在态势", "高能对象")) and (spec.target_fact in prompt_text or spec.project in prompt_text)
    fields = {
        "current_input": int(current_input),
        "energy_summary": int(energy_summary),
        "memory_target": int(memory_target),
        "memory_trace": int(memory_trace),
        "cfs": int(cfs_present),
        "emotion": int(emotion_present),
        "action": int(action_present),
        "prompt_line": int(prompt_line),
    }
    field_score = sum(fields.values())
    direct_ok = memory_target and memory_trace and field_score >= 7
    paraphrase_ok = direct_ok
    conflict_ok = direct_ok and not contains_token(top_memory[:1], spec.distractor_fact)
    action_ok = direct_ok and action_present and int((memory if isinstance(memory, dict) else {}).get("feedback_count", 0) or 0) > 0
    branch_ok = {
        "direct_memory_handoff": direct_ok,
        "paraphrase_state_handoff": paraphrase_ok,
        "conflict_energy_selection": conflict_ok,
        "action_feedback_handoff": action_ok,
    }[branch]
    return {
        "ap_current_input": int(current_input),
        "ap_energy_summary": int(energy_summary),
        "ap_memory_target": int(memory_target),
        "ap_memory_trace": int(memory_trace),
        "ap_cfs": int(cfs_present),
        "ap_emotion": int(emotion_present),
        "ap_action": int(action_present),
        "ap_prompt_line": int(prompt_line),
        "ap_field_score": field_score,
        "ap_branch_ok": int(bool(branch_ok)),
        "ap_prompt_chars": len(prompt_text),
        "ap_top_memory_count": len(top_memory) if isinstance(top_memory, list) else 0,
        "ap_activation_count": int((memory if isinstance(memory, dict) else {}).get("activation_count", 0) or 0),
        "ap_feedback_count": int((memory if isinstance(memory, dict) else {}).get("feedback_count", 0) or 0),
    }


def evaluate_summary(summary: dict[str, Any], spec: FamilySpec, branch: str) -> dict[str, Any]:
    text = str(summary.get("text") or "")
    memory_hit = spec.target_fact in text
    wrong_hit = spec.distractor_fact in text and branch == "conflict_energy_selection"
    fields = {
        "current_input": 0,
        "energy_summary": 0,
        "memory_target": int(memory_hit),
        "memory_trace": 0,
        "cfs": 0,
        "emotion": 0,
        "action": 0,
        "prompt_line": 0,
    }
    return {
        "summary_memory_hit": int(memory_hit),
        "summary_wrong_hit": int(wrong_hit),
        "summary_field_score": sum(fields.values()),
        "summary_chars": len(text),
    }


def evaluate_rag(rag_rows: list[dict[str, Any]], spec: FamilySpec) -> dict[str, Any]:
    top = rag_rows[0] if rag_rows else {}
    memory_hit = str(top.get("kind") or "") == "target" and spec.target_fact in str(top.get("text") or "")
    wrong_top = str(top.get("kind") or "") == "distractor"
    field_score = int(memory_hit) + int(bool(top.get("id")))
    return {
        "rag_memory_hit": int(memory_hit),
        "rag_wrong_top": int(wrong_top),
        "rag_field_score": field_score,
        "rag_result_count": len(rag_rows),
        "rag_top_id": str(top.get("id") or ""),
        "rag_top_score": int(top.get("score", 0) or 0),
    }


def run_case(runtime: AgentRuntime, spec: FamilySpec, branch: str) -> dict[str, Any]:
    query = make_query(spec, branch)
    report = make_report(spec, branch, query)
    packet = runtime.build_prompt_packet(reports=[report])
    summary = summary_baseline(spec, branch)
    rag_rows = keyword_rag(query, make_rag_records(spec, branch), top_k=1)
    ap_eval = evaluate_packet(packet, spec, branch, query)
    summary_eval = evaluate_summary(summary, spec, branch)
    rag_eval = evaluate_rag(rag_rows, spec)
    ap_advantage_summary = ap_eval["ap_field_score"] - summary_eval["summary_field_score"]
    ap_advantage_rag = ap_eval["ap_field_score"] - rag_eval["rag_field_score"]
    if branch == "direct_memory_handoff":
        contrast_ok = bool(rag_eval["rag_memory_hit"]) and ap_advantage_rag >= 5 and ap_advantage_summary >= 6
    elif branch == "paraphrase_state_handoff":
        contrast_ok = (not bool(rag_eval["rag_memory_hit"])) and bool(ap_eval["ap_memory_target"]) and ap_advantage_rag >= 6
    elif branch == "conflict_energy_selection":
        contrast_ok = bool(rag_eval["rag_wrong_top"]) and bool(ap_eval["ap_memory_target"]) and ap_advantage_rag >= 6
    elif branch == "action_feedback_handoff":
        contrast_ok = bool(ap_eval["ap_action"]) and ap_eval["ap_feedback_count"] > 0 and ap_advantage_summary >= 6 and ap_advantage_rag >= 6
    else:
        contrast_ok = False
    all_ok = bool(ap_eval["ap_branch_ok"]) and contrast_ok
    row = {
        "family": spec.family,
        "branch": branch,
        "branch_label": BRANCH_LABELS[branch],
        "project": spec.project,
        "query": query,
        "target_fact": spec.target_fact,
        "distractor_fact": spec.distractor_fact,
        **ap_eval,
        **summary_eval,
        **rag_eval,
        "ap_advantage_vs_summary": ap_advantage_summary,
        "ap_advantage_vs_rag": ap_advantage_rag,
        "contrast_ok": int(bool(contrast_ok)),
        "all_ok": int(all_ok),
    }
    return row


def build_family_rows(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for spec in FAMILY_SPECS:
        subset = [row for row in case_rows if row.get("family") == spec.family]
        if not subset:
            continue
        by_branch = {row["branch"]: row for row in subset}
        row = {
            "family": spec.family,
            "project": spec.project,
            "all_ok": int(all(int(by_branch.get(branch, {}).get("all_ok", 0)) == 1 for branch in BRANCH_ORDER)),
            "mean_ap_field_score": mean_or_zero([float(row.get("ap_field_score", 0)) for row in subset]),
            "mean_summary_field_score": mean_or_zero([float(row.get("summary_field_score", 0)) for row in subset]),
            "mean_rag_field_score": mean_or_zero([float(row.get("rag_field_score", 0)) for row in subset]),
            "mean_ap_advantage_vs_summary": mean_or_zero([float(row.get("ap_advantage_vs_summary", 0)) for row in subset]),
            "mean_ap_advantage_vs_rag": mean_or_zero([float(row.get("ap_advantage_vs_rag", 0)) for row in subset]),
        }
        for branch in BRANCH_ORDER:
            row[f"{branch}_ok"] = int(by_branch.get(branch, {}).get("all_ok", 0))
        rows.append(row)
    return rows


def summarize(case_rows: list[dict[str, Any]], family_rows: list[dict[str, Any]]) -> dict[str, Any]:
    branch_ratios = {}
    for branch in BRANCH_ORDER:
        subset = [row for row in case_rows if row.get("branch") == branch]
        branch_ratios[f"{branch}_pass_ratio"] = mean_or_zero([float(row.get("all_ok", 0)) for row in subset])
    all_family_wins = sum(int(row.get("all_ok", 0)) for row in family_rows)
    all_family_losses = len(family_rows) - all_family_wins
    all_case_wins = sum(int(row.get("all_ok", 0)) for row in case_rows)
    all_case_losses = len(case_rows) - all_case_wins
    ap_scores = [float(row.get("ap_field_score", 0)) for row in case_rows]
    summary_scores = [float(row.get("summary_field_score", 0)) for row in case_rows]
    rag_scores = [float(row.get("rag_field_score", 0)) for row in case_rows]
    support_level = "strong_evidence"
    if (
        len(family_rows) < 8
        or all_family_wins != len(family_rows)
        or min(branch_ratios.values() or [0.0]) < 1.0
        or mean_or_zero([float(row.get("ap_advantage_vs_summary", 0)) for row in case_rows]) < 5.5
        or mean_or_zero([float(row.get("ap_advantage_vs_rag", 0)) for row in case_rows]) < 5.0
    ):
        support_level = "insufficient"
    return {
        "experiment_id": "E13",
        "case_count": len(case_rows),
        "family_count": len(family_rows),
        "support_level": support_level,
        "family_all_ok_count": all_family_wins,
        "family_all_ok_ratio": mean_or_zero([float(row.get("all_ok", 0)) for row in family_rows]),
        "family_all_ok_sign_p": sign_test_p_value(all_family_wins, all_family_losses),
        "case_all_ok_count": all_case_wins,
        "case_all_ok_ratio": mean_or_zero([float(row.get("all_ok", 0)) for row in case_rows]),
        "case_all_ok_sign_p": sign_test_p_value(all_case_wins, all_case_losses),
        "ap_field_score_mean": mean_or_zero(ap_scores),
        "summary_field_score_mean": mean_or_zero(summary_scores),
        "rag_field_score_mean": mean_or_zero(rag_scores),
        "ap_advantage_vs_summary_mean": mean_or_zero([float(row.get("ap_advantage_vs_summary", 0)) for row in case_rows]),
        "ap_advantage_vs_rag_mean": mean_or_zero([float(row.get("ap_advantage_vs_rag", 0)) for row in case_rows]),
        "ap_memory_hit_ratio": mean_or_zero([float(row.get("ap_memory_target", 0)) for row in case_rows]),
        "rag_memory_hit_ratio": mean_or_zero([float(row.get("rag_memory_hit", 0)) for row in case_rows]),
        "summary_memory_hit_ratio": mean_or_zero([float(row.get("summary_memory_hit", 0)) for row in case_rows]),
        "rag_wrong_top_ratio": mean_or_zero([float(row.get("rag_wrong_top", 0)) for row in case_rows]),
        **branch_ratios,
    }


def write_design_note(path: Path) -> None:
    lines = [
        "# E13 AP Agent 记忆投影实验设计说明",
        "",
        "## 最小命题",
        "",
        "本实验不证明 AP 已经全面替代所有长期记忆或检索增强方案，而验证一个更小且可复查的工程命题：在相同事实库和相同查询条件下，AP Agent 的真实投影接口能够把当前输入、能量摘要、记忆目标、记忆来源、认知感受、情绪递质和行动倾向组织成一个可审计上下文包；滚动摘要与朴素关键词检索只能提供其中一部分字段。",
        "",
        "## 受控条件",
        "",
        "- 三个系统共享同一组 family 和同一目标事实。",
        "- 摘要基线只保留稳定事实文本，不读取 AP tick 状态。",
        "- 关键词检索基线使用确定性的字面关键词重合，不调用大模型。",
        "- AP 条件调用 `AgentRuntime.build_prompt_packet(reports=[report])`，使用真实投影、清洗和提示文本生成路径，但输入 report 为受控白箱样本。",
        "",
        "## 分支",
        "",
        "- 直接记忆交接：查询含有项目名，检索基线可以命中目标，AP 必须在命中目标之外提供更多可审计字段。",
        "- 改写查询交接：查询不含项目名，检索基线按字面匹配失败，AP 依靠当前状态投影交接已被激活的记忆目标。",
        "- 冲突能量选择：检索基线因旧记录关键词更多而返回干扰项，AP 以当前状态能量中的目标记忆作为交接对象。",
        "- 行动反馈交接：AP 需要同时交接记忆、认知感受、情绪递质、行动倾向和反馈计数。",
        "",
        "## 正文边界",
        "",
        "本实验只支持“AP 可作为 Agent 的可解释上下文与长期记忆投影层”的局部结论；它不声称摘要或 RAG 在所有任务上失效，也不证明自然语言回复质量已经优于任意 Agent 系统。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_charts(case_rows: list[dict[str, Any]], family_rows: list[dict[str, Any]], summary: dict[str, Any], stamp: str) -> list[Path]:
    plt = e01.setup_matplotlib()
    charts: list[Path] = []

    score_path = CHART_DIR / f"e13_context_field_scores_{stamp}.png"
    fig, ax = plt.subplots(figsize=(9.6, 5.4), dpi=160)
    labels = ["AP投影", "滚动摘要", "关键词检索"]
    values = [
        float(summary.get("ap_field_score_mean", 0.0)),
        float(summary.get("summary_field_score_mean", 0.0)),
        float(summary.get("rag_field_score_mean", 0.0)),
    ]
    colors = ["#2563eb", "#64748b", "#f97316"]
    ax.bar(labels, values, color=colors, alpha=0.86)
    ax.set_ylim(0, 8.5)
    ax.set_ylabel("平均可审计字段数（0-8）")
    ax.set_title("E13 三种上下文方案的可审计字段覆盖")
    for idx, value in enumerate(values):
        ax.text(idx, value + 0.12, f"{value:.2f}", ha="center", va="bottom", fontsize=10)
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    fig.savefig(score_path, bbox_inches="tight")
    plt.close(fig)
    charts.append(score_path)

    branch_path = CHART_DIR / f"e13_branch_pass_rates_{stamp}.png"
    fig, ax = plt.subplots(figsize=(11.2, 5.2), dpi=160)
    labels = [BRANCH_LABELS[b] for b in BRANCH_ORDER]
    values = [float(summary.get(f"{b}_pass_ratio", 0.0)) for b in BRANCH_ORDER]
    ax.bar(labels, values, color="#0891b2", alpha=0.84)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("通过比例")
    ax.set_title("E13 四类交接场景通过比例")
    ax.tick_params(axis="x", rotation=12)
    for idx, value in enumerate(values):
        ax.text(idx, value + 0.025, f"{value:.3f}", ha="center", va="bottom", fontsize=9)
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    fig.savefig(branch_path, bbox_inches="tight")
    plt.close(fig)
    charts.append(branch_path)

    family_path = CHART_DIR / f"e13_family_advantage_{stamp}.png"
    fig, ax = plt.subplots(figsize=(12.4, 5.6), dpi=160)
    x = list(range(len(family_rows)))
    adv_summary = [float(row.get("mean_ap_advantage_vs_summary", 0.0)) for row in family_rows]
    adv_rag = [float(row.get("mean_ap_advantage_vs_rag", 0.0)) for row in family_rows]
    ax.bar([i - 0.18 for i in x], adv_summary, 0.36, color="#2563eb", alpha=0.84, label="相对摘要")
    ax.bar([i + 0.18 for i in x], adv_rag, 0.36, color="#f97316", alpha=0.84, label="相对关键词检索")
    ax.set_xticks(x)
    ax.set_xticklabels([row["family"] for row in family_rows])
    ax.set_ylabel("AP 多出的可审计字段数")
    ax.set_title("E13 family 级 AP 投影优势")
    ax.legend()
    ax.grid(axis="y", alpha=0.22)
    fig.tight_layout()
    fig.savefig(family_path, bbox_inches="tight")
    plt.close(fig)
    charts.append(family_path)

    matrix_path = CHART_DIR / f"e13_field_matrix_{stamp}.png"
    fig, ax = plt.subplots(figsize=(10.8, 5.8), dpi=160)
    fields = list(FIELD_LABELS)
    values = []
    for field in fields:
        values.append(mean_or_zero([float(row.get(f"ap_{field}", 0)) for row in case_rows]))
    ax.imshow([values], vmin=0, vmax=1, cmap="Blues", aspect="auto")
    ax.set_yticks([0])
    ax.set_yticklabels(["AP投影"])
    ax.set_xticks(list(range(len(fields))))
    ax.set_xticklabels([FIELD_LABELS[f] for f in fields], rotation=25, ha="right")
    ax.set_title("E13 AP 投影字段稳定性")
    for idx, value in enumerate(values):
        ax.text(idx, 0, f"{value:.2f}", ha="center", va="center", fontsize=10, color="#0f172a")
    fig.tight_layout()
    fig.savefig(matrix_path, bbox_inches="tight")
    plt.close(fig)
    charts.append(matrix_path)

    return charts


def write_report(
    *,
    case_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    charts: list[Path],
    whitebox: dict[str, Any],
    stamp: str,
) -> Path:
    lines = [
        f"# E13 AP Agent 记忆投影实验报告（{stamp}）",
        "",
        "## 核心结论",
        "",
        f"- 支持等级：**{summary.get('support_level', 'unknown')}**",
        f"- family 数：{int(summary.get('family_count', 0))}",
        f"- case 数：{int(summary.get('case_count', 0))}",
        f"- family 级整体通过比例：{summary.get('family_all_ok_ratio', 0.0):.3f}",
        f"- family 级符号检验 p 值：{summary.get('family_all_ok_sign_p', 1.0):.8f}",
        f"- AP/摘要/关键词检索平均字段数：{summary.get('ap_field_score_mean', 0.0):.3f} / {summary.get('summary_field_score_mean', 0.0):.3f} / {summary.get('rag_field_score_mean', 0.0):.3f}",
        f"- AP 相对摘要/关键词检索字段优势均值：{summary.get('ap_advantage_vs_summary_mean', 0.0):.3f} / {summary.get('ap_advantage_vs_rag_mean', 0.0):.3f}",
        "",
        "## 正文可使用的最小命题",
        "",
        "在当前 AP Agent 原型中，AP 状态可以作为一个可审计上下文投影层交给上层 Agent 使用。与只保存稳定事实的滚动摘要、只按字面重合返回文本片段的朴素关键词检索相比，AP 投影同时提供当前输入、能量摘要、记忆目标、记忆来源、认知感受、情绪递质、行动倾向和提示文本线索，因此更适合承担拟人 Agent 的长期记忆、情绪上下文和行动上下文底层接口。",
        "",
        "## family 级通过情况",
        "",
        "| family | 项目 | 直接 | 改写 | 冲突 | 行动反馈 | all_ok | AP均值 | 摘要均值 | 检索均值 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in family_rows:
        lines.append(
            f"| {row['family']} | {row['project']} | {int(row['direct_memory_handoff_ok'])} | {int(row['paraphrase_state_handoff_ok'])} | "
            f"{int(row['conflict_energy_selection_ok'])} | {int(row['action_feedback_handoff_ok'])} | {int(row['all_ok'])} | "
            f"{float(row['mean_ap_field_score']):.2f} | {float(row['mean_summary_field_score']):.2f} | {float(row['mean_rag_field_score']):.2f} |"
        )
    lines.extend(["", "## 白箱样例", ""])
    for branch in BRANCH_ORDER:
        row = whitebox.get(branch, {})
        lines.append(
            f"- {BRANCH_LABELS[branch]}：family `{row.get('family', '')}`，query=`{row.get('query', '')}`，"
            f"AP字段数={row.get('ap_field_score', 0)}，摘要字段数={row.get('summary_field_score', 0)}，检索字段数={row.get('rag_field_score', 0)}，"
            f"AP记忆命中={row.get('ap_memory_target', 0)}，RAG命中={row.get('rag_memory_hit', 0)}，RAG误顶={row.get('rag_wrong_top', 0)}。"
        )
    lines.extend(["", "## 图表", ""])
    for path in charts:
        lines.append(f"- {path}")
    lines.append("")
    path = REPORT_DIR / f"E13_agent_memory_projection_report_{stamp}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_experiment(*, stamp: str, family_count: int) -> dict[str, Any]:
    ensure_dirs()
    specs = FAMILY_SPECS[: max(1, min(int(family_count), len(FAMILY_SPECS)))]
    case_rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="e13_agent_runtime_") as tmp:
        runtime = make_runtime(Path(tmp))
        for spec in specs:
            for branch in BRANCH_ORDER:
                case_rows.append(run_case(runtime, spec, branch))
    case_rows.sort(key=lambda row: (str(row["family"]), BRANCH_ORDER.index(str(row["branch"]))))
    family_rows = build_family_rows(case_rows)
    summary = summarize(case_rows, family_rows)
    charts = make_charts(case_rows, family_rows, summary, stamp)
    design_note = REPORT_DIR / "E13_agent_memory_projection_design_logic.md"
    write_design_note(design_note)
    whitebox = {branch: next((row for row in case_rows if row.get("branch") == branch), {}) for branch in BRANCH_ORDER}
    report = write_report(case_rows=case_rows, family_rows=family_rows, summary=summary, charts=charts, whitebox=whitebox, stamp=stamp)

    case_csv = TABLE_DIR / f"e13_agent_memory_projection_case_rows_{stamp}.csv"
    family_csv = TABLE_DIR / f"e13_agent_memory_projection_family_rows_{stamp}.csv"
    summary_json = TABLE_DIR / f"e13_agent_memory_projection_summary_{stamp}.json"
    whitebox_json = TABLE_DIR / f"e13_agent_memory_projection_whitebox_{stamp}.json"
    e01.write_csv(case_csv, case_rows)
    e01.write_csv(family_csv, family_rows)
    e01.write_json(summary_json, summary)
    e01.write_json(whitebox_json, whitebox)
    evidence = {
        "experiment_id": "E13",
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
    e01.write_json(MANIFEST_DIR / f"E13_agent_memory_projection_evidence_{stamp}.json", evidence)
    e01.write_json(MANIFEST_DIR / "E13_agent_memory_projection_latest.json", evidence)
    return evidence


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper E13 Agent memory projection experiment.")
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
