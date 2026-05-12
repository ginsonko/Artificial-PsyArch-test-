# E13 Agent 场景下的可审计记忆投影实验报告（e13_final_v1）

## 实验目的

验证 AP 作为 Agent 底层记忆投影时，是否比摘要压缩和关键词检索更能保留可审计上下文字段。

## 逻辑预期与强证据判据

AP 分支应在当前输入、能量摘要、记忆目标、记忆痕迹、认知感受、情绪递质、行动节点和提示行等字段上完整保留证据；摘要和朴素 RAG 对照可命中部分事实，但不应提供同等白箱字段。

## 数据集与变量控制

每个 family 包含直接记忆交接、改写查询交接、冲突能量选择和行动反馈交接四个分支。对照组使用摘要字段和关键词检索字段，逐 case 比较可审计信息量。

## 结果与解释

- 支持等级：`strong_evidence`
- case 数：48
- family 数：12
- family 全通过率：1
- case 全通过率：1
- AP 字段分均值：7.75
- 摘要字段分均值：0.75
- RAG 字段分均值：1.25
- AP 相对摘要优势：7
- AP 相对 RAG 优势：6.5

AP 字段分均值为 7.75，摘要为 0.75，RAG 为 1.25；AP 相对 RAG 优势为 6.5，且四个分支通过率均为 1.0。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e13_branch_pass_rates_final.png`
- `charts/e13_context_field_scores_final.png`
- `charts/e13_family_advantage_final.png`
- `charts/e13_field_matrix_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e13_agent_memory_projection_case_rows_final.csv`
  - `tables/source_tables/e13_agent_memory_projection_family_rows_final.csv`
  - `tables/source_tables/e13_agent_memory_projection_summary_final.json`
  - `tables/source_tables/e13_agent_memory_projection_whitebox_final.json`
- 清单与哈希：
  - `manifests/E13_agent_memory_projection_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
