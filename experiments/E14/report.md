# E14 奖惩状态对行动阈值与局部驱动力的调制实验报告（e14_final_v1）

## 实验目的

验证认知感受和情绪递质是否能改变行动阈值与局部驱动力，使行动准备随内部状态连续调制。

## 逻辑预期与强证据判据

奖励状态应降低全局行动阈值并提前执行，压力状态应提高阈值并推迟执行；局部奖励应提高目标 drive，局部惩罚应降低目标 drive；关闭局部调制时对应差异应消失。

## 数据集与变量控制

实验把全局阈值、NT 调制、固定阈值对照、局部奖惩和局部关闭分支分开记录，避免把单个参数变化误判为完整行动调制。

## 结果与解释

- 支持等级：`strong_evidence`
- case 数：144
- family 数：12
- family 全通过率：1
- 奖励阈值分支通过率：1
- 压力阈值分支通过率：1
- 局部奖励通过率：1
- 局部惩罚通过率：1
- 奖励阈值相对基线变化：-0.2753
- 压力阈值相对基线变化：0.3502
- 局部奖励 drive 变化：0.1176

奖励阈值相对基线下降 0.2753，压力阈值相对基线上升 0.3502；局部奖励 drive 上升 0.1176，局部惩罚 drive 下降 0.1540。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e14_drive_threshold_curves_final.png`
- `charts/e14_execution_timing_final.png`
- `charts/e14_family_pass_matrix_final.png`
- `charts/e14_local_drive_final.png`
- `charts/e14_threshold_modulation_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e14_action_threshold_modulation_case_rows_final.csv`
  - `tables/source_tables/e14_action_threshold_modulation_family_rows_final.csv`
  - `tables/source_tables/e14_action_threshold_modulation_summary_final.json`
  - `tables/source_tables/e14_action_threshold_modulation_tick_rows_final.csv`
  - `tables/source_tables/e14_action_threshold_modulation_whitebox_final.json`
- 清单与哈希：
  - `manifests/E14_action_threshold_modulation_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
