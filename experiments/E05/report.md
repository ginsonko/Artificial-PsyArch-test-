# E05 行动执行后的可复用准备痕迹实验报告（e05_final_v1）

## 实验目的

验证一次真实执行过的行动是否会留下可复用的行动准备痕迹，而不是只在执行日志中短暂出现。

## 逻辑预期与强证据判据

显式训练分支应触发行动并形成可见执行来源；弱探针分支不直接给足行动条件，但若历史执行已沉淀，弱探针中的行动 drive 与 margin 应高于只见过弱文本的对照。

## 数据集与变量控制

实验把行动执行、运行态投影、弱探针再激活和对照静默拆成四个观察点，用来证明从行动到记忆再到行动准备的闭环。

本目录保留最小数据集文件：
- `datasets/paper_e05_F01_executed_history_r1_v1.yaml`
- `datasets/paper_e05_F01_weak_only_control_r1_v1.yaml`
- `datasets/paper_e05_F02_executed_history_r1_v1.yaml`
- `datasets/paper_e05_F02_weak_only_control_r1_v1.yaml`
- `datasets/paper_e05_F03_executed_history_r1_v1.yaml`
- `datasets/paper_e05_F03_weak_only_control_r1_v1.yaml`
- `datasets/paper_e05_F04_executed_history_r1_v1.yaml`
- `datasets/paper_e05_F04_weak_only_control_r1_v1.yaml`
- `datasets/paper_e05_F05_executed_history_r1_v1.yaml`
- `datasets/paper_e05_F05_weak_only_control_r1_v1.yaml`
- `datasets/paper_e05_F06_executed_history_r1_v1.yaml`
- `datasets/paper_e05_F06_weak_only_control_r1_v1.yaml`
- 其余 12 个数据集文件见 `datasets/` 目录。

## 结果与解释

- 支持等级：`strong_evidence`
- pair 数：12
- 显式训练触发率：1
- 弱对照静默率：1
- 执行来源可见率：1
- 运行态投影率：1
- 弱探针 drive 优势率：1
- 弱探针 drive 优势均值：0.1928

弱探针 drive 优势均值为 0.1928，且 probe_drive_advantage_ratio 为 1.0，说明行动痕迹在弱输入下仍可被重新调动。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e05_action_closure_chain_ratios_final.png`
- `charts/e05_action_closure_probe_drive_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e05_action_closure_pair_rows_final.csv`
  - `tables/source_tables/e05_action_closure_row_metrics_final.csv`
  - `tables/source_tables/e05_action_closure_summary_final.json`
- 清单与哈希：
  - `manifests/E05_action_closure_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
