# E08 时间显影下残差记忆受控晋升实验报告（e08_final_v1）

## 实验目的

验证残差记忆是否只在历史种子和时间线索同时满足时晋升为当前可选对象。

## 逻辑预期与强证据判据

匹配开启分支应完整通过；关闭匹配、无种子、无线索三个对照分支应在“影子候选、通配匹配、晋升选择”这条链路上保持静默。新版指标层可能仍会记录基础时间投影（例如 tick 级时间感受绑定），因此本实验不把“是否存在基础时间投影”作为 no_seed/no_cue 失败条件；真正的强证据判据是：只有同时具备历史种子和当前线索时，残差记忆才会从影子候选显影、晋升，并重新进入主竞争。若晋升只出现在 matched 分支，并且旧运行态记忆以 runtime EM 路径可见，说明显影机制受控。

## 数据集与变量控制

每个同构家族都包含 on_matched、off_matched、on_no_seed、on_no_cue 四个分支。实验用并列对照排除“只要有时间词就晋升”或“只要有旧记忆就晋升”的解释。

本目录保留最小数据集文件：
- `datasets/paper_e08_e08_final_v1_F01_off_matched.yaml`
- `datasets/paper_e08_e08_final_v1_F01_on_matched.yaml`
- `datasets/paper_e08_e08_final_v1_F01_on_no_cue.yaml`
- `datasets/paper_e08_e08_final_v1_F01_on_no_seed.yaml`
- `datasets/paper_e08_e08_final_v1_F02_off_matched.yaml`
- `datasets/paper_e08_e08_final_v1_F02_on_matched.yaml`
- `datasets/paper_e08_e08_final_v1_F02_on_no_cue.yaml`
- `datasets/paper_e08_e08_final_v1_F02_on_no_seed.yaml`
- `datasets/paper_e08_e08_final_v1_F03_off_matched.yaml`
- `datasets/paper_e08_e08_final_v1_F03_on_matched.yaml`
- `datasets/paper_e08_e08_final_v1_F03_on_no_cue.yaml`
- `datasets/paper_e08_e08_final_v1_F03_on_no_seed.yaml`
- 其余 36 个数据集文件见 `datasets/` 目录。

## 结果与解释

- 支持等级：`strong_evidence`
- case 数：48
- family 数：12
- 匹配开启通过率：1
- 匹配关闭静默率：1
- 无种子静默率：1
- 无线索静默率：1
- 匹配分支晋升率：1
- 旧运行态记忆可见率：1

on_matched_selected_promoted_ratio 为 1.0，三个对照分支的 selected_promoted_ratio 均为 0.0，说明晋升条件具有清晰边界。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e08_time_like_residual_promotion_contrast_final.png`
- `charts/e08_time_like_residual_promotion_family_pass_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e08_time_like_residual_promotion_case_rows_final.csv`
  - `tables/source_tables/e08_time_like_residual_promotion_pair_rows_final.csv`
  - `tables/source_tables/e08_time_like_residual_promotion_summary_final.json`
  - `tables/source_tables/e08_time_like_residual_promotion_whitebox_final.json`
- 清单与哈希：
  - `manifests/E08_time_like_residual_promotion_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
