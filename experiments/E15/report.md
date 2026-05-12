# E15 自适应调参器的方向稳定性实验报告（e15_final_v1）

## 实验目的

验证自适应调参器是否能根据短窗口运行状态给出方向稳定的参数调整，而不是随机扰动参数。

## 逻辑预期与强证据判据

健康场景应静默；内源恢复、注意力过热、EV 传播不足、EV 诱发不足、EV 保留不足和输入饱和等压力场景应触发对应参数方向；禁用调参时应静默。

## 数据集与变量控制

实验不追求一个固定最优参数，而是检查“状态诊断 -> 参数方向 -> 更新记录”是否一致。每个压力类型都对应独立规则和预期方向。

## 结果与解释

- 支持等级：`strong_evidence`
- case 数：96
- family 数：12
- family 全通过率：1
- case 全通过率：1
- 健康静默通过率：1
- 内源恢复通过率：1
- 注意力过热通过率：1
- EV 传播通过率：1
- 禁用静默通过率：1
- 过热 CAM 预算调整均值：-2

注意力过热时 CAM 预算调整均值为 -2；EV 传播不足时传播比例调整为 0.05；健康静默和禁用静默通过率均为 1.0。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e15_branch_param_heatmap_final.png`
- `charts/e15_branch_pass_rates_final.png`
- `charts/e15_family_pass_matrix_final.png`
- `charts/e15_param_delta_directions_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e15_auto_tuner_stability_case_rows_final.csv`
  - `tables/source_tables/e15_auto_tuner_stability_family_rows_final.csv`
  - `tables/source_tables/e15_auto_tuner_stability_summary_final.json`
  - `tables/source_tables/e15_auto_tuner_stability_tick_rows_final.csv`
  - `tables/source_tables/e15_auto_tuner_stability_whitebox_final.json`
- 清单与哈希：
  - `manifests/E15_auto_tuner_stability_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
