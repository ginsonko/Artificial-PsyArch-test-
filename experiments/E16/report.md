# E16 多来源属性化接地入口与锚点隔离实验报告（e16_final_v1）

## 实验目的

验证来自不同来源的属性刺激能否作为可审计对象进入状态池，并与对应锚点绑定、与错误锚点隔离。

## 逻辑预期与强证据判据

多来源属性包应保持模态和来源字段；错误锚点、折叠属性和非法角色对照应被识别；运行态工具绑定应只落在正确目标上。

## 数据集与变量控制

实验把 packet 层和 runtime 层分开。packet 层检查属性对象是否被正确构造，runtime 层检查对象进入状态池后是否仍保留锚点、模态和来源。

## 结果与解释

- 支持等级：`strong_evidence`
- case 数：72
- family 数：12
- family 全通过率：1
- case 全通过率：1
- 多来源属性包通过率：1
- 错误锚点对照通过率：1
- 运行态工具绑定通过率：1
- 运行态错误目标通过率：1
- packet 属性入池保真均值：1

packet 与 runtime 的属性模态、来源保真均值都为 1.0，错误锚点和非法角色分支也全部通过，说明接地入口没有把属性折叠成无锚点标签。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e16_anchor_isolation_final.png`
- `charts/e16_attribute_integrity_final.png`
- `charts/e16_branch_pass_rates_final.png`
- `charts/e16_family_pass_matrix_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e16_multimodal_symbol_grounding_case_rows_final.csv`
  - `tables/source_tables/e16_multimodal_symbol_grounding_family_rows_final.csv`
  - `tables/source_tables/e16_multimodal_symbol_grounding_summary_final.json`
  - `tables/source_tables/e16_multimodal_symbol_grounding_whitebox_final.json`
- 清单与哈希：
  - `manifests/E16_multimodal_symbol_grounding_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
