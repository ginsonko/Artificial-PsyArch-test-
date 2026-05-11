# E17 内部候选链实验报告 e17_final_v1

## 结论摘要

- 支持等级：strong_evidence
- family 数：12
- case 数：72
- step 数：192
- 整体通过比例：1.000
- 符号检验 p 值：0.00048828
- 六分支通过比例：1.000 / 1.000 / 1.000 / 1.000 / 1.000 / 1.000

## 正文可使用的最小命题

在当前 AP 原型中，结构目标可以作为跨 tick 的内部候选链节点被承接：当上一拍 top 结构进入下一拍 source 后，感应赋能会沿已学习结构链逐拍推进；错误种子、低预算、无承接和终端记忆均能形成可复查的边界。这支持“内部续写链/叙事候选链”的工程基础，但不等同于完整自然语言生成能力已经完成。

## family 判据

| family | 连续承接 | 错误种子静默 | 低预算静默 | 无承接停滞 | 权重转向 | 终端停止 | all_ok |
|---|---:|---:|---:|---:|---:|---:|---:|
| F01 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F02 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F03 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F04 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F05 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F06 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F07 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F08 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F09 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F10 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F11 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F12 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

## 白箱样例

- chain_follow: `{"family": "F01", "branch": "chain_follow", "branch_label": "连续承接", "case_counted_steps": 3, "source_ev": 1.0, "low_budget_ev": 0.012, "expected_sequence": "AB>ABC>memory:terminal", "top_sequence": "AB>ABC>memory:terminal", "expected_hit_ratio": 1.0, "chain_order_ok": 1, "target_chain_ok": 1, "next_seed_from_previous_top_count": 2, "next_seed_from_previous_top_ratio": 1.0, "wrong_target_quiet": 0, "low_budget_quiet": 0, "no_carry_stalled": 0, "branch_switched": 0, "terminal_stopped": 1, "terminal_followup_target_count": 0, "terminal_step_index": 3, "carried_source_ids": "A>AB>ABC"}`
- no_carry_control: `{"family": "F01", "branch": "no_carry_control", "branch_label": "无承接对照", "case_counted_steps": 3, "source_ev": 1.0, "low_budget_ev": 0.012, "expected_sequence": "AB>AB>AB", "top_sequence": "AB>AB>AB", "expected_hit_ratio": 1.0, "chain_order_ok": 1, "target_chain_ok": 0, "next_seed_from_previous_top_count": 0, "next_seed_from_previous_top_ratio": 0.0, "wrong_target_quiet": 0, "low_budget_quiet": 0, "no_carry_stalled": 1, "branch_switched": 0, "terminal_stopped": 0, "terminal_followup_target_count": 0, "terminal_step_index": -1, "carried_source_ids": "A>A>A"}`
- branch_switch: `{"family": "F01", "branch": "branch_switch", "branch_label": "权重转向", "case_counted_steps": 3, "source_ev": 1.0, "low_budget_ev": 0.012, "expected_sequence": "AB>ABY>memory:switch", "top_sequence": "AB>ABY>memory:switch", "expected_hit_ratio": 1.0, "chain_order_ok": 1, "target_chain_ok": 1, "next_seed_from_previous_top_count": 2, "next_seed_from_previous_top_ratio": 1.0, "wrong_target_quiet": 0, "low_budget_quiet": 0, "no_carry_stalled": 0, "branch_switched": 1, "terminal_stopped": 1, "terminal_followup_target_count": 0, "terminal_step_index": 3, "carried_source_ids": "A>AB>ABY"}`
- terminal_stop: `{"family": "F01", "branch": "terminal_stop", "branch_label": "终端停止", "case_counted_steps": 3, "source_ev": 1.0, "low_budget_ev": 0.012, "expected_sequence": "AB>ABC>memory:terminal", "top_sequence": "AB>ABC>memory:terminal", "expected_hit_ratio": 1.0, "chain_order_ok": 1, "target_chain_ok": 1, "next_seed_from_previous_top_count": 2, "next_seed_from_previous_top_ratio": 1.0, "wrong_target_quiet": 0, "low_budget_quiet": 0, "no_carry_stalled": 0, "branch_switched": 0, "terminal_stopped": 1, "terminal_followup_target_count": 0, "terminal_step_index": 3, "carried_source_ids": "A>AB>ABC"}`

## 图表

- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E17_internal_narrative_chain\charts\e17_branch_pass_rates_e17_final_v1.png
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E17_internal_narrative_chain\charts\e17_chain_step_delta_ev_e17_final_v1.png
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E17_internal_narrative_chain\charts\e17_family_pass_matrix_e17_final_v1.png
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E17_internal_narrative_chain\charts\e17_sample_path_contrast_e17_final_v1.png

