# E01 历史特异性局部结构复用实验报告（e01_v4_crossover_final）

## 实验目的

验证 AP 是否会把相同探针输入放回对应历史路径中处理，而不是只因为字符重复就无差别降低成本。

## 逻辑预期与强证据判据

在共享冷启动后，同一条有序探针输入应当在曾见过有序历史的 treatment 分支中更省新增存储；同字符乱序探针则应当在曾见过乱序历史的 control 分支中更省新增存储。若两组冷启动相等、两种探针优势方向互换、历史内偏好成立，并且机制链路也显示路径差异，才判为通过。

## 数据集与变量控制

数据集只改变第二条历史输入的顺序，其余冷启动、探针文本和运行基线保持一致。这样可以排除“文本本身更容易”这一解释，把差异收束到历史路径是否一致。

本目录保留最小数据集文件：
- `datasets/paper_e01_crossover_calibration_F01_r1_context_strict_probe_v4.yaml`
- `datasets/paper_e01_crossover_calibration_F02_r1_context_strict_probe_v4.yaml`
- `datasets/paper_e01_crossover_control_F01_r1_context_strict_probe_v4.yaml`
- `datasets/paper_e01_crossover_control_F02_r1_context_strict_probe_v4.yaml`
- `datasets/paper_e01_crossover_treatment_F01_r1_context_strict_probe_v4.yaml`
- `datasets/paper_e01_crossover_treatment_F02_r1_context_strict_probe_v4.yaml`

## 结果与解释

- 支持等级：`strong_evidence`
- 家族样本数：2
- 冷启动可比通过率：1
- 有序探针优势均值：2.3
- 乱序探针优势均值：1.6
- 历史特异性通过率：1
- 机制链路通过率：1

读者可在 family 明细表中看到 F01 与 F02 的冷启动差均为 0；有序探针优势为 2.3000，乱序探针优势为 1.6000，说明优势随历史方向反转。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e01_v4_crossover_family_effects_final.png`
- `charts/e01_v4_crossover_phase_curves_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e01_v4_crossover_evidence_summary_final.json`
  - `tables/source_tables/e01_v4_crossover_family_evidence_final.csv`
  - `tables/source_tables/e01_v4_crossover_phase_summary_final.csv`
  - `tables/source_tables/e01_v4_crossover_row_metrics_final.csv`
- 清单与哈希：
  - `manifests/E01_v4_crossover_dataset_manifest_final.json`
  - `manifests/E01_v4_crossover_evidence_final.json`
  - `manifests/E01_v4_crossover_latest.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
