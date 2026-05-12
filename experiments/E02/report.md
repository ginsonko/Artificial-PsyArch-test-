# E02 稳定句壳下标签替换导致结构生长实验报告（e02_label_switch_holdout_confirm_v1）

## 实验目的

验证当句壳保持不变、只替换局部标签时，AP 是否会保留共同结构并为差异部分产生可测的结构增量。

## 逻辑预期与强证据判据

repeat 分支第二次输入完全重复，switch 分支第二次输入只替换标签。若设计控制全部通过，并且 switch 分支在感应生长身份、HDB 结构数、残差差异项和带记忆引用差异项上稳定高于 repeat 分支，说明局部差异被写成可追溯结构生长。

## 数据集与变量控制

终稿使用 16 个未参与开发扫描的长句壳设计，每个设计 3 次重复，共 48 个 pair。每个 pair 都记录句壳、标签长度、变更字符数和非标签差异数，确保关键变量只落在标签替换上。

本目录保留最小数据集文件：
- `datasets/paper_e02_switch_H01_repeat_A_r1_v2.yaml`
- `datasets/paper_e02_switch_H01_repeat_A_r2_v2.yaml`
- `datasets/paper_e02_switch_H01_repeat_A_r3_v2.yaml`
- `datasets/paper_e02_switch_H01_repeat_B_r1_v2.yaml`
- `datasets/paper_e02_switch_H01_repeat_B_r2_v2.yaml`
- `datasets/paper_e02_switch_H01_repeat_B_r3_v2.yaml`
- `datasets/paper_e02_switch_H01_switch_A_r1_v2.yaml`
- `datasets/paper_e02_switch_H01_switch_A_r2_v2.yaml`
- `datasets/paper_e02_switch_H01_switch_A_r3_v2.yaml`
- `datasets/paper_e02_switch_H01_switch_B_r1_v2.yaml`
- `datasets/paper_e02_switch_H01_switch_B_r2_v2.yaml`
- `datasets/paper_e02_switch_H01_switch_B_r3_v2.yaml`
- 其余 84 个数据集文件见 `datasets/` 目录。

## 结果与解释

- 支持等级：`strong_evidence`
- pair 数：48
- 唯一句壳设计数：16
- 平均重复次数：3
- 设计控制通过率：1
- 严格生长通过率：1
- 严格模式通过率：1
- HDB 结构数均值差：4
- 残差差异项均值差：2
- 带记忆引用差异项均值差：1

例如 H01 中，首句均为同一代号句，第二句只在“辰栈/陌钥”之间替换；明细表显示非标签差异数为 0，结构数差为 4，残差差异项差为 2。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e02_label_switch_growth_core_final.png`
- `charts/e02_label_switch_growth_extended_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e02_label_switch_pair_rows_final.csv`
  - `tables/source_tables/e02_label_switch_row_metrics_final.csv`
  - `tables/source_tables/e02_label_switch_summary_final.json`
- 清单与哈希：
  - `manifests/E02_label_switch_dataset_manifest_final.json`
  - `manifests/E02_label_switch_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
