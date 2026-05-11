# E11 有限分形能量扩散报告（e11_final_v1）

## 核心结论

- 支持等级：**strong_evidence**
- family 数：12
- case 数：72
- 整体通过比例：1.000
- 符号检验 p 值：0.00048828
- 多轮扩散 / 单轮截断 / 前沿阈值 / 预算阈值 / 宽度上限 / 无 ER 重诱发通过比例：1.000 / 1.000 / 1.000 / 1.000 / 1.000 / 1.000

## 正文可使用的最小命题

在当前 AP 原型中，分层能量图可以从一个被激活的源结构出发，沿结构局部数据库向结构目标与记忆目标分配虚能量；结构目标可以作为下一轮前沿继续展开，记忆目标作为终止叶节点停止扩散。扩散深度和宽度不是无限增长，而会被最大轮数、前沿能量阈值、最小预算和前沿节点上限约束。

## 强证据边界

- 本实验不宣称 AP 已经产生完整的人类联想、想象或叙事意识。
- 本实验只证明当前原型中的分层能量图具备可控的多层展开、终止和剪枝边界。

## family 级通过情况

| family | 多轮 | 单轮 | 前沿阈值 | 预算阈值 | 宽度上限 | 无ER重诱发 | all_ok |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
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

- 多轮样例：family `F01`，depth_max=2，round_count=4，terminal_memory_count=11，root_reinduction_count=3。
- 前沿阈值样例：depth_max=1，frontier_pruned_count=6。
- 宽度上限样例：frontier_out_count_max=1，frontier_pruned_count=6。

## 多轮样例 round 摘要

| round | frontier_in | frontier_out | pruned | memory_terminal | root_reinduction | frontier_budget | root_budget | delta_ev |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 2 | 0 | 2 | 0 | 1.000000 | 0.300000 | 1.300000 |
| 2 | 2 | 4 | 0 | 3 | 1 | 1.040000 | 0.246000 | 1.286000 |
| 3 | 4 | 4 | 0 | 3 | 1 | 0.196800 | 0.201720 | 0.398520 |
| 4 | 4 | 4 | 1 | 3 | 1 | 0.161376 | 0.165410 | 0.326786 |

## 图表

- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E11_energy_graph\charts\e11_energy_graph_branch_controls_e11_final_v1.png
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E11_energy_graph\charts\e11_energy_graph_round_budget_e11_final_v1.png
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E11_energy_graph\charts\e11_energy_graph_target_depth_kind_e11_final_v1.png
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E11_energy_graph\charts\e11_energy_graph_family_pass_e11_final_v1.png

