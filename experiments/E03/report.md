# E03 教师奖惩信号局部塑形实验报告（e03_final_v1）

## 结论摘要

- 支持等级：**strong_evidence**
- pair 数：12
- 奖励历史局部命中比例：1.000
- 惩罚历史局部命中比例：1.000
- 中性对照静默比例：1.000
- 清晰因果链比例：1.000
- 奖励局部增益均值：0.3920
- 惩罚局部减益均值：0.3920
- 奖励局部增益符号检验 p 值：0.00048828
- 惩罚局部减益符号检验 p 值：0.00048828

## 设计逻辑

本实验验证一个局部而可复查的教师塑形命题：在受控监督后，后续相同弱天气壳探针输入的局部行动偏置是否发生方向性变化。实验设置 reward_history（奖励历史）、punish_history（惩罚历史）和 neutral_control（中性对照）三支。奖励或惩罚并不直接改写最终结论文本，而是经由局部别名、文本回退命中和行动侧局部增益/减益，影响后续同目标弱探针输入上的行动准备过程。

## 核心观察

奖励历史与惩罚历史都稳定命中局部塑形链路，中性对照保持静默。奖励分支的局部奖励增益均值为 0.3920，惩罚分支的局部惩罚减益均值为 0.3920，两项符号检验均达到 0.00048828。因此，本实验支持“教师奖惩可以冻结为后续局部行动偏置”的最小机制结论。

需要注意的是，drive 排序在本实验中作为辅助读数，而不是主判据。奖励分支在训练阶段也可能消耗部分行动驱动力，因此正文采用更贴近机制链路的局部命中、别名叠加、奖励增益和惩罚减益作为准入判据。

## 图表

- `charts/e03_reward_shaping_differences_final.png`
- `charts/e03_reward_shaping_ordered_probe_final.png`

## 数据与清单

- `tables/source_tables/e03_reward_shaping_pair_rows_final.csv`
- `tables/source_tables/e03_reward_shaping_probe_rows_final.csv`
- `tables/source_tables/e03_reward_shaping_row_metrics_final.csv`
- `tables/source_tables/e03_reward_shaping_summary_final.json`
- `manifests/E03_reward_shaping_dataset_manifest_final.json`
- `manifests/E03_reward_shaping_evidence_final.json`
