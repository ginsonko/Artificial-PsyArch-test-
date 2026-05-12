# E17 内部候选链的跨拍承接与续写实验报告（e17_final_v1）

## 实验目的

验证 AP 的内部候选对象能否跨认知滴答承接，形成可观察的短链续写雏形。

## 逻辑预期与强证据判据

连续承接分支应按 AB -> ABC -> terminal memory 顺序推进；错误种子、低预算和无承接对照应阻断；分支切换应按权重转向；终端记忆之后不应继续展开。

## 数据集与变量控制

实验使用结构图而不是自由文本生成。每个 family 记录 case 级分支结果和 step 级 top candidate，使读者可以逐拍复核候选从哪里来、为什么换向、在哪里停住。

## 结果与解释

- 支持等级：`strong_evidence`
- case 数：72
- step 数：192
- family 数：12
- 连续承接通过率：1
- 错误种子对照通过率：1
- 低预算对照通过率：1
- 无承接对照通过率：1
- 分支切换通过率：1
- 终端停止通过率：1
- 承接比例均值：1

连续承接的 chain_carry_ratio_mean 为 1.0，无承接对照为 0；terminal_followup_target_count_mean 为 0，说明终端记忆之后没有继续扩散。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e17_branch_pass_rates_final.png`
- `charts/e17_chain_step_delta_ev_final.png`
- `charts/e17_family_pass_matrix_final.png`
- `charts/e17_sample_path_contrast_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e17_internal_narrative_chain_case_rows_final.csv`
  - `tables/source_tables/e17_internal_narrative_chain_family_rows_final.csv`
  - `tables/source_tables/e17_internal_narrative_chain_step_rows_final.csv`
  - `tables/source_tables/e17_internal_narrative_chain_summary_final.json`
  - `tables/source_tables/e17_internal_narrative_chain_whitebox_final.json`
- 清单与哈希：
  - `manifests/E17_internal_narrative_chain_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
