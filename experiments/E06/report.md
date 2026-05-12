# E06 时间间隔感受的注册、到期与回投实验报告（e06_final_v1）

## 实验目的

验证 AP 是否能把认知滴答间隔转化为可注册、可等待、到期后可回投的时间感受对象。

## 逻辑预期与强证据判据

开启延迟通道时，时间因子应注册为任务，到第 3 tick 到期并执行回投；关闭延迟通道时，对照应保持静默。若绑定保持、到期执行和成对对照全部成立，说明时间感受进入了闭环。

## 数据集与变量控制

实验同时包含时间桶映射、受控重复和集成 pair 三层。这样可以区分“能识别时间桶”和“能在真实运行闭环中按时回投”。

## 结果与解释

- 支持等级：`strong_evidence`
- 时间桶样本数：12
- 时间桶完整匹配率：1
- 集成 pair 数：12
- 开启分支注册率：1
- 第 3 tick 到期率：1
- 第 3 tick 执行率：1
- 关闭分支静默率：1
- 成对对照通过率：1

integrated_on_registration_ratio、integrated_on_due3_ratio、integrated_on_exec3_ratio 与 integrated_off_quiet_ratio 均为 1.0，构成注册、到期、执行、对照静默的完整链条。

这些数值的解释重点不是单个指标越大越好，而是关键分支是否按预先设定的因果方向同时成立。若主分支通过、对照分支静默或反向成立、白箱字段能追溯到相应机制路径，则该实验进入正文强证据层。

## 图表

- `charts/e06_time_interval_bucket_weights_final.png`
- `charts/e06_time_interval_integrated_ratios_final.png`
- `charts/e06_time_interval_parallel_branches_final.png`

## 数据与复现

- `design.md`：实验变量、对照分支与判据说明。
- `tables/summary.json`：正文采用的终稿强证据汇总。
- 逐项表格：
  - `tables/source_tables/e06_time_interval_bucket_rows_final.csv`
  - `tables/source_tables/e06_time_interval_controlled_rows_final.csv`
  - `tables/source_tables/e06_time_interval_integrated_ticks_final.csv`
  - `tables/source_tables/e06_time_interval_pair_rows_final.csv`
  - `tables/source_tables/e06_time_interval_summary_final.json`
- 清单与哈希：
  - `manifests/E06_time_interval_evidence_final.json`
- 复现入口：见仓库根目录 `REPRODUCE.md`；对应脚本位于 `scripts/`，脚本会读取同级 AP 原型仓库或环境变量指定的 AP 原型路径。
