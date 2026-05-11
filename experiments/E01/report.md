# E01 v4 最小强证据实验报告

- 生成时间：2026-05-11 17:32:33
- 批次标识：`smoke3_20260511_e01_v4_crossover_f2`
- 运行参数档：`context_strict_probe`
- 判定：`strong_evidence`
- 家族样本数：2

## 设计逻辑

本实验使用交叉 probe，而不是直接拿两条不同文本做比较。共享冷启动后，两组只在历史第二条输入不同：一组见过有序 B，另一组见过乱序 B。后续把同一条有序 B probe 同时喂给两组，因此任何差异都更容易解释为历史路径差异，而不是文本本身难度差异。

## 数据集与运行

| 条件 | 家族 | 重复 | dataset_id | sha256 | run_id | 状态 | 文本 tick |
|---|---|---:|---|---|---|---|---:|
| treatment | F01 | 1 | `paper_e01_crossover_treatment_F01_r1_context_strict_probe_v4` | `bcfed2736abf...` | `paper_e01_crossover_treatment_F01_r1_context_strict_probe_smoke3_20260511_e01_v4_crossover_f2` | completed | 4 |
| treatment | F02 | 1 | `paper_e01_crossover_treatment_F02_r1_context_strict_probe_v4` | `5eb922d4d228...` | `paper_e01_crossover_treatment_F02_r1_context_strict_probe_smoke3_20260511_e01_v4_crossover_f2` | completed | 4 |
| control | F01 | 1 | `paper_e01_crossover_control_F01_r1_context_strict_probe_v4` | `3072af36515c...` | `paper_e01_crossover_control_F01_r1_context_strict_probe_smoke3_20260511_e01_v4_crossover_f2` | completed | 4 |
| control | F02 | 1 | `paper_e01_crossover_control_F02_r1_context_strict_probe_v4` | `0f896e48b066...` | `paper_e01_crossover_control_F02_r1_context_strict_probe_smoke3_20260511_e01_v4_crossover_f2` | completed | 4 |
| calibration | F01 | 1 | `paper_e01_crossover_calibration_F01_r1_context_strict_probe_v4` | `8203e4247b7e...` | `paper_e01_crossover_calibration_F01_r1_context_strict_probe_smoke3_20260511_e01_v4_crossover_f2` | completed | 4 |
| calibration | F02 | 1 | `paper_e01_crossover_calibration_F02_r1_context_strict_probe_v4` | `82b933e950ac...` | `paper_e01_crossover_calibration_F02_r1_context_strict_probe_smoke3_20260511_e01_v4_crossover_f2` | completed | 4 |

## 阶段均值

| 条件 | 阶段 | n | 新增存储/字 | 匹配分 | 复用信号 | 新路径 | 语境支持 | 机制阳性率 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| calibration | cold_A | 2 | 5.1000 | 0.9311 | 3.0000 | 10.0000 | 0.0000 | 1.0000 |
| calibration | history_B | 2 | 6.2000 | 0.8833 | 1.0000 | 15.0000 | 0.0000 | 1.0000 |
| calibration | probe_ordered_B | 4 | 3.6500 | 0.9237 | 3.0000 | 10.5000 | 0.7578 | 0.5000 |
| control | cold_A | 2 | 5.1000 | 0.9311 | 3.0000 | 10.0000 | 0.0000 | 1.0000 |
| control | history_B | 2 | 6.2000 | 0.8833 | 1.0000 | 15.0000 | 0.0000 | 1.0000 |
| control | probe_ordered_B | 2 | 5.7000 | 0.9189 | 3.0000 | 16.0000 | 0.7562 | 1.0000 |
| control | probe_permuted_B | 2 | 3.9000 | 0.9159 | 15.0000 | 9.0000 | 0.7657 | 1.0000 |
| treatment | cold_A | 2 | 5.1000 | 0.9311 | 3.0000 | 10.0000 | 0.0000 | 1.0000 |
| treatment | history_B | 2 | 6.2000 | 0.8833 | 1.0000 | 15.0000 | 0.0000 | 1.0000 |
| treatment | probe_ordered_B | 2 | 3.4000 | 0.9313 | 0.0000 | 9.0000 | 0.7556 | 0.0000 |
| treatment | probe_permuted_B | 2 | 5.5000 | 0.9115 | 3.0000 | 13.0000 | 0.7544 | 1.0000 |

## 逐家族判定

| 重复 | 家族 | 冷启动差 | 有序 probe 优势 | 乱序 probe 优势 | treatment 历史偏好 | control 历史偏好 | 机制优势 | 通过项 |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | F01 | 0.0000 | 2.3000 | 1.6000 | 2.1000 | 1.8000 | 7.0000 | cold_equal,ordered_probe,history_specificity,mechanism |
| 1 | F02 | 0.0000 | 2.3000 | 1.6000 | 2.1000 | 1.8000 | 7.0000 | cold_equal,ordered_probe,history_specificity,mechanism |

## 汇总结论

- 冷启动可比通过率：1.0000。
- 有序 probe 优势通过率：1.0000；平均优势：2.3000。
- 乱序 probe 优势通过率：1.0000；平均优势：1.6000。
- 历史特异性通过率：1.0000；treatment 内历史偏好：2.1000；control 内历史偏好：1.8000。
- 机制通过率：1.0000；平均有序 probe 路径优势：7.0000；平均乱序 probe 路径优势：4.0000。

## 附件

- `docs\paper_artifacts_2026-05-11\E01_lexical_abstraction\strong_reuse_v4_crossover_probe\charts\e01_v4_crossover_phase_curves_smoke3_20260511_e01_v4_crossover_f2.png`
- `docs\paper_artifacts_2026-05-11\E01_lexical_abstraction\strong_reuse_v4_crossover_probe\charts\e01_v4_crossover_family_effects_smoke3_20260511_e01_v4_crossover_f2.png`
- `docs\paper_artifacts_2026-05-11\E01_lexical_abstraction\strong_reuse_v4_crossover_probe\tables\e01_v4_crossover_row_metrics_smoke3_20260511_e01_v4_crossover_f2.csv`
- `docs\paper_artifacts_2026-05-11\E01_lexical_abstraction\strong_reuse_v4_crossover_probe\tables\e01_v4_crossover_phase_summary_smoke3_20260511_e01_v4_crossover_f2.csv`
- `docs\paper_artifacts_2026-05-11\E01_lexical_abstraction\strong_reuse_v4_crossover_probe\tables\e01_v4_crossover_family_evidence_smoke3_20260511_e01_v4_crossover_f2.csv`
- `docs\paper_artifacts_2026-05-11\E01_lexical_abstraction\strong_reuse_v4_crossover_probe\reports\E01_v4_crossover_design_logic.md`
