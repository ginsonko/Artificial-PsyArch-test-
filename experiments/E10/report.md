# E10 重复、疲劳与恢复后的再出现实验报告（e10_final_v1）

## 实验目的

验证 AP 是否能区分同项重复、变体输入和恢复后再出现，并把重复调节投射到注意力与认知感受两层。

## 逻辑预期与强证据判据

首次出现不应被惩罚，同项重复应出现惩罚，变体应避免同项惩罚，恢复后再出现的惩罚应显著降低；疲劳类认知感受只在满足重复和低新鲜度条件时触发。

## 数据集与变量控制

实验分为注意力重复层和疲劳感受层。前者记录 priority 与 penalty，后者记录 boredom、repetition 和 NT 通道，避免把短期注意力抑制等同于完整疲劳感受。

## 结果与解释

- 支持等级：`strong_evidence`
- 注意力 case 数：60
- 疲劳 case 数：60
- family 数：12
- 首次零惩罚率：1
- 同项重复惩罚率：1
- 变体零惩罚率：1
- 恢复后仍可出现率：1
- 同项重复惩罚均值：0.25
- 疲劳分支通过率：1

同项重复惩罚均值为 0.25，变体惩罚为 0，恢复后惩罚降至 0.0117，说明系统保留重复痕迹但允许恢复。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e10_repeat_fatigue_attention_contrast_final.png`
- `charts/e10_repeat_fatigue_boredom_gating_final.png`
- `charts/e10_repeat_fatigue_family_pass_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e10_repeat_fatigue_attention_rows_final.csv`
  - `tables/source_tables/e10_repeat_fatigue_boredom_rows_final.csv`
  - `tables/source_tables/e10_repeat_fatigue_pair_rows_final.csv`
  - `tables/source_tables/e10_repeat_fatigue_summary_final.json`
  - `tables/source_tables/e10_repeat_fatigue_whitebox_final.json`
- 清单与哈希：
  - `manifests/E10_repeat_fatigue_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
