# E03 教师奖惩信号的局部塑形实验报告（e03_final_v1）

## 实验目的

验证教师奖励和惩罚是否会进入局部结构路径，并在后续弱探针输入中改变同一目标的行动准备。

## 逻辑预期与强证据判据

奖励历史、惩罚历史和中性历史使用同一弱天气壳。奖励分支应出现局部奖励增益，惩罚分支应出现局部惩罚减益，中性分支保持静默，并且三者的因果链字段完整。

## 数据集与变量控制

实验不把最终输出文本作为主判据，而是观察局部别名命中、文本回退命中、奖励增益和惩罚减益是否同时存在，避免把一次回答风格误判为学习。

本目录保留最小数据集文件：
- `datasets/paper_e03_F01_neutral_control_r1_v1.yaml`
- `datasets/paper_e03_F01_neutral_control_r2_v1.yaml`
- `datasets/paper_e03_F01_punish_history_r1_v1.yaml`
- `datasets/paper_e03_F01_punish_history_r2_v1.yaml`
- `datasets/paper_e03_F01_reward_history_r1_v1.yaml`
- `datasets/paper_e03_F01_reward_history_r2_v1.yaml`
- `datasets/paper_e03_F02_neutral_control_r1_v1.yaml`
- `datasets/paper_e03_F02_neutral_control_r2_v1.yaml`
- `datasets/paper_e03_F02_punish_history_r1_v1.yaml`
- `datasets/paper_e03_F02_punish_history_r2_v1.yaml`
- `datasets/paper_e03_F02_reward_history_r1_v1.yaml`
- `datasets/paper_e03_F02_reward_history_r2_v1.yaml`
- 其余 24 个数据集文件见 `datasets/` 目录。

## 结果与解释

- 支持等级：`strong_evidence`
- pair 数：12
- 奖励历史局部命中率：1
- 惩罚历史局部命中率：1
- 中性对照静默率：1
- 清晰因果链比例：1
- 奖励局部增益均值：0.392
- 惩罚局部减益均值：0.392
- 奖励增益符号检验 p 值：0.0005

drive 排序在该实验中只是辅助读数；报告采用奖励增益和惩罚减益作为主判据，因为它们更贴近 AP 内部塑形路径。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e03_reward_shaping_differences_final.png`
- `charts/e03_reward_shaping_ordered_probe_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e03_reward_shaping_pair_rows_final.csv`
  - `tables/source_tables/e03_reward_shaping_probe_rows_final.csv`
  - `tables/source_tables/e03_reward_shaping_row_metrics_final.csv`
  - `tables/source_tables/e03_reward_shaping_summary_final.json`
- 清单与哈希：
  - `manifests/E03_reward_shaping_dataset_manifest_final.json`
  - `manifests/E03_reward_shaping_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
