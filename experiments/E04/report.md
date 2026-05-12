# E04 惩罚与奖励的双向纠偏实验报告（e04_final_v1）

## 实验目的

验证教师反馈能否同时削弱错误方向并加强正确方向，形成可复查的双向纠偏痕迹。

## 逻辑预期与强证据判据

错误目标被惩罚后应留下负向局部信号，正确目标被奖励后应留下正向局部信号；中性目标不应出现同类塑形。若纠偏总局部信号、正确目标相对中性增强和错误目标相对中性抑制同时成立，才支持该命题。

## 数据集与变量控制

每个 pair 都包含被纠偏目标、被惩罚目标和中性对照。实验把“改正了什么”和“压下了什么”分开计量，避免只证明奖励有效而没有证明惩罚边界。

本目录保留最小数据集文件：
- `datasets/paper_e04_F01_corrected_history_r1_v1.yaml`
- `datasets/paper_e04_F01_neutral_control_r1_v1.yaml`
- `datasets/paper_e04_F01_punished_history_r1_v1.yaml`
- `datasets/paper_e04_F02_corrected_history_r1_v1.yaml`
- `datasets/paper_e04_F02_neutral_control_r1_v1.yaml`
- `datasets/paper_e04_F02_punished_history_r1_v1.yaml`
- `datasets/paper_e04_F03_corrected_history_r1_v1.yaml`
- `datasets/paper_e04_F03_neutral_control_r1_v1.yaml`
- `datasets/paper_e04_F03_punished_history_r1_v1.yaml`
- `datasets/paper_e04_F04_corrected_history_r1_v1.yaml`
- `datasets/paper_e04_F04_neutral_control_r1_v1.yaml`
- `datasets/paper_e04_F04_punished_history_r1_v1.yaml`
- 其余 24 个数据集文件见 `datasets/` 目录。

## 结果与解释

- 支持等级：`strong_evidence`
- pair 数：12
- 正确目标局部命中率：1
- 被惩罚目标局部命中率：1
- 中性对照静默率：1
- 纠偏总局部信号均值：0.784
- 正确目标相对中性增强：0.392
- 错误目标相对中性抑制：0.392

summary 中 corrected_total_local_signal_mean 为 0.784，corrected_vs_neutral_right_effect_mean 与 punished_vs_neutral_wrong_effect_mean 均为 0.392，显示增强和抑制两侧同时存在。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e04_punish_correction_effects_final.png`
- `charts/e04_punish_correction_key_drives_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e04_punish_correction_pair_rows_final.csv`
  - `tables/source_tables/e04_punish_correction_probe_rows_final.csv`
  - `tables/source_tables/e04_punish_correction_summary_final.json`
- 清单与哈希：
  - `manifests/E04_punish_correction_dataset_manifest_final.json`
  - `manifests/E04_punish_correction_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
