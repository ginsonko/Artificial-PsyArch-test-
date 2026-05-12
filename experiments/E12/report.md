# E12 结构过程态与记忆目标态实验报告（e12_final_v2）

## 实验目的

验证结构目标和情景记忆目标在 AP 中承担不同角色：结构表示仍可展开的过程态，记忆表示已经抵达的经历目标态。

## 逻辑预期与强证据判据

同一 memory_id 应聚合多个来源；纯结构过程不应自动写成记忆快照；不同 memory_id 不应合并；记忆维护 tick 后应按配置衰减。

## 数据集与变量控制

实验构造同源结构目标和记忆目标，并分别测试汇聚、纯结构过程、不同记忆边界和衰减。这样可以避免把所有历史命中都解释成同一种对象。

## 结果与解释

- 支持等级：`strong_evidence`
- case 数：48
- family 数：12
- 记忆汇聚通过率：1
- 结构过程通过率：1
- 不同记忆边界通过率：1
- 记忆衰减通过率：1
- 汇聚命中数均值：3
- 纯结构过程记忆快照均值：0
- 衰减比例均值：0.5

同记忆汇聚的 hit_count 均值为 3，source_count 均值为 4；纯结构过程的 memory_snapshot_count 为 0，不同记忆分支的 memory_count 为 2。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e12_memory_convergence_final.png`
- `charts/e12_memory_decay_final.png`
- `charts/e12_process_memory_family_pass_final.png`
- `charts/e12_process_memory_role_split_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e12_process_memory_case_rows_final.csv`
  - `tables/source_tables/e12_process_memory_pair_rows_final.csv`
  - `tables/source_tables/e12_process_memory_summary_final.json`
  - `tables/source_tables/e12_process_memory_target_rows_final.csv`
  - `tables/source_tables/e12_process_memory_whitebox_final.json`
- 清单与哈希：
  - `manifests/E12_process_memory_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
