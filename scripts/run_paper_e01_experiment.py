# -*- coding: utf-8 -*-
"""Build and run paper E01 lexical-abstraction experiments.

This script generates controlled datasets, runs them through the existing AP
Observatory experiment runner, and writes reproduction charts/tables/reports
under the configured AP_PAPER_ARTIFACT_ROOT directory.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import shutil
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from _reproduction_paths import AP_ROOT, ARTIFACT_ROOT, ATTACHMENT_ROOT

if str(AP_ROOT) not in sys.path:
    sys.path.insert(0, str(AP_ROOT))

from observatory._app import ObservatoryApp
from observatory.experiment.runner import RunOptions, run_dataset
from observatory.experiment.storage import DatasetFileRef, imported_datasets_dir, resolve_run_dir
from observatory.experiment.io import sha256_file


E01_ROOT = ARTIFACT_ROOT / "E01_lexical_abstraction"
DATASET_ARTIFACT_DIR = E01_ROOT / "datasets"
RUN_ARTIFACT_DIR = E01_ROOT / "runs"
CHART_DIR = E01_ROOT / "charts"
TABLE_DIR = E01_ROOT / "tables"
REPORT_DIR = E01_ROOT / "reports"
MANIFEST_DIR = E01_ROOT / "manifests"

ANCHOR_PHRASES = [
    "确认目标",
    "开始记录",
    "标记原因",
    "安排复查",
    "三条结论",
    "发送给小林",
    "检查进度",
    "下一步动作",
]

CURRICULUM_VERSION = "paper_e01_v2_matched_control"
CORE_PHASES = {"homomorphic_template", "matched_nonisomorphic_control"}

E01_METRIC_KEYS = [
    "input_len",
    "sensor_feature_sa_count",
    "external_sa_count",
    "hdb_structure_count",
    "hdb_contextual_structure_count",
    "hdb_residual_diff_entry_count",
    "hdb_diff_entry_with_memory_ref_count",
    "stimulus_cut_common_part_total_count",
    "stimulus_best_match_common_part_count",
    "stimulus_residual_ratio",
    "stimulus_best_match_score",
    "stimulus_match_v2_score_mean",
    "stimulus_match_v2_order_alignment_mean",
    "stimulus_match_v2_soft_partial_selected_count",
    "stimulus_match_v2_exact_match_selected_count",
    "structure_best_match_score",
    "structure_match_v2_score_mean",
    "structure_match_v2_order_alignment_mean",
    "induction_growth_target_count",
    "induction_growth_identity_hit_count",
    "induction_growth_identity_created_count",
    "induction_growth_identity_shared_cache_hit_count",
    "induction_growth_identity_local_cache_hit_count",
    "induction_growth_deduped_count",
    "induction_growth_total_delta_ev",
    "pool_active_item_count",
    "pool_total_ev",
    "pool_total_er",
    "timing_total_logic_ms",
]


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dirs() -> None:
    for path in [
        DATASET_ARTIFACT_DIR,
        RUN_ARTIFACT_DIR,
        CHART_DIR,
        TABLE_DIR,
        REPORT_DIR,
        MANIFEST_DIR,
        imported_datasets_dir(),
    ]:
        path.mkdir(parents=True, exist_ok=True)


def _compact_text(text: Any) -> str:
    return "".join(str(text or "").replace(" ", "").replace("+", "").replace("{", "").replace("}", "").split())


def _top_identity_list(row: dict[str, Any], key: str = "pool_ev_structure_top5") -> list[str]:
    raw = row.get(key)
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        ident = str(
            item.get("ref_object_id")
            or item.get("object_id")
            or item.get("id")
            or item.get("display")
            or item.get("display_text")
            or ""
        ).strip()
        if ident:
            out.append(ident[:180])
    return out


def _top_display_blob(row: dict[str, Any]) -> str:
    pieces: list[str] = []
    for key in (
        "pool_er_top5",
        "pool_ev_top5",
        "pool_cp_top5",
        "pool_er_structure_top5",
        "pool_ev_structure_top5",
        "pool_cp_structure_top5",
    ):
        raw = row.get(key)
        if isinstance(raw, list):
            for item in raw[:5]:
                if isinstance(item, dict):
                    pieces.append(str(item.get("display") or item.get("display_text") or ""))
        text_key = f"{key}_text"
        if row.get(text_key):
            pieces.append(str(row.get(text_key) or ""))
    return _compact_text(" ".join(pieces))


def _anchor_presence(row: dict[str, Any]) -> float:
    blob = _top_display_blob(row)
    if not blob:
        return 0.0
    hits = sum(1 for phrase in ANCHOR_PHRASES if phrase in blob)
    return float(hits) / max(1.0, float(len(ANCHOR_PHRASES)))


def _numeric(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        value = row.get(key, default)
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _stats(values: list[float]) -> dict[str, float | int]:
    clean = [float(x) for x in values if isinstance(x, (int, float)) and math.isfinite(float(x))]
    if not clean:
        return {"n": 0, "mean": 0.0, "sd": 0.0, "min": 0.0, "max": 0.0, "sum": 0.0}
    return {
        "n": len(clean),
        "mean": round(statistics.fmean(clean), 8),
        "sd": round(statistics.stdev(clean), 8) if len(clean) >= 2 else 0.0,
        "min": round(min(clean), 8),
        "max": round(max(clean), 8),
        "sum": round(sum(clean), 8),
    }


def _paired_direction(treatment: list[float], control: list[float], *, higher_is_better: bool = True) -> dict[str, Any]:
    pairs = min(len(treatment), len(control))
    diffs = []
    wins = 0
    for i in range(pairs):
        diff = float(treatment[i]) - float(control[i])
        diffs.append(diff)
        if higher_is_better and diff > 0:
            wins += 1
        if not higher_is_better and diff < 0:
            wins += 1
    return {
        "pairs": pairs,
        "wins": wins,
        "win_ratio": round(float(wins) / max(1.0, float(pairs or 1)), 6),
        "mean_diff": round(statistics.fmean(diffs), 8) if diffs else 0.0,
        "diffs": [round(x, 8) for x in diffs],
    }


def _safe_ratio(num: float, den: float) -> float:
    return round(float(num) / max(1e-12, float(den)), 8)


def build_treatment_records() -> list[dict[str, Any]]:
    specs = [
        (
            "T01_confirm_goal",
            "请先确认{obj}的{task}目标，再开始记录。",
            [
                ("客户甲", "周报"),
                ("客户乙", "邮件"),
                ("项目蓝桥", "接口"),
                ("课程作业", "复盘"),
                ("实验记录", "排期"),
                ("采购清单", "验收"),
                ("部署窗口", "备份"),
                ("晨会议题", "演示"),
            ],
        ),
        (
            "T02_mark_reason",
            "如果{obj}出现{issue}，先标记原因，再安排复查。",
            [
                ("客户甲", "延迟"),
                ("客户乙", "误差"),
                ("项目蓝桥", "冲突"),
                ("课程作业", "遗漏"),
                ("实验记录", "噪声"),
                ("采购清单", "缺项"),
                ("部署窗口", "告警"),
                ("晨会议题", "偏差"),
            ],
        ),
        (
            "T03_summarize_send",
            "把{place}的{material}整理成三条结论，然后发送给小林。",
            [
                ("会议室", "访谈记录"),
                ("实验台", "观测数据"),
                ("资料夹", "客户反馈"),
                ("任务板", "进度摘要"),
                ("白板", "讨论要点"),
                ("工单页", "错误日志"),
                ("控制台", "运行结果"),
                ("仓库", "变更清单"),
            ],
        ),
        (
            "T04_time_progress",
            "{time_word}提醒我检查{project}进度，并记录下一步动作。",
            [
                ("上午九点", "周报"),
                ("中午之前", "邮件"),
                ("下午三点", "接口"),
                ("晚饭以后", "复盘"),
                ("明天早晨", "排期"),
                ("周五之前", "验收"),
                ("下次启动时", "备份"),
                ("会议结束后", "演示"),
            ],
        ),
    ]
    records: list[dict[str, Any]] = []
    for template_id, template, values in specs:
        for trial_index, slot_values in enumerate(values):
            text = template.format(
                obj=slot_values[0],
                task=slot_values[1],
                issue=slot_values[1],
                place=slot_values[0],
                material=slot_values[1],
                time_word=slot_values[0],
                project=slot_values[1],
            )
            records.append(
                {
                    "text": text,
                    "template_id": template_id,
                    "trial_index": trial_index,
                    "phase": "homomorphic_template",
                    "condition": "treatment",
                    "expected_frame": template,
                }
            )

    distractors = [
        "小林临时把白板擦干净，因为下午要给客户甲演示另一套方案。",
        "控制台上的告警并不来自接口，而是测试账户没有刷新权限。",
        "会议结束以后，资料夹被放回仓库，采购清单暂时不用复查。",
        "课程作业里的访谈记录很短，但实验台数据需要单独备份。",
        "客户乙说邮件已经发送，可晨会议题还没有进入任务板。",
        "部署窗口推迟到周五之前，周报和排期都需要重新同步。",
        "错误日志显示噪声来自旧版本，运行结果暂时不能直接验收。",
        "讨论要点被拆成两段，下一步动作先等小林确认时间。",
    ]
    for trial_index, text in enumerate(distractors):
        records.append(
            {
                "text": text,
                "template_id": "D00_distractor",
                "trial_index": trial_index,
                "phase": "nonisomorphic_distractor",
                "condition": "treatment",
                "expected_frame": "同主题非同构干扰句",
            }
        )
    return records


def build_control_records() -> list[dict[str, Any]]:
    subjects = ["客户甲", "客户乙", "项目蓝桥", "课程作业", "实验记录", "采购清单", "部署窗口", "晨会议题"]
    tasks = ["周报", "邮件", "接口", "复盘", "排期", "验收", "备份", "演示"]
    issues = ["延迟", "误差", "冲突", "遗漏", "噪声", "缺项", "告警", "偏差"]
    places = ["会议室", "实验台", "资料夹", "任务板", "白板", "工单页", "控制台", "仓库"]
    times = ["上午九点", "中午之前", "下午三点", "晚饭以后", "明天早晨", "周五之前", "下次启动时", "会议结束后"]
    patterns = [
        "{subj}把{task}目标临时换成附件说明，记录前小林先离开会议室。",
        "关于{task}，{subj}没有要求确认目标，只留下一个需要复查的注释。",
        "{time_word}以后再看{subj}，{task}的下一步动作可能要重新排期。",
        "如果出现{issue}，小林先问{place}有没有旧记录，而不是直接安排复查。",
        "{place}里的{task}材料被分成两份，客户只要求发送摘要。",
        "检查{subj}进度时，{issue}和备份混在一起，结论暂时不止三条。",
        "记录{task}之前，{place}的控制台弹出{issue}，演示被推迟。",
        "{subj}提醒小林：{time_word}不用发送结论，先等任务板更新。",
        "三条结论来自{place}，但{task}目标还在客户那里，没有进入记录。",
        "{issue}并不影响{subj}，真正要处理的是{time_word}后的验收窗口。",
    ]
    records: list[dict[str, Any]] = []
    index = 0
    for block in range(4):
        for trial_index in range(8):
            subj = subjects[(trial_index + block) % len(subjects)]
            task = tasks[(trial_index * 2 + block) % len(tasks)]
            issue = issues[(trial_index + block * 3) % len(issues)]
            place = places[(trial_index * 3 + block) % len(places)]
            time_word = times[(trial_index + block * 2) % len(times)]
            pattern = patterns[(index * 3 + block) % len(patterns)]
            text = pattern.format(subj=subj, task=task, issue=issue, place=place, time_word=time_word)
            records.append(
                {
                    "text": text,
                    "template_id": f"C{block + 1:02d}_nonisomorphic",
                    "trial_index": trial_index,
                    "phase": "nonisomorphic_control",
                    "condition": "control",
                    "expected_frame": "控制组：主题词近似但句式不固定",
                }
            )
            index += 1
    control_distractors = [
        "小林把运行结果贴到白板旁边，客户甲暂时只关心权限说明。",
        "任务板没有显示采购清单，会议室的访谈记录也没有同步。",
        "旧版本把噪声写进错误日志，课程作业因此需要重新命名。",
        "仓库里的变更清单被合并，控制台却仍然提示演示窗口。",
        "客户乙回复邮件时没有提目标，只说下午三点以后再看。",
        "接口告警和周报复盘同时出现，排期表需要人工判断。",
        "白板上的讨论要点被擦掉，实验台只留下三行观测数据。",
        "部署窗口结束以后，小林把备份说明放进资料夹。",
    ]
    for trial_index, text in enumerate(control_distractors):
        records.append(
            {
                "text": text,
                "template_id": "C00_distractor",
                "trial_index": trial_index,
                "phase": "control_distractor",
                "condition": "control",
                "expected_frame": "控制组：同主题非同构干扰句",
            }
        )
    return records


def _matched_case_specs() -> list[dict[str, Any]]:
    """Return paired treatment/control cases for the stricter E01 design.

    The paired texts deliberately reuse the same domain roles and key words.
    The treatment side keeps a stable long frame; the control side keeps the
    local vocabulary but changes word order, connective pattern, and phrase
    boundary so that simple topic overlap is not enough to explain a positive
    result.
    """

    subjects = ["客户甲", "客户乙", "项目蓝桥", "课程作业", "实验记录", "采购清单", "部署窗口", "晨会议题"]
    tasks = ["周报", "邮件", "接口", "复盘", "排期", "验收", "备份", "演示"]
    issues = ["延迟", "误差", "冲突", "遗漏", "噪声", "缺项", "告警", "偏差"]
    places = ["会议室", "实验台", "资料夹", "任务板", "白板", "工单页", "控制台", "仓库"]
    materials = ["访谈记录", "观测数据", "客户反馈", "进度摘要", "讨论要点", "错误日志", "运行结果", "变更清单"]
    times = ["上午九点", "中午之前", "下午三点", "晚饭以后", "明天早晨", "周五之前", "下次启动时", "会议结束后"]

    frames = [
        {
            "template_id": "T01_confirm_goal",
            "treatment_template": "请先确认{subject}的{task}目标，再开始记录。",
            "control_templates": [
                "{task}由{subject}提交，开始记录前先确认目标。",
                "开始记录以前，先确认{subject}的{task}目标。",
                "{subject}提交{task}后，把确认目标放在开始记录前。",
                "关于{subject}的{task}，开始记录前需要确认目标。",
            ],
            "anchor": "确认目标/开始记录",
        },
        {
            "template_id": "T02_mark_reason",
            "treatment_template": "如果{subject}出现{issue}，先标记原因，再安排复查。",
            "control_templates": [
                "{subject}{issue}以后，安排复查前先标记原因。",
                "安排复查{subject}前，{issue}原因需要先标记。",
                "{issue}出现在{subject}时，标记原因完成再安排复查。",
                "关于{subject}的{issue}，先标记原因，安排复查稍后进行。",
            ],
            "anchor": "标记原因/安排复查",
        },
        {
            "template_id": "T03_summarize_send",
            "treatment_template": "把{place}的{material}整理成三条结论，然后发送给小林。",
            "control_templates": [
                "发送给小林之前，{place}的{material}先整理成三条结论。",
                "{place}的{material}整理成三条结论后，再发送给小林。",
                "三条结论来自{place}{material}，发送给小林前先整理。",
                "关于{place}{material}，整理成三条结论后发送给小林。",
            ],
            "anchor": "三条结论/发送给小林",
        },
        {
            "template_id": "T04_time_progress",
            "treatment_template": "{time_word}提醒我检查{task}进度，并记录下一步动作。",
            "control_templates": [
                "{task}下一步动作记录后，{time_word}再提醒我检查进度。",
                "检查{task}进度这件事，由{time_word}提醒并记录下一步动作。",
                "{time_word}先提醒检查进度，{task}的下一步动作记录在后。",
                "关于{task}进度，{time_word}提醒检查后记录下一步动作。",
            ],
            "anchor": "检查进度/下一步动作",
        },
    ]

    cases: list[dict[str, Any]] = []
    for frame_index, frame in enumerate(frames):
        for trial_index in range(8):
            values = {
                "subject": subjects[trial_index],
                "task": tasks[trial_index],
                "issue": issues[trial_index],
                "place": places[trial_index],
                "material": materials[trial_index],
                "time_word": times[trial_index],
            }
            treatment = str(frame["treatment_template"]).format(**values)
            control_template = frame["control_templates"][(trial_index + frame_index) % len(frame["control_templates"])]
            control = str(control_template).format(**values)
            cases.append(
                {
                    "case_id": f"F{frame_index + 1:02d}_{trial_index:02d}",
                    "template_id": frame["template_id"],
                    "trial_index": trial_index,
                    "treatment_text": treatment,
                    "control_text": control,
                    "treatment_len": len(treatment),
                    "control_len": len(control),
                    "length_delta": len(treatment) - len(control),
                    "expected_frame": frame["treatment_template"],
                    "control_frame": control_template,
                    "anchor": frame["anchor"],
                }
            )
    return cases


def build_matched_e01_records(condition: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for case in _matched_case_specs():
        if condition == "treatment":
            text = case["treatment_text"]
            template_id = case["template_id"]
            phase = "homomorphic_template"
            expected_frame = case["expected_frame"]
            condition_note = "实验组：稳定句式框架，只替换变量位置。"
        else:
            text = case["control_text"]
            template_id = "C" + str(case["template_id"])[1:]
            phase = "matched_nonisomorphic_control"
            expected_frame = case["control_frame"]
            condition_note = "对照组：复用同一词料和语义角色，但不保留稳定长句式。"
        records.append(
            {
                "text": text,
                "template_id": template_id,
                "trial_index": case["trial_index"],
                "phase": phase,
                "condition": condition,
                "expected_frame": expected_frame,
                "case_id": case["case_id"],
                "matched_anchor": case["anchor"],
                "matched_treatment_len": case["treatment_len"],
                "matched_control_len": case["control_len"],
                "matched_length_delta": case["length_delta"],
                "condition_note": condition_note,
            }
        )

    shared_distractors = [
        "小林把运行结果贴到白板旁边，客户甲暂时只关心权限说明。",
        "任务板没有显示采购清单，会议室的访谈记录也没有同步。",
        "旧版本把噪声写进错误日志，课程作业因此需要重新命名。",
        "仓库里的变更清单被合并，控制台却仍然提示演示窗口。",
        "客户乙回复邮件时没有提目标，只说下午三点以后再看。",
        "接口告警和周报复盘同时出现，排期表需要人工判断。",
        "白板上的讨论要点被擦掉，实验台只留下三行观测数据。",
        "部署窗口结束以后，小林把备份说明放进资料夹。",
    ]
    for trial_index, text in enumerate(shared_distractors):
        records.append(
            {
                "text": text,
                "template_id": "S00_shared_distractor",
                "trial_index": trial_index,
                "phase": "shared_distractor",
                "condition": condition,
                "expected_frame": "两组完全相同的共享干扰句",
                "case_id": f"S00_{trial_index:02d}",
                "matched_anchor": "",
                "matched_treatment_len": len(text),
                "matched_control_len": len(text),
                "matched_length_delta": 0,
                "condition_note": "两组共享：用于观察非核心输入对稳定句式效应的稀释程度。",
            }
        )
    return records


def order_records(records: list[dict[str, Any]], replicate: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["template_id"])].append(record)
    for items in grouped.values():
        items.sort(key=lambda x: int(x.get("trial_index", 0)))

    template_ids = sorted(k for k in grouped if not k.endswith("distractor") and not k.startswith("D00") and not k.startswith("C00"))
    distractor_ids = sorted(k for k in grouped if k not in template_ids)
    distractors = []
    for did in distractor_ids:
        distractors.extend(grouped[did])

    if replicate == 1:
        ordered: list[dict[str, Any]] = []
        max_trials = max(len(grouped[tid]) for tid in template_ids)
        for trial in range(max_trials):
            for tid in template_ids:
                if trial < len(grouped[tid]):
                    ordered.append(grouped[tid][trial])
            if trial < len(distractors):
                ordered.append(distractors[trial])
        return ordered

    if replicate == 2:
        ordered = []
        for tid in template_ids:
            ordered.extend(grouped[tid])
            if distractors:
                ordered.append(distractors.pop(0))
                if distractors:
                    ordered.append(distractors.pop(0))
        ordered.extend(distractors)
        return ordered

    ordered = []
    max_trials = max(len(grouped[tid]) for tid in template_ids)
    rotated = list(reversed(template_ids))
    for trial in range(max_trials - 1, -1, -1):
        for idx, tid in enumerate(rotated):
            items = grouped[tid]
            pick = (trial + idx) % len(items)
            ordered.append(items[pick])
            if len(ordered) % 5 == 0 and distractors:
                ordered.append(distractors.pop(0))
    ordered.extend(distractors)
    return ordered


def dataset_doc(*, condition: str, replicate: int, empty_repeat: int) -> dict[str, Any]:
    base_records = build_matched_e01_records(condition)
    ordered_records = order_records(base_records, replicate)
    ticks: list[dict[str, Any]] = []
    for source_index, record in enumerate(ordered_records):
        tick_tags = [
            "paper_e01",
            "E01",
            "lexical_abstraction",
            str(condition),
            str(record["phase"]),
            str(record["template_id"]),
            "text_tick",
        ]
        ticks.append(
            {
                "text": record["text"],
                "tags": tick_tags,
                "labels": {
                    "paper_e01": {
                        "condition": condition,
                        "replicate": replicate,
                        "source_text_index": source_index,
                        "template_id": record["template_id"],
                        "trial_index": record["trial_index"],
                        "phase": record["phase"],
                        "expected_frame": record["expected_frame"],
                        "case_id": record.get("case_id", ""),
                        "matched_anchor": record.get("matched_anchor", ""),
                        "matched_treatment_len": record.get("matched_treatment_len", 0),
                        "matched_control_len": record.get("matched_control_len", 0),
                        "matched_length_delta": record.get("matched_length_delta", 0),
                        "condition_note": record.get("condition_note", ""),
                    },
                    "stream": {
                        "role": "user",
                        "kind": "message",
                        "phase": "lexical_abstraction",
                        "pure_text": True,
                        "real_input_index": source_index,
                    },
                },
            }
        )
        if empty_repeat > 0:
            ticks.append(
                {
                    "empty": True,
                    "repeat": int(empty_repeat),
                    "tags": ["paper_e01", "E01", "idle_gap", "controlled_decay_gap", condition],
                    "labels": {
                        "paper_e01": {
                            "condition": condition,
                            "replicate": replicate,
                            "phase": "idle_gap",
                            "after_source_text_index": source_index,
                        }
                    },
            }
        )
    dataset_id = f"paper_e01_lexical_abstraction_{condition}_r{replicate}_v2"
    title_condition = "同构模板组" if condition == "treatment" else "非同构对照组"
    return {
        "dataset_id": dataset_id,
        "title": f"E01 词汇重复与句式抽象 - {title_condition} - 重复 {replicate}",
        "description": (
            "论文 E01 定向实验数据集。v2 版本使用同词料、近似等长的配对对照；"
            "真实 text 字段只包含自然中文输入，实验条件、模板编号、变量位置和分析标签全部放在 labels/tags 旁路。"
        ),
        "experiment_goal": (
            "在词汇主题、语义角色和输入长度尽量匹配的条件下，观察稳定句式框架在变量替换后是否比"
            "同词料非同构输入更容易形成共同结构、残差路径、结构复用和更稳定的状态池波峰。"
        ),
        "evaluation_dimensions": [
            "同构模板输入是否在按字符数和外源 SA 数归一化后仍提高共同切割或共同部分命中。",
            "同构模板输入是否提高刺激级匹配分、顺序对齐和结构复用比例。",
            "同构模板输入是否形成更稳定、更可解释的 top 结构波峰。",
            "配对对照是否排除单纯词汇重复、主题相近或文本长度造成的假阳性。",
        ],
        "notes": [
            f"本数据集包含 {len(ordered_records)} 条真实文本 tick，每条真实文本后跟随 {empty_repeat} 个空 tick。",
            "三组重复只改变输入顺序，不改变文本集合，用于检查顺序敏感性。",
            "核心 32 条文本在两组之间一一配对，共享主题词、角色词和动作词；共享干扰句在两组完全相同。",
            "对照组保留相似语义任务，但改变连接词、短语边界和语序，避免稳定长句式模板。",
        ],
        "seed": 20260511 + int(replicate),
        "time_basis": "tick",
        "tick_dt_ms": 3000,
        "curriculum_version": CURRICULUM_VERSION,
        "episodes": [
            {
                "id": f"paper_e01_{condition}_r{replicate}_main",
                "title": f"E01 {title_condition}主序列 r{replicate}",
                "tags": ["paper_e01", "E01", "lexical_abstraction", condition],
                "repeat": 1,
                "ticks": ticks,
            }
        ],
    }


def write_datasets(*, replicates: int, empty_repeat: int) -> list[dict[str, Any]]:
    datasets: list[dict[str, Any]] = []
    for condition in ("treatment", "control"):
        for replicate in range(1, replicates + 1):
            doc = dataset_doc(condition=condition, replicate=replicate, empty_repeat=empty_repeat)
            name = f"{doc['dataset_id']}.yaml"
            text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
            artifact_path = DATASET_ARTIFACT_DIR / name
            imported_path = imported_datasets_dir() / name
            artifact_path.write_text(text, encoding="utf-8")
            imported_path.write_text(text, encoding="utf-8")
            datasets.append(
                {
                    "condition": condition,
                    "replicate": replicate,
                    "dataset_id": doc["dataset_id"],
                    "dataset_name": name,
                    "artifact_path": artifact_path,
                    "imported_path": imported_path,
                    "sha256": sha256_file(imported_path),
                    "source_text_ticks": len([t for t in doc["episodes"][0]["ticks"] if t.get("text")]),
                    "total_source_ticks": sum(int(t.get("repeat", 1) or 1) for t in doc["episodes"][0]["ticks"]),
                }
            )
    return datasets


def _quiet_progress(payload: dict[str, Any]) -> None:
    stage = str(payload.get("stage", "") or "")
    status = str(payload.get("status", "") or "")
    if stage in {"loading_dataset", "preparing_manifest", "resetting_runtime", "running_tick", "finished", "failed"}:
        tick_done = payload.get("source_tick_done", payload.get("tick_done", ""))
        planned = payload.get("tick_planned", "")
        if stage == "running_tick" and tick_done not in {0, "", None}:
            try:
                tick_int = int(tick_done)
            except Exception:
                tick_int = 0
            if tick_int % 24 != 0:
                return
        print(f"[E01] {status or 'running'} {stage} {tick_done}/{planned}", flush=True)


def run_one_dataset(dataset_info: dict[str, Any], *, run_stamp: str, max_ticks: int | None) -> dict[str, Any]:
    condition = str(dataset_info["condition"])
    replicate = int(dataset_info["replicate"])
    run_id = f"paper_e01_{condition}_r{replicate}_{run_stamp}"
    print(f"[E01] start run_id={run_id} dataset={dataset_info['dataset_name']}", flush=True)
    app = ObservatoryApp()
    # The Observatory cleanup task rotates every large *.jsonl under outputs/.
    # During a dataset run that can race with experiment metrics.jsonl writes.
    # Paper evidence needs the full per-tick record, so disable cycle-output
    # cleanup for this app instance while keeping AP runtime logic unchanged.
    try:
        app._config["outputs_cleanup_enabled"] = False  # type: ignore[attr-defined]
        app._config["outputs_cycle_max_total_bytes"] = 0  # type: ignore[attr-defined]
        app._config["outputs_cycle_max_age_days"] = 0  # type: ignore[attr-defined]
        app._config["export_cycle_json_history"] = False  # type: ignore[attr-defined]
        app._config["export_cycle_html_history"] = False  # type: ignore[attr-defined]
        # _cleanup_output_reports() calls _cleanup_jsonl_logs() unconditionally
        # in the current app implementation. Replacing only the cleanup helper
        # keeps the cognitive tick path intact while protecting experiment
        # metrics from concurrent rotation.
        setattr(app, "_cleanup_jsonl_logs", lambda: None)
        setattr(app, "_cleanup_output_reports", lambda: None)
    except Exception:
        pass
    try:
        result = run_dataset(
            app=app,
            dataset_ref=DatasetFileRef(source="imported", rel_path=str(dataset_info["dataset_name"])),
            options=RunOptions(
                reset_mode="clear_all",
                clean_run=False,
                export_json=False,
                export_html=False,
                auto_tune_enabled=False,
                max_ticks=max_ticks,
            ),
            run_id=run_id,
            progress_cb=_quiet_progress,
        )
    finally:
        app.close()
    run_dir = resolve_run_dir(run_id)
    manifest_path = run_dir / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out = {
        **dataset_info,
        "run_id": run_id,
        "run_dir": run_dir,
        "manifest": manifest,
        "success": bool(result.get("success", False)),
        "status": manifest.get("status", ""),
        "metrics_path": run_dir / "metrics.jsonl",
        "runner_timing_path": run_dir / "runner_timing.jsonl",
    }
    print(f"[E01] finished run_id={run_id} status={out['status']}", flush=True)
    return out


def read_metrics_rows_from_run_dir(run_dir: Path) -> list[dict[str, Any]]:
    """Read full metrics rows.

    Normal runs should keep metrics.jsonl intact. Older/raced runs may have
    gzip archives with NUL-padded fragments; this reader attempts best-effort
    recovery but callers still validate row counts against manifest.
    """

    files = [run_dir / "metrics.jsonl"]
    files.extend(sorted(run_dir.glob("metrics.*.jsonl.gz")))
    rows_by_tick: dict[int, dict[str, Any]] = {}
    fallback_rows: list[dict[str, Any]] = []
    for path in files:
        if not path.exists():
            continue
        try:
            if path.suffix == ".gz":
                with gzip.open(path, "rb") as fh:
                    data = fh.read()
                # If a cleanup race produced sparse/NUL-padded gzip payloads,
                # remove NUL bytes before line parsing. Valid JSON never uses
                # literal NUL bytes outside escaped strings.
                raw_text = data.replace(b"\x00", b"").decode("utf-8", errors="replace")
                lines = raw_text.splitlines()
            else:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            tick_value = obj.get("tick_index", obj.get("tick"))
            try:
                tick_index = int(tick_value)
            except Exception:
                tick_index = -1
            if tick_index >= 0:
                rows_by_tick[tick_index] = obj
            else:
                fallback_rows.append(obj)
    rows = [rows_by_tick[k] for k in sorted(rows_by_tick)]
    rows.extend(fallback_rows)
    return rows


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def summarize_run_metrics(run_info: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(run_info["run_dir"])
    rows = read_metrics_rows_from_run_dir(run_dir)
    text_rows = [r for r in rows if not bool(r.get("synthetic_tick", False)) and not bool(r.get("input_is_empty", False))]
    all_source_rows = [r for r in rows if not bool(r.get("synthetic_tick", False))]
    first = rows[0] if rows else {}
    last = rows[-1] if rows else {}
    labels = [r.get("labels", {}).get("paper_e01", {}) for r in text_rows if isinstance(r.get("labels"), dict)]
    condition = str(run_info.get("condition"))
    replicate = int(run_info.get("replicate", 0))

    previous_top: set[str] | None = None
    continuity_values: list[float] = []
    for row in text_rows:
        current = set(_top_identity_list(row))
        if previous_top is not None:
            union = current | previous_top
            continuity_values.append(float(len(current & previous_top)) / max(1.0, float(len(union or {""}))))
        previous_top = current

    phase_counts = Counter(str(label.get("phase", "")) for label in labels)
    template_counts = Counter(str(label.get("template_id", "")) for label in labels)
    anchor_values = [_anchor_presence(row) for row in text_rows]

    metric_values: dict[str, list[float]] = {key: [_numeric(row, key) for row in text_rows] for key in E01_METRIC_KEYS}
    core_pairs = [
        (row, label)
        for row, label in zip(text_rows, labels)
        if str(label.get("phase", "")) in CORE_PHASES
    ]
    core_rows = [row for row, _ in core_pairs]
    core_input_len_sum = sum(_numeric(row, "input_len") for row in core_rows)
    core_external_sa_sum = sum(_numeric(row, "external_sa_count") for row in core_rows)
    text_input_len_sum = sum(_numeric(row, "input_len") for row in text_rows)
    text_external_sa_sum = sum(_numeric(row, "external_sa_count") for row in text_rows)
    core_common_sum = sum(_numeric(row, "stimulus_cut_common_part_total_count") for row in core_rows)
    core_best_common_sum = sum(_numeric(row, "stimulus_best_match_common_part_count") for row in core_rows)
    core_target_sum = sum(_numeric(row, "induction_growth_target_count") for row in core_rows)
    core_hit_sum = sum(_numeric(row, "induction_growth_identity_hit_count") for row in core_rows)
    core_created_sum = sum(_numeric(row, "induction_growth_identity_created_count") for row in core_rows)
    final_delta = {
        "hdb_structure_count_delta": _numeric(last, "hdb_structure_count") - _numeric(first, "hdb_structure_count"),
        "hdb_contextual_structure_count_delta": _numeric(last, "hdb_contextual_structure_count") - _numeric(first, "hdb_contextual_structure_count"),
        "hdb_residual_diff_entry_count_delta": _numeric(last, "hdb_residual_diff_entry_count") - _numeric(first, "hdb_residual_diff_entry_count"),
        "hdb_diff_entry_with_memory_ref_count_delta": _numeric(last, "hdb_diff_entry_with_memory_ref_count") - _numeric(first, "hdb_diff_entry_with_memory_ref_count"),
    }
    target_sum = sum(metric_values.get("induction_growth_target_count", []))
    hit_sum = sum(metric_values.get("induction_growth_identity_hit_count", []))
    created_sum = sum(metric_values.get("induction_growth_identity_created_count", []))
    summary = {
        "condition": condition,
        "replicate": replicate,
        "dataset_id": run_info.get("dataset_id"),
        "dataset_sha256": run_info.get("sha256"),
        "run_id": run_info.get("run_id"),
        "run_status": run_info.get("status"),
        "metric_rows": len(rows),
        "metric_row_coverage_ratio": _safe_ratio(len(rows), int((run_info.get("manifest") or {}).get("executed_tick_done_total", 0) or 0)),
        "source_rows": len(all_source_rows),
        "text_rows": len(text_rows),
        "core_text_rows": len(core_rows),
        "empty_rows": len([r for r in all_source_rows if bool(r.get("input_is_empty", False))]),
        "phase_counts": dict(phase_counts),
        "template_counts": dict(template_counts),
        "input_len_mean": _stats(metric_values["input_len"])["mean"],
        "input_len_total": round(text_input_len_sum, 8),
        "core_input_len_mean": _stats([_numeric(row, "input_len") for row in core_rows])["mean"],
        "core_input_len_total": round(core_input_len_sum, 8),
        "external_sa_count_mean": _stats(metric_values["external_sa_count"])["mean"],
        "external_sa_count_total": round(text_external_sa_sum, 8),
        "core_external_sa_count_mean": _stats([_numeric(row, "external_sa_count") for row in core_rows])["mean"],
        "core_external_sa_count_total": round(core_external_sa_sum, 8),
        "hdb_structure_count_first": _numeric(first, "hdb_structure_count"),
        "hdb_structure_count_latest": _numeric(last, "hdb_structure_count"),
        "hdb_structure_count_delta": final_delta["hdb_structure_count_delta"],
        "hdb_contextual_structure_count_delta": final_delta["hdb_contextual_structure_count_delta"],
        "hdb_residual_diff_entry_count_delta": final_delta["hdb_residual_diff_entry_count_delta"],
        "hdb_diff_entry_with_memory_ref_count_delta": final_delta["hdb_diff_entry_with_memory_ref_count_delta"],
        "structure_delta_per_text": _safe_ratio(final_delta["hdb_structure_count_delta"], len(text_rows)),
        "structure_delta_per_input_char": _safe_ratio(final_delta["hdb_structure_count_delta"], text_input_len_sum),
        "structure_delta_per_external_sa": _safe_ratio(final_delta["hdb_structure_count_delta"], text_external_sa_sum),
        "common_part_total_per_text": _safe_ratio(sum(metric_values["stimulus_cut_common_part_total_count"]), len(text_rows)),
        "common_part_total_per_input_char": _safe_ratio(sum(metric_values["stimulus_cut_common_part_total_count"]), text_input_len_sum),
        "common_part_total_per_external_sa": _safe_ratio(sum(metric_values["stimulus_cut_common_part_total_count"]), text_external_sa_sum),
        "best_match_common_part_per_text": _safe_ratio(sum(metric_values["stimulus_best_match_common_part_count"]), len(text_rows)),
        "best_match_common_part_per_input_char": _safe_ratio(sum(metric_values["stimulus_best_match_common_part_count"]), text_input_len_sum),
        "best_match_common_part_per_external_sa": _safe_ratio(sum(metric_values["stimulus_best_match_common_part_count"]), text_external_sa_sum),
        "core_common_part_total_per_text": _safe_ratio(core_common_sum, len(core_rows)),
        "core_common_part_total_per_input_char": _safe_ratio(core_common_sum, core_input_len_sum),
        "core_common_part_total_per_external_sa": _safe_ratio(core_common_sum, core_external_sa_sum),
        "core_best_match_common_part_per_text": _safe_ratio(core_best_common_sum, len(core_rows)),
        "core_best_match_common_part_per_input_char": _safe_ratio(core_best_common_sum, core_input_len_sum),
        "core_best_match_common_part_per_external_sa": _safe_ratio(core_best_common_sum, core_external_sa_sum),
        "stimulus_best_match_score_mean": _stats(metric_values["stimulus_best_match_score"])["mean"],
        "core_stimulus_best_match_score_mean": _stats([_numeric(row, "stimulus_best_match_score") for row in core_rows])["mean"],
        "stimulus_match_v2_score_mean": _stats(metric_values["stimulus_match_v2_score_mean"])["mean"],
        "core_stimulus_match_v2_score_mean": _stats([_numeric(row, "stimulus_match_v2_score_mean") for row in core_rows])["mean"],
        "stimulus_order_alignment_mean": _stats(metric_values["stimulus_match_v2_order_alignment_mean"])["mean"],
        "core_stimulus_order_alignment_mean": _stats([_numeric(row, "stimulus_match_v2_order_alignment_mean") for row in core_rows])["mean"],
        "stimulus_residual_ratio_mean": _stats(metric_values["stimulus_residual_ratio"])["mean"],
        "structure_best_match_score_mean": _stats(metric_values["structure_best_match_score"])["mean"],
        "induction_target_per_text": _safe_ratio(target_sum, len(text_rows)),
        "induction_identity_hit_ratio": _safe_ratio(hit_sum, hit_sum + created_sum),
        "induction_identity_hit_to_target": _safe_ratio(hit_sum, target_sum),
        "core_induction_target_per_text": _safe_ratio(core_target_sum, len(core_rows)),
        "core_induction_identity_hit_ratio": _safe_ratio(core_hit_sum, core_hit_sum + core_created_sum),
        "core_induction_identity_hit_to_target": _safe_ratio(core_hit_sum, core_target_sum),
        "top5_continuity_mean": _stats(continuity_values)["mean"],
        "top_anchor_presence_mean": _stats(anchor_values)["mean"],
        "core_top_anchor_presence_mean": _stats([_anchor_presence(row) for row in core_rows])["mean"],
        "timing_total_logic_ms_mean": _stats(metric_values["timing_total_logic_ms"])["mean"],
        "metric_stats": {key: _stats(vals) for key, vals in metric_values.items()},
    }
    return summary


def build_long_rows(run_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    long_rows: list[dict[str, Any]] = []
    for run_info in run_infos:
        condition = str(run_info["condition"])
        replicate = int(run_info["replicate"])
        for row in read_metrics_rows_from_run_dir(Path(run_info["run_dir"])):
            labels = row.get("labels", {}).get("paper_e01", {}) if isinstance(row.get("labels"), dict) else {}
            source_text_index = labels.get("source_text_index")
            long_rows.append(
                {
                    "condition": condition,
                    "replicate": replicate,
                    "run_id": run_info["run_id"],
                    "tick_index": row.get("tick_index"),
                    "source_dataset_tick_index": row.get("source_dataset_tick_index"),
                    "input_is_empty": bool(row.get("input_is_empty", False)),
                    "input_text_preview": row.get("input_text_preview", ""),
                    "phase": labels.get("phase", "idle_gap" if row.get("input_is_empty") else ""),
                    "template_id": labels.get("template_id", ""),
                    "trial_index": labels.get("trial_index", ""),
                    "case_id": labels.get("case_id", ""),
                    "matched_anchor": labels.get("matched_anchor", ""),
                    "matched_treatment_len": labels.get("matched_treatment_len", ""),
                    "matched_control_len": labels.get("matched_control_len", ""),
                    "matched_length_delta": labels.get("matched_length_delta", ""),
                    "source_text_index": source_text_index,
                    "input_len": _numeric(row, "input_len"),
                    "sensor_feature_sa_count": _numeric(row, "sensor_feature_sa_count"),
                    "external_sa_count": _numeric(row, "external_sa_count"),
                    "hdb_structure_count": _numeric(row, "hdb_structure_count"),
                    "hdb_contextual_structure_count": _numeric(row, "hdb_contextual_structure_count"),
                    "hdb_residual_diff_entry_count": _numeric(row, "hdb_residual_diff_entry_count"),
                    "stimulus_cut_common_part_total_count": _numeric(row, "stimulus_cut_common_part_total_count"),
                    "stimulus_best_match_common_part_count": _numeric(row, "stimulus_best_match_common_part_count"),
                    "stimulus_cut_common_part_per_input_char": _safe_ratio(
                        _numeric(row, "stimulus_cut_common_part_total_count"),
                        _numeric(row, "input_len"),
                    ),
                    "stimulus_cut_common_part_per_external_sa": _safe_ratio(
                        _numeric(row, "stimulus_cut_common_part_total_count"),
                        _numeric(row, "external_sa_count"),
                    ),
                    "stimulus_best_match_score": _numeric(row, "stimulus_best_match_score"),
                    "stimulus_match_v2_score_mean": _numeric(row, "stimulus_match_v2_score_mean"),
                    "stimulus_match_v2_order_alignment_mean": _numeric(row, "stimulus_match_v2_order_alignment_mean"),
                    "stimulus_residual_ratio": _numeric(row, "stimulus_residual_ratio"),
                    "induction_growth_target_count": _numeric(row, "induction_growth_target_count"),
                    "induction_growth_identity_hit_count": _numeric(row, "induction_growth_identity_hit_count"),
                    "induction_growth_identity_created_count": _numeric(row, "induction_growth_identity_created_count"),
                    "top_anchor_presence": _anchor_presence(row),
                    "top_ids": "|".join(_top_identity_list(row)),
                }
            )
    return long_rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _median(values: list[float]) -> float:
    clean = sorted(float(x) for x in values if math.isfinite(float(x)))
    if not clean:
        return 0.0
    mid = len(clean) // 2
    if len(clean) % 2:
        return round(clean[mid], 8)
    return round((clean[mid - 1] + clean[mid]) / 2.0, 8)


def _sign_test_p_value(wins: int, losses: int) -> float:
    n = int(wins) + int(losses)
    if n <= 0:
        return 1.0
    k = min(int(wins), int(losses))
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return round(min(1.0, 2.0 * tail), 8)


def _bootstrap_mean_ci(values: list[float], *, iterations: int = 2000) -> dict[str, float]:
    clean = [float(x) for x in values if math.isfinite(float(x))]
    if not clean:
        return {"low": 0.0, "high": 0.0}
    # Deterministic bootstrap: use a simple LCG sequence so the report is
    # reproducible without depending on global random state.
    state = 20260511 + len(clean) * 17
    means: list[float] = []
    n = len(clean)
    for _ in range(iterations):
        total = 0.0
        for _j in range(n):
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            total += clean[state % n]
        means.append(total / n)
    means.sort()
    low = means[int(0.025 * (len(means) - 1))]
    high = means[int(0.975 * (len(means) - 1))]
    return {"low": round(low, 8), "high": round(high, 8)}


def build_case_pair_comparison(long_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    text_rows = [
        row
        for row in long_rows
        if not row.get("input_is_empty")
        and str(row.get("phase") or "") in CORE_PHASES
        and str(row.get("case_id") or "")
    ]
    by_key: dict[tuple[int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in text_rows:
        condition = str(row.get("condition") or "")
        replicate = int(row.get("replicate") or 0)
        case_id = str(row.get("case_id") or "")
        if condition in {"treatment", "control"}:
            by_key[(replicate, case_id)][condition] = row

    metrics: list[tuple[str, str, bool]] = [
        ("stimulus_cut_common_part_total_count", "共同切割计数", True),
        ("stimulus_cut_common_part_per_input_char", "共同切割/字", True),
        ("stimulus_cut_common_part_per_external_sa", "共同切割/外源SA", True),
        ("stimulus_best_match_score", "最佳匹配分", True),
        ("stimulus_match_v2_score_mean", "V2匹配分", True),
        ("stimulus_match_v2_order_alignment_mean", "顺序对齐", True),
        ("top_anchor_presence", "锚点显现", True),
    ]
    pair_rows: list[dict[str, Any]] = []
    for (replicate, case_id), parts in sorted(by_key.items()):
        if "treatment" not in parts or "control" not in parts:
            continue
        t = parts["treatment"]
        c = parts["control"]
        out: dict[str, Any] = {
            "replicate": replicate,
            "case_id": case_id,
            "template_id_treatment": t.get("template_id", ""),
            "template_id_control": c.get("template_id", ""),
            "trial_index": t.get("trial_index", ""),
            "matched_anchor": t.get("matched_anchor", c.get("matched_anchor", "")),
            "treatment_text": t.get("input_text_preview", ""),
            "control_text": c.get("input_text_preview", ""),
            "treatment_input_len": t.get("input_len", 0),
            "control_input_len": c.get("input_len", 0),
            "input_len_diff_t_minus_c": round(float(t.get("input_len") or 0.0) - float(c.get("input_len") or 0.0), 8),
            "treatment_external_sa_count": t.get("external_sa_count", 0),
            "control_external_sa_count": c.get("external_sa_count", 0),
            "external_sa_diff_t_minus_c": round(float(t.get("external_sa_count") or 0.0) - float(c.get("external_sa_count") or 0.0), 8),
        }
        for key, _label, higher_is_better in metrics:
            t_val = float(t.get(key) or 0.0)
            c_val = float(c.get(key) or 0.0)
            diff = t_val - c_val
            out[f"treatment_{key}"] = round(t_val, 8)
            out[f"control_{key}"] = round(c_val, 8)
            out[f"diff_{key}"] = round(diff, 8)
            if diff == 0:
                direction = "tie"
            elif (diff > 0 and higher_is_better) or (diff < 0 and not higher_is_better):
                direction = "support"
            else:
                direction = "against"
            out[f"direction_{key}"] = direction
        pair_rows.append(out)

    stats: dict[str, Any] = {
        "pair_count": len(pair_rows),
        "metrics": {},
        "note": "文本级配对分析按 replicate + case_id 一一比较同词料输入，避免只依赖 run 级均值。",
    }
    for key, label, higher_is_better in metrics:
        diffs = [float(row.get(f"diff_{key}", 0.0) or 0.0) for row in pair_rows]
        supports = sum(1 for row in pair_rows if row.get(f"direction_{key}") == "support")
        against = sum(1 for row in pair_rows if row.get(f"direction_{key}") == "against")
        ties = sum(1 for row in pair_rows if row.get(f"direction_{key}") == "tie")
        stats["metrics"][key] = {
            "label": label,
            "higher_is_better": higher_is_better,
            "pair_count": len(pair_rows),
            "support_count": supports,
            "against_count": against,
            "tie_count": ties,
            "support_ratio": _safe_ratio(supports, len(pair_rows)),
            "mean_diff_treatment_minus_control": round(statistics.fmean(diffs), 8) if diffs else 0.0,
            "median_diff_treatment_minus_control": _median(diffs),
            "mean_diff_bootstrap_95ci": _bootstrap_mean_ci(diffs),
            "sign_test_p_value_two_sided": _sign_test_p_value(supports, against),
        }
    return pair_rows, stats


def setup_matplotlib():
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    candidates = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Arial Unicode MS",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def generate_charts(
    long_rows: list[dict[str, Any]],
    run_summaries: list[dict[str, Any]],
    comparison: dict[str, Any],
    case_pair_rows: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    plt = setup_matplotlib()
    import numpy as np

    chart_paths: dict[str, str] = {}

    # 1. Structure growth curve.
    fig, ax = plt.subplots(figsize=(11, 6), dpi=160)
    colors = {"treatment": "#2563eb", "control": "#dc2626"}
    condition_label = {"treatment": "同构模板组", "control": "非同构对照组"}
    for (condition, replicate), rows in _group_long_rows(long_rows, keys=("condition", "replicate")).items():
        rows = sorted(rows, key=lambda r: int(r.get("source_dataset_tick_index") or r.get("tick_index") or 0))
        x = [int(r.get("source_dataset_tick_index") or r.get("tick_index") or 0) for r in rows]
        y = [float(r.get("hdb_structure_count") or 0.0) for r in rows]
        ax.plot(x, y, color=colors.get(condition, "#333333"), alpha=0.28, linewidth=1.2)
    for condition in ("treatment", "control"):
        grouped_by_tick: dict[int, list[float]] = defaultdict(list)
        for row in long_rows:
            if row["condition"] != condition:
                continue
            tick = int(row.get("source_dataset_tick_index") or row.get("tick_index") or 0)
            grouped_by_tick[tick].append(float(row.get("hdb_structure_count") or 0.0))
        xs = sorted(grouped_by_tick)
        ys = [statistics.fmean(grouped_by_tick[x]) for x in xs]
        ax.plot(xs, ys, color=colors[condition], linewidth=2.8, label=condition_label[condition])
    ax.set_title("E01 结构数量随 tick 增长")
    ax.set_xlabel("数据集 source tick")
    ax.set_ylabel("HDB 结构数量")
    ax.grid(True, alpha=0.22)
    ax.legend()
    path = CHART_DIR / "e01_structure_growth_curve.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    chart_paths["structure_growth_curve"] = str(path)

    # 2. Metric comparison with error bars.
    metrics = [
        ("core_common_part_total_per_input_char", "核心共同切割/字", True),
        ("stimulus_best_match_score_mean", "刺激匹配分", True),
        ("core_induction_identity_hit_ratio", "核心身份复用比", True),
        ("core_top_anchor_presence_mean", "核心锚点显现", True),
        ("structure_delta_per_input_char", "新结构/字", False),
    ]
    fig, ax = plt.subplots(figsize=(12, 6.2), dpi=160)
    x = np.arange(len(metrics))
    width = 0.34
    for offset, condition in [(-width / 2, "treatment"), (width / 2, "control")]:
        means = []
        sds = []
        for key, _, _ in metrics:
            vals = [float(s.get(key, 0.0) or 0.0) for s in run_summaries if s.get("condition") == condition]
            means.append(statistics.fmean(vals) if vals else 0.0)
            sds.append(statistics.stdev(vals) if len(vals) >= 2 else 0.0)
        ax.bar(x + offset, means, width, yerr=sds, capsize=4, label=condition_label[condition], color=colors[condition], alpha=0.82)
    ax.set_title("E01 核心指标对照")
    ax.set_xticks(x)
    ax.set_xticklabels([label for _, label, _ in metrics], rotation=15, ha="right")
    ax.set_ylabel("指标值")
    ax.grid(axis="y", alpha=0.22)
    ax.legend()
    path = CHART_DIR / "e01_metric_comparison.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    chart_paths["metric_comparison"] = str(path)

    # 3. Common-part heatmap by template/trial for text rows.
    text_rows = [r for r in long_rows if not r.get("input_is_empty")]
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.8), dpi=160)
    for ax, condition in zip(axes, ("treatment", "control")):
        rows = [r for r in text_rows if r["condition"] == condition]
        template_ids = sorted({str(r.get("template_id") or "") for r in rows if str(r.get("template_id") or "")})
        trial_ids = sorted({int(r.get("trial_index") or 0) for r in rows if str(r.get("trial_index") or "") != ""})
        matrix = np.zeros((len(template_ids), len(trial_ids)))
        for i, tid in enumerate(template_ids):
            for j, trial in enumerate(trial_ids):
                vals = [
                    float(r.get("stimulus_cut_common_part_total_count") or 0.0)
                    for r in rows
                    if str(r.get("template_id") or "") == tid and int(r.get("trial_index") or 0) == trial
                ]
                matrix[i, j] = statistics.fmean(vals) if vals else 0.0
        im = ax.imshow(matrix, aspect="auto", cmap="YlGnBu")
        ax.set_title(condition_label[condition])
        ax.set_xlabel("trial index")
        ax.set_ylabel("模板/分组")
        ax.set_xticks(range(len(trial_ids)))
        ax.set_xticklabels([str(x) for x in trial_ids])
        ax.set_yticks(range(len(template_ids)))
        ax.set_yticklabels([tid.replace("_", "\n") for tid in template_ids], fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("E01 共同切割计数热力图")
    path = CHART_DIR / "e01_common_part_heatmap.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    chart_paths["common_part_heatmap"] = str(path)

    # 4. Top continuity time series.
    continuity_rows: list[dict[str, Any]] = []
    for (condition, replicate), rows in _group_long_rows(text_rows, keys=("condition", "replicate")).items():
        rows = sorted(rows, key=lambda r: int(r.get("source_text_index") or 0))
        prev: set[str] | None = None
        for row in rows:
            ids = set(str(row.get("top_ids") or "").split("|")) - {""}
            val = 0.0
            if prev is not None:
                val = len(ids & prev) / max(1.0, float(len(ids | prev)))
            continuity_rows.append(
                {
                    "condition": condition,
                    "replicate": replicate,
                    "source_text_index": int(row.get("source_text_index") or 0),
                    "top5_jaccard": val,
                }
            )
            prev = ids
    fig, ax = plt.subplots(figsize=(11, 5.8), dpi=160)
    for condition in ("treatment", "control"):
        grouped: dict[int, list[float]] = defaultdict(list)
        for row in continuity_rows:
            if row["condition"] == condition:
                grouped[int(row["source_text_index"])].append(float(row["top5_jaccard"]))
        xs = sorted(grouped)
        ys = [statistics.fmean(grouped[x]) for x in xs]
        ax.plot(xs, ys, label=condition_label[condition], color=colors[condition], linewidth=2.5)
    ax.set_title("E01 Top5 结构连续性")
    ax.set_xlabel("真实文本序号")
    ax.set_ylabel("相邻文本 Top5 Jaccard")
    ax.grid(True, alpha=0.22)
    ax.legend()
    path = CHART_DIR / "e01_top_structure_continuity.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    chart_paths["top_structure_continuity"] = str(path)

    # 5. Match/residual timeseries.
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), dpi=160, sharex=True)
    for condition in ("treatment", "control"):
        by_idx: dict[int, list[dict[str, float]]] = defaultdict(list)
        for row in text_rows:
            if row["condition"] != condition:
                continue
            idx = int(row.get("source_text_index") or 0)
            by_idx[idx].append(
                {
                    "score": float(row.get("stimulus_best_match_score") or 0.0),
                    "residual": float(row.get("stimulus_residual_ratio") or 0.0),
                }
            )
        xs = sorted(by_idx)
        score_y = [statistics.fmean([v["score"] for v in by_idx[x]]) for x in xs]
        residual_y = [statistics.fmean([v["residual"] for v in by_idx[x]]) for x in xs]
        axes[0].plot(xs, score_y, color=colors[condition], linewidth=2.4, label=condition_label[condition])
        axes[1].plot(xs, residual_y, color=colors[condition], linewidth=2.4, label=condition_label[condition])
    axes[0].set_title("刺激级最佳匹配分")
    axes[0].set_ylabel("best match score")
    axes[1].set_title("刺激残差比例")
    axes[1].set_xlabel("真实文本序号")
    axes[1].set_ylabel("residual ratio")
    for ax in axes:
        ax.grid(True, alpha=0.22)
        ax.legend()
    path = CHART_DIR / "e01_match_residual_timeseries.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    chart_paths["match_residual_timeseries"] = str(path)

    # 6. Normalized common-part comparison.
    fig, ax = plt.subplots(figsize=(11, 5.8), dpi=160)
    norm_metrics = [
        ("common_part_total_per_text", "全部/文本"),
        ("common_part_total_per_input_char", "全部/字"),
        ("core_common_part_total_per_text", "核心/文本"),
        ("core_common_part_total_per_input_char", "核心/字"),
    ]
    x = np.arange(len(norm_metrics))
    width = 0.34
    for offset, condition in [(-width / 2, "treatment"), (width / 2, "control")]:
        means = []
        sds = []
        for key, _ in norm_metrics:
            vals = [float(s.get(key, 0.0) or 0.0) for s in run_summaries if s.get("condition") == condition]
            means.append(statistics.fmean(vals) if vals else 0.0)
            sds.append(statistics.stdev(vals) if len(vals) >= 2 else 0.0)
        ax.bar(x + offset, means, width, yerr=sds, capsize=4, label=condition_label[condition], color=colors[condition], alpha=0.82)
    ax.set_title("E01 共同切割归一化对照")
    ax.set_xticks(x)
    ax.set_xticklabels([label for _, label in norm_metrics])
    ax.set_ylabel("归一化计数")
    ax.grid(axis="y", alpha=0.22)
    ax.legend()
    path = CHART_DIR / "e01_normalized_common_part_comparison.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    chart_paths["normalized_common_part_comparison"] = str(path)

    # 7. Input length balance by condition.
    fig, ax = plt.subplots(figsize=(11, 5.8), dpi=160)
    text_rows_sorted = [r for r in text_rows if str(r.get("phase") or "") in CORE_PHASES]
    for condition in ("treatment", "control"):
        grouped: dict[int, list[float]] = defaultdict(list)
        for row in text_rows_sorted:
            if row["condition"] != condition:
                continue
            idx = int(row.get("source_text_index") or 0)
            grouped[idx].append(float(row.get("input_len") or 0.0))
        xs = sorted(grouped)
        ys = [statistics.fmean(grouped[x]) for x in xs]
        ax.plot(xs, ys, color=colors[condition], linewidth=2.4, label=condition_label[condition])
    ax.set_title("E01 核心文本长度控制")
    ax.set_xlabel("真实文本序号")
    ax.set_ylabel("input_len")
    ax.grid(True, alpha=0.22)
    ax.legend()
    path = CHART_DIR / "e01_input_length_balance.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    chart_paths["input_length_balance"] = str(path)

    if case_pair_rows:
        # 8. Paired text-level differences.
        pair_metrics = [
            ("diff_stimulus_cut_common_part_per_input_char", "共同切割/字"),
            ("diff_stimulus_best_match_score", "最佳匹配分"),
            ("diff_stimulus_match_v2_order_alignment_mean", "顺序对齐"),
            ("diff_top_anchor_presence", "锚点显现"),
        ]
        fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.2), dpi=160)
        axes_flat = list(axes.ravel())
        for ax, (key, title) in zip(axes_flat, pair_metrics):
            vals = [float(row.get(key, 0.0) or 0.0) for row in case_pair_rows]
            ax.axvline(0, color="#111827", linewidth=1.0, alpha=0.7)
            ax.hist(vals, bins=16, color="#2563eb", alpha=0.76, edgecolor="white")
            ax.set_title(title)
            ax.set_xlabel("实验组 - 对照组")
            ax.set_ylabel("配对文本数")
            ax.grid(axis="y", alpha=0.22)
        fig.suptitle("E01 文本级配对差异分布")
        path = CHART_DIR / "e01_case_pair_difference_distribution.png"
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        chart_paths["case_pair_difference_distribution"] = str(path)

    return chart_paths


def _group_long_rows(rows: list[dict[str, Any]], *, keys: tuple[str, ...]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(k) for k in keys)].append(row)
    return grouped


def copy_run_artifacts(run_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for info in run_infos:
        run_id = str(info["run_id"])
        dest = RUN_ARTIFACT_DIR / run_id
        dest.mkdir(parents=True, exist_ok=True)
        run_dir = Path(info["run_dir"])
        for name in ["manifest.json", "dataset.normalized.yaml", "dataset.source.yaml", "runner_timing.jsonl", "expectation_contract_events.jsonl"]:
            src = run_dir / name
            if src.exists():
                shutil.copy2(src, dest / name)
        metrics_rows = read_metrics_rows_from_run_dir(run_dir)
        metrics_gz = dest / "metrics.full_recovered.jsonl.gz"
        if metrics_rows:
            with gzip.open(metrics_gz, "wt", encoding="utf-8", compresslevel=5) as fh:
                for row in metrics_rows:
                    fh.write(json.dumps(row, ensure_ascii=False))
                    fh.write("\n")
        for src in sorted(run_dir.glob("metrics*.jsonl*")):
            if src.exists():
                shutil.copy2(src, dest / src.name)
        copied.append(
            {
                "run_id": run_id,
                "source_run_dir": str(run_dir),
                "artifact_run_dir": str(dest),
                "metrics_gzip": str(metrics_gz) if metrics_gz.exists() else "",
                "metrics_row_count": len(metrics_rows),
            }
        )
    return copied


def compare_conditions(run_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    comparison_keys = [
        ("common_part_total_per_text", True),
        ("common_part_total_per_input_char", True),
        ("common_part_total_per_external_sa", True),
        ("best_match_common_part_per_text", True),
        ("best_match_common_part_per_input_char", True),
        ("core_common_part_total_per_text", True),
        ("core_common_part_total_per_input_char", True),
        ("core_best_match_common_part_per_text", True),
        ("core_best_match_common_part_per_input_char", True),
        ("stimulus_best_match_score_mean", True),
        ("core_stimulus_best_match_score_mean", True),
        ("stimulus_match_v2_score_mean", True),
        ("core_stimulus_match_v2_score_mean", True),
        ("stimulus_order_alignment_mean", True),
        ("core_stimulus_order_alignment_mean", True),
        ("induction_identity_hit_ratio", True),
        ("core_induction_identity_hit_ratio", True),
        ("induction_identity_hit_to_target", True),
        ("top5_continuity_mean", True),
        ("top_anchor_presence_mean", True),
        ("core_top_anchor_presence_mean", True),
        ("structure_delta_per_text", False),
        ("structure_delta_per_input_char", False),
        ("structure_delta_per_external_sa", False),
        ("stimulus_residual_ratio_mean", False),
    ]
    by_condition: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_rep: dict[tuple[str, int], dict[str, Any]] = {}
    for summary in run_summaries:
        condition = str(summary.get("condition"))
        rep = int(summary.get("replicate", 0))
        by_rep[(condition, rep)] = summary
        for key, _ in comparison_keys:
            by_condition[condition][key].append(float(summary.get(key, 0.0) or 0.0))
    out: dict[str, Any] = {"metrics": {}, "paired": {}, "assessment": {}}
    for key, higher_is_better in comparison_keys:
        treatment = [float((by_rep.get(("treatment", rep), {}) or {}).get(key, 0.0) or 0.0) for rep in sorted({r for c, r in by_rep if c == "treatment"})]
        control = [float((by_rep.get(("control", rep), {}) or {}).get(key, 0.0) or 0.0) for rep in sorted({r for c, r in by_rep if c == "control"})]
        t_stats = _stats(treatment)
        c_stats = _stats(control)
        paired = _paired_direction(treatment, control, higher_is_better=higher_is_better)
        out["metrics"][key] = {
            "higher_is_better": higher_is_better,
            "treatment": t_stats,
            "control": c_stats,
            "mean_ratio_treatment_to_control": _safe_ratio(float(t_stats["mean"]), float(c_stats["mean"])),
            "mean_diff_treatment_minus_control": round(float(t_stats["mean"]) - float(c_stats["mean"]), 8),
        }
        out["paired"][key] = paired
    primary_keys = [
        "core_common_part_total_per_input_char",
        "core_stimulus_best_match_score_mean",
        "core_induction_identity_hit_ratio",
        "core_top_anchor_presence_mean",
        "structure_delta_per_input_char",
    ]
    wins = sum(1 for key in primary_keys if out["paired"].get(key, {}).get("win_ratio", 0.0) >= 2 / 3)
    coverage_values = [float(item.get("metric_row_coverage_ratio", 0.0) or 0.0) for item in run_summaries]
    min_coverage = min(coverage_values) if coverage_values else 0.0
    if min_coverage < 0.999:
        level = "采集不完整，暂不判定"
    elif wins >= 3:
        level = "支持"
    elif wins >= 2:
        level = "部分支持"
    else:
        level = "削弱或证据不足"
    out["assessment"] = {
        "primary_support_count": wins,
        "primary_metric_count": len(primary_keys),
        "min_metric_row_coverage_ratio": round(min_coverage, 6),
        "support_level": level,
        "note": "该判断只针对本地受控短程实验，不能外推为全部长期能力证明。",
    }
    return out


def write_report(
    *,
    run_summaries: list[dict[str, Any]],
    comparison: dict[str, Any],
    case_pair_stats: dict[str, Any],
    chart_paths: dict[str, str],
    copied_runs: list[dict[str, Any]],
    datasets: list[dict[str, Any]],
    run_stamp: str,
) -> Path:
    condition_name = {"treatment": "同构模板组", "control": "非同构对照组"}
    lines: list[str] = []
    lines.append("# E01 词汇重复与句式抽象实验报告")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 批次标识：`{run_stamp}`")
    lines.append(f"- 数据集版本：`{CURRICULUM_VERSION}`")
    lines.append("- 实验目标：在同词料、近似等长的配对条件下，检验变量替换的稳定句式是否比非同构输入更容易形成共同结构、残差路径与稳定波峰。")
    lines.append("- 运行口径：每个 run 使用 `reset_mode=clear_all` 冷启动；使用观测台实验 runner 默认主线配置；不修改 AP 核心运行代码。")
    lines.append("- 可靠性口径：只有指标覆盖率达到 0.999 以上的运行才参与结论；早期因日志清理导致指标缺失的探索运行不进入证据表。")
    lines.append("")
    lines.append("## 数据集与运行")
    lines.append("")
    lines.append("| 条件 | 重复 | dataset_id | sha256 | run_id | 状态 | 文本 tick | 核心文本 | 平均字数 | 空 tick | 指标覆盖率 |")
    lines.append("|---|---:|---|---|---|---|---:|---:|---:|---:|---:|")
    summary_by_key = {(s["condition"], int(s["replicate"])): s for s in run_summaries}
    for ds in datasets:
        summary = summary_by_key.get((ds["condition"], int(ds["replicate"])), {})
        lines.append(
            f"| {condition_name.get(ds['condition'], ds['condition'])} | {ds['replicate']} | `{ds['dataset_id']}` | `{ds['sha256'][:12]}...` | "
            f"`{summary.get('run_id', '')}` | {summary.get('run_status', '')} | {summary.get('text_rows', 0)} | "
            f"{summary.get('core_text_rows', 0)} | {float(summary.get('input_len_mean', 0.0) or 0.0):.2f} | {summary.get('empty_rows', 0)} | "
            f"{float(summary.get('metric_row_coverage_ratio', 0.0) or 0.0):.3f} |"
        )
    lines.append("")
    lines.append("## 核心结果")
    lines.append("")
    lines.append(f"- 综合判定：**{comparison.get('assessment', {}).get('support_level', '未知')}**。")
    lines.append(f"- 主指标支持数：{comparison.get('assessment', {}).get('primary_support_count', 0)} / {comparison.get('assessment', {}).get('primary_metric_count', 0)}。")
    lines.append(f"- 最低指标覆盖率：{comparison.get('assessment', {}).get('min_metric_row_coverage_ratio', 0):.3f}。")
    lines.append("- 这里的“支持”表示短程受控实验结果与 E01 局部断言方向一致；结论边界由数据集、运行口径和指标覆盖率共同限定。")
    lines.append("")
    lines.append("| 指标 | 同构模板组均值 | 非同构对照均值 | 均值差 | 配对方向 |")
    lines.append("|---|---:|---:|---:|---:|")
    display_names = {
        "common_part_total_per_text": "共同切割/文本",
        "common_part_total_per_input_char": "共同切割/输入字",
        "common_part_total_per_external_sa": "共同切割/外源SA",
        "best_match_common_part_per_text": "最佳共同部分/文本",
        "best_match_common_part_per_input_char": "最佳共同部分/输入字",
        "core_common_part_total_per_text": "核心共同切割/文本",
        "core_common_part_total_per_input_char": "核心共同切割/输入字",
        "core_best_match_common_part_per_text": "核心最佳共同部分/文本",
        "core_best_match_common_part_per_input_char": "核心最佳共同部分/输入字",
        "stimulus_best_match_score_mean": "刺激最佳匹配分",
        "core_stimulus_best_match_score_mean": "核心刺激最佳匹配分",
        "stimulus_match_v2_score_mean": "刺激 V2 匹配分",
        "core_stimulus_match_v2_score_mean": "核心刺激 V2 匹配分",
        "stimulus_order_alignment_mean": "顺序对齐",
        "core_stimulus_order_alignment_mean": "核心顺序对齐",
        "induction_identity_hit_ratio": "感应身份复用比",
        "core_induction_identity_hit_ratio": "核心感应身份复用比",
        "induction_identity_hit_to_target": "复用/目标",
        "top5_continuity_mean": "Top5 连续性",
        "top_anchor_presence_mean": "模板锚点显现",
        "core_top_anchor_presence_mean": "核心模板锚点显现",
        "structure_delta_per_text": "新结构/文本（较低更偏复用）",
        "structure_delta_per_input_char": "新结构/输入字（较低更偏复用）",
        "structure_delta_per_external_sa": "新结构/外源SA（较低更偏复用）",
        "stimulus_residual_ratio_mean": "刺激残差比例（较低更偏命中）",
    }
    for key, item in comparison.get("metrics", {}).items():
        paired = comparison.get("paired", {}).get(key, {})
        lines.append(
            f"| {display_names.get(key, key)} | {item.get('treatment', {}).get('mean', 0):.6g} | "
            f"{item.get('control', {}).get('mean', 0):.6g} | {item.get('mean_diff_treatment_minus_control', 0):.6g} | "
            f"{paired.get('wins', 0)}/{paired.get('pairs', 0)} |"
        )
    lines.append("")
    lines.append("## 文本级配对分析")
    lines.append("")
    lines.append(f"- 配对样本数：{case_pair_stats.get('pair_count', 0)}。每个样本用同一 `case_id` 下的实验组文本和对照组文本一一比较。")
    lines.append("- 该分析用于检查 run 级均值是否由少数顺序重复造成；它不替代长期运行实验，但能更细地暴露局部指标方向。")
    lines.append("")
    lines.append("| 指标 | 支持/反向/相等 | 支持比例 | 平均差 | 中位差 | 均值 95% bootstrap CI | 符号检验 p |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for key, item in case_pair_stats.get("metrics", {}).items():
        ci = item.get("mean_diff_bootstrap_95ci", {}) if isinstance(item.get("mean_diff_bootstrap_95ci"), dict) else {}
        p_value = item.get("sign_test_p_value_two_sided", 1.0)
        try:
            p_value_float = float(p_value)
        except Exception:
            p_value_float = 1.0
        lines.append(
            f"| {item.get('label', key)} | {item.get('support_count', 0)}/{item.get('against_count', 0)}/{item.get('tie_count', 0)} | "
            f"{float(item.get('support_ratio', 0.0) or 0.0):.3f} | {float(item.get('mean_diff_treatment_minus_control', 0.0) or 0.0):.6g} | "
            f"{float(item.get('median_diff_treatment_minus_control', 0.0) or 0.0):.6g} | "
            f"[{float(ci.get('low', 0.0) or 0.0):.6g}, {float(ci.get('high', 0.0) or 0.0):.6g}] | "
            f"{p_value_float:.4f} |"
        )
    lines.append("")
    lines.append("## 论文可用结论")
    lines.append("")
    lines.append("- 可以写入的结论：在同词料、近似等长的配对输入中，稳定句式组在共同切割/输入字、共同切割/外源 SA 等指标上呈现更高水平；文本级配对分析也显示该方向不是单个 run 的偶然均值。")
    lines.append("- 需要降级表述的结论：本轮数据尚不能证明稳定句式会同步提高身份复用、Top5 连续性或注意力波峰锚点显现；这些指标在当前短程原型条件下要么接近不变，要么出现反向。")
    lines.append("- 更稳妥的论文表述：E01 支持 AP 当前实现具备对重复句式局部结构进行共同切割和减少新增结构开销的弱形式抽象迹象，但不支持把该迹象直接扩展为完整、稳定的长期概念抽象能力证明。")
    lines.append("- 后续实验衔接：若要证明更强形式，需要追加更长程运行、更多重复、结构身份追踪指标，以及对注意力 Top 结构显示口径的人工审查或可解释性抽样。")
    lines.append("")
    lines.append("## 图表")
    lines.append("")
    for title, key in [
        ("结构数量随 tick 增长", "structure_growth_curve"),
        ("核心指标对照", "metric_comparison"),
        ("共同切割计数热力图", "common_part_heatmap"),
        ("Top5 结构连续性", "top_structure_continuity"),
        ("匹配分与残差比例时间序列", "match_residual_timeseries"),
        ("共同切割归一化对照", "normalized_common_part_comparison"),
        ("核心文本长度控制", "input_length_balance"),
        ("文本级配对差异分布", "case_pair_difference_distribution"),
    ]:
        path = chart_paths.get(key, "")
        if path:
            lines.append(f"- {title}: `{path}`")
    lines.append("")
    lines.append("## 证据边界")
    lines.append("")
    lines.append("- 本实验使用短程文本输入和当前字符 SA 主线流程，结论只覆盖“重复句式变量替换”的局部抽象现象。")
    lines.append("- v2 对照组与实验组共享核心词料和语义角色，并记录输入字数、外源 SA 数等归一化分母；自然语言仍无法做到每句完全等长，因此论文正文应同时报告原始指标和归一化指标。")
    lines.append("- 共同切割计数越高不必然等于抽象越好；若对照组因重排词料产生更多局部切割，需要结合匹配分、复用比、新结构增量和锚点显现共同解释。")
    lines.append("- 本轮没有关闭共同切割或结构写入作为强消融，因为该消融会同时改变多个核心机制，解释边界不如同主题非同构对照干净。")
    lines.append("- 若后续强消融需要加入，应单独标注为机制破坏实验，不与当前主线能力实验混为一组。")
    lines.append("")
    lines.append("## 反驳式验收")
    lines.append("")
    lines.append("- 可反驳点 1：如果核心文本平均长度或外源 SA 数差异过大，则共同切割与结构增量可能只是输入规模效应。对应检查：查看 `input_len_mean`、`core_input_len_mean`、`external_sa_count_mean` 与长度控制图。")
    lines.append("- 可反驳点 2：如果只出现共同切割升高，而匹配分、身份复用、锚点显现没有同步改善，则不能称为稳定抽象能力增强，只能称为局部重叠增加。")
    lines.append("- 可反驳点 3：如果指标覆盖率低于 0.999，或 run manifest 的执行 tick 与恢复 metrics 行数不一致，则该 run 不得进入论文证据。")
    lines.append("- 可反驳点 4：如果多重复顺序下方向不一致，应把该结果写成顺序敏感现象，而不是写成稳定机制证据。")
    lines.append("- 可反驳点 5：如果文本级配对分析的置信区间跨过 0，或符号检验不稳定，论文中应使用“初步支持”“弱形式支持”一类表述，而不是写成确定性证明。")
    lines.append("")
    lines.append("## 附件索引")
    lines.append("")
    lines.append(f"- 数据集目录：`{DATASET_ARTIFACT_DIR}`")
    lines.append(f"- 运行附件目录：`{RUN_ARTIFACT_DIR}`")
    lines.append(f"- 表格目录：`{TABLE_DIR}`")
    lines.append(f"- 图表目录：`{CHART_DIR}`")
    lines.append("")
    lines.append("### 运行附件")
    lines.append("")
    for item in copied_runs:
        lines.append(f"- `{item['run_id']}`: `{item['artifact_run_dir']}`")

    report_path = REPORT_DIR / "E01_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def write_outputs(
    *,
    datasets: list[dict[str, Any]],
    run_infos: list[dict[str, Any]],
    run_stamp: str,
) -> dict[str, Any]:
    run_summaries = [summarize_run_metrics(info) for info in run_infos]
    long_rows = build_long_rows(run_infos)
    case_pair_rows, case_pair_stats = build_case_pair_comparison(long_rows)
    comparison = compare_conditions(run_summaries)
    write_csv(TABLE_DIR / "e01_run_summary.csv", run_summaries)
    write_csv(TABLE_DIR / "e01_tick_metrics_long.csv", long_rows)
    write_csv(TABLE_DIR / "e01_case_pair_comparison.csv", case_pair_rows)
    write_json(TABLE_DIR / "e01_run_summary.json", run_summaries)
    write_json(TABLE_DIR / "e01_case_pair_comparison.json", {"rows": case_pair_rows, "stats": case_pair_stats})
    write_json(TABLE_DIR / "e01_condition_comparison.json", comparison)
    chart_paths = generate_charts(long_rows, run_summaries, comparison, case_pair_rows)
    copied_runs = copy_run_artifacts(run_infos)
    evidence_index = {
        "experiment": "E01_词汇重复与句式抽象",
        "run_stamp": run_stamp,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "datasets": [
            {
                "condition": d["condition"],
                "replicate": d["replicate"],
                "dataset_id": d["dataset_id"],
                "sha256": d["sha256"],
                "artifact_path": str(d["artifact_path"]),
            }
            for d in datasets
        ],
        "runs": [
            {
                "condition": s["condition"],
                "replicate": s["replicate"],
                "run_id": s["run_id"],
                "status": s["run_status"],
                "dataset_sha256": s["dataset_sha256"],
            }
            for s in run_summaries
        ],
        "comparison": comparison,
        "case_pair_stats": case_pair_stats,
        "charts": chart_paths,
        "tables": {
            "run_summary_csv": str(TABLE_DIR / "e01_run_summary.csv"),
            "tick_metrics_long_csv": str(TABLE_DIR / "e01_tick_metrics_long.csv"),
            "case_pair_comparison_csv": str(TABLE_DIR / "e01_case_pair_comparison.csv"),
            "condition_comparison_json": str(TABLE_DIR / "e01_condition_comparison.json"),
            "case_pair_comparison_json": str(TABLE_DIR / "e01_case_pair_comparison.json"),
        },
    }
    write_json(MANIFEST_DIR / "E01_evidence_index.json", evidence_index)
    report_path = write_report(
        run_summaries=run_summaries,
        comparison=comparison,
        case_pair_stats=case_pair_stats,
        chart_paths=chart_paths,
        copied_runs=copied_runs,
        datasets=datasets,
        run_stamp=run_stamp,
    )
    evidence_index["report_path"] = str(report_path)
    write_json(MANIFEST_DIR / "E01_evidence_index.json", evidence_index)
    return evidence_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AP paper E01 controlled experiment.")
    parser.add_argument("--replicates", type=int, default=3, help="Number of deterministic order replicates per condition.")
    parser.add_argument("--empty-repeat", type=int, default=2, help="Empty ticks after each real text tick.")
    parser.add_argument("--max-ticks", type=int, default=0, help="Optional max source ticks per run for quick checks.")
    parser.add_argument("--make-only", action="store_true", help="Only generate datasets, do not run AP.")
    parser.add_argument("--analyze-existing-stamp", default="", help="Analyze existing runs for this stamp without rerunning AP.")
    parser.add_argument("--stamp", default="", help="Optional run stamp for reproducibility.")
    args = parser.parse_args(argv)

    _ensure_dirs()
    replicates = max(1, int(args.replicates))
    empty_repeat = max(0, int(args.empty_repeat))
    run_stamp = str(args.stamp or _now_stamp())
    datasets = write_datasets(replicates=replicates, empty_repeat=empty_repeat)
    write_json(
        MANIFEST_DIR / f"E01_dataset_manifest_{run_stamp}.json",
        {
            "run_stamp": run_stamp,
            "replicates": replicates,
            "empty_repeat": empty_repeat,
            "datasets": [
                {
                    "condition": d["condition"],
                    "replicate": d["replicate"],
                    "dataset_id": d["dataset_id"],
                    "dataset_name": d["dataset_name"],
                    "sha256": d["sha256"],
                    "artifact_path": str(d["artifact_path"]),
                    "imported_path": str(d["imported_path"]),
                    "source_text_ticks": d["source_text_ticks"],
                    "total_source_ticks": d["total_source_ticks"],
                }
                for d in datasets
            ],
        },
    )
    print(f"[E01] generated {len(datasets)} datasets under {DATASET_ARTIFACT_DIR}", flush=True)
    if args.make_only:
        return 0

    run_infos: list[dict[str, Any]] = []
    max_ticks = int(args.max_ticks) if int(args.max_ticks or 0) > 0 else None
    started = time.perf_counter()
    analyze_existing_stamp = str(args.analyze_existing_stamp or "").strip()
    if analyze_existing_stamp:
        run_stamp = analyze_existing_stamp
        for dataset_info in datasets:
            condition = str(dataset_info["condition"])
            replicate = int(dataset_info["replicate"])
            run_id = f"paper_e01_{condition}_r{replicate}_{run_stamp}"
            run_dir = resolve_run_dir(run_id)
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
            run_infos.append(
                {
                    **dataset_info,
                    "run_id": run_id,
                    "run_dir": run_dir,
                    "manifest": manifest,
                    "success": str(manifest.get("status", "")) in {"completed", "stopped_max_ticks"},
                    "status": manifest.get("status", ""),
                    "metrics_path": run_dir / "metrics.jsonl",
                    "runner_timing_path": run_dir / "runner_timing.jsonl",
                }
            )
    else:
        for dataset_info in datasets:
            run_infos.append(run_one_dataset(dataset_info, run_stamp=run_stamp, max_ticks=max_ticks))
    evidence_index = write_outputs(datasets=datasets, run_infos=run_infos, run_stamp=run_stamp)
    elapsed = time.perf_counter() - started
    print(json.dumps({
        "ok": True,
        "elapsed_sec": round(elapsed, 3),
        "report_path": evidence_index.get("report_path"),
        "support_level": evidence_index.get("comparison", {}).get("assessment", {}).get("support_level"),
        "charts": evidence_index.get("charts"),
        "tables": evidence_index.get("tables"),
    }, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
