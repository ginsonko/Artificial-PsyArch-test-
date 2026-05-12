# E09 恢复类认知感受的分层触发与门控阻断实验报告（e09_final_v1）

## 实验目的

验证恢复类认知感受是否会按条件分层触发，并在惩罚过高、把握过低或复杂度过高时被阻断。

## 逻辑预期与强证据判据

缓解、正确事件和安抚分支应分别触发对应信号；高惩罚、低把握和高复杂度对照应静默。若情绪递质方向同时符合预期，说明认知感受不只是文本标签，而参与了状态调制。

## 数据集与变量控制

实验把同一类主观状态拆成 relief、correct event、reassurance 与三个阻断分支，观察触发强度、属性生成和 NT 通道是否同步。

## 结果与解释

- 支持等级：`strong_evidence`
- case 数：84
- family 数：12
- 缓解分支通过率：1
- 正确事件通过率：1
- 安抚分支通过率：1
- 高惩罚阻断静默率：1
- 低把握阻断静默率：1
- 高复杂度阻断静默率：1
- 缓解信号强度均值：0.24

reassure_on_grasp_score_mean 为 0.5167，而 block_low_grasp_score_mean 为 0.12；reassure_on_punish_state_mean 为 0.1992，而高惩罚阻断为 0.72。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e09_conflict_relief_branch_contrast_final.png`
- `charts/e09_conflict_relief_family_pass_final.png`
- `charts/e09_conflict_relief_gating_contrast_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e09_conflict_relief_case_rows_final.csv`
  - `tables/source_tables/e09_conflict_relief_pair_rows_final.csv`
  - `tables/source_tables/e09_conflict_relief_summary_final.json`
  - `tables/source_tables/e09_conflict_relief_whitebox_final.json`
- 清单与哈希：
  - `manifests/E09_conflict_relief_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
