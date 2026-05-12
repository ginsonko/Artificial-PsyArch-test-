# E11 有限分层能量图景与阈值剪枝实验报告（e11_final_v1）

## 实验目的

验证感应能量是否能从种子结构向外形成有限层级扩散，并受轮数、阈值、预算和宽度约束自然停住。

## 逻辑预期与强证据判据

多轮分支应形成 depth>=2 的展开并触达终止记忆；单轮分支应只到第一层；高阈值、高预算门槛和宽度上限应剪枝；关闭根源 ER 重诱发后，总 EV 应下降。

## 数据集与变量控制

实验使用同构结构图，而不是自然语言大样本。每个家族都有相同拓扑，六个分支只改变一个边界参数，从而直接观察能量扩散和剪枝边界。

## 结果与解释

- 支持等级：`strong_evidence`
- case 数：72
- family 数：12
- 多轮扩散通过率：1
- 单轮截断通过率：1
- 高前沿阈值通过率：1
- 高预算阈值通过率：1
- 宽度上限通过率：1
- 无 ER 重诱发通过率：1
- 深扩散深度均值：2

多轮分支深度均值为 2，终止记忆均值为 11；关闭 ER 重诱发后，总 EV 比多轮分支低 1.6847。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e11_energy_graph_branch_controls_final.png`
- `charts/e11_energy_graph_family_pass_final.png`
- `charts/e11_energy_graph_round_budget_final.png`
- `charts/e11_energy_graph_target_depth_kind_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e11_energy_graph_case_rows_final.csv`
  - `tables/source_tables/e11_energy_graph_pair_rows_final.csv`
  - `tables/source_tables/e11_energy_graph_round_rows_final.csv`
  - `tables/source_tables/e11_energy_graph_summary_final.json`
  - `tables/source_tables/e11_energy_graph_target_rows_final.csv`
  - `tables/source_tables/e11_energy_graph_whitebox_final.json`
- 清单与哈希：
  - `manifests/E11_energy_graph_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
