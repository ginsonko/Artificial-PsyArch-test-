# E07 复杂度状态调制下一拍注意力预算实验报告（e07_final_v1）

## 实验目的

验证上一拍复杂度状态是否会改变下一拍注意力容量和预算，而不是只作为静态日志存在。

## 逻辑预期与强证据判据

低复杂度、中复杂度和高复杂度分支应形成有序状态差异；下一拍探针中，低复杂度分支保留更大的 top_n， 高复杂度分支获得更高预算，且三分支均符合预设方向。

## 数据集与变量控制

实验先用 source case 产生低、中、高复杂度状态，再用 probe case 读取下一拍注意力参数。这样把状态生成和状态效应分离，降低循环解释风险。

## 结果与解释

- 支持等级：`strong_evidence`
- source case 数：60
- probe case 数：36
- probe pair 数：12
- 低复杂度分支通过率：1
- 中复杂度分支通过率：1
- 高复杂度分支通过率：1
- 低高 top_n 差：10
- 高低预算差：4

低复杂度 top_n 均值为 21，高复杂度 top_n 均值为 11；高低预算差为 4，说明容量收缩和预算提高同时出现。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e07_attention_complexity_probe_contrast_final.png`
- `charts/e07_attention_complexity_source_transition_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e07_attention_complexity_pair_rows_final.csv`
  - `tables/source_tables/e07_attention_complexity_probe_rows_final.csv`
  - `tables/source_tables/e07_attention_complexity_source_rows_final.csv`
  - `tables/source_tables/e07_attention_complexity_summary_final.json`
- 清单与哈希：
  - `manifests/E07_attention_complexity_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
