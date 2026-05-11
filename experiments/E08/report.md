# E08 时间显影下的残差记忆受控晋升报告（e08_final_v1）

## 核心结论

- 支持等级：**strong_evidence**
- family 数：12
- 四分支整体通过比例：1.000
- 四分支整体符号检验 p 值：0.00048828
- on_matched 通过比例：1.000
- off_matched 静默比例：1.000
- on_no_seed 静默比例：1.000
- on_no_cue 静默比例：1.000

## 正文可使用的最小命题

在 `runtime_em_only` 主链中，只要旧 seed 记忆与延迟 cue 同时存在，时间样属性就可以进入当前刺激级匹配，使影子残差记忆候选从“仅可见”提升为“可晋升、可重新竞争”的对象。关闭晋升开关、拿掉 seed 或拿掉 cue 后，这条链会同步熄灭。

## 四分支对照

| family | on_matched | off_matched quiet | on_no_seed quiet | on_no_cue quiet | all_ok |
| --- | ---: | ---: | ---: | ---: | ---: |
| F01 | 1 | 1 | 1 | 1 | 1 |
| F02 | 1 | 1 | 1 | 1 | 1 |
| F03 | 1 | 1 | 1 | 1 | 1 |
| F04 | 1 | 1 | 1 | 1 | 1 |
| F05 | 1 | 1 | 1 | 1 | 1 |
| F06 | 1 | 1 | 1 | 1 | 1 |
| F07 | 1 | 1 | 1 | 1 | 1 |
| F08 | 1 | 1 | 1 | 1 | 1 |
| F09 | 1 | 1 | 1 | 1 | 1 |
| F10 | 1 | 1 | 1 | 1 | 1 |
| F11 | 1 | 1 | 1 | 1 | 1 |
| F12 | 1 | 1 | 1 | 1 | 1 |

## 分支均值

| 分支 | 时间绑定 | 时间 wildcard | 影子候选 | 影子晋升 | 晋升后重入主竞争 |
| --- | ---: | ---: | ---: | ---: | ---: |
| on_matched | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| off_matched | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| on_no_seed | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| on_no_cue | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

## 白箱样例

标准 matched 样例使用 5 个 source tick：`seed -> empty -> empty -> cue -> empty`。在 observation tick 中，旧运行态记忆仍然可见，且主链路径为 `runtime_em_only`。

- 样例 family：`F01`；branch：`on_matched`
- 旧运行态记忆可见条数：`2`
- 主竞争最终入选模式：`promoted_shadow_raw_residual`
- 影子候选种类：`raw_residual_memory`；memory_id：`em_000006`
- 影子候选是否带时间 wildcard：`1`；晋升结构 id：`st_000030`

## 图表

- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E08_time_like_residual_promotion\charts\e08_time_like_residual_promotion_contrast_e08_final_v1.png
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E08_time_like_residual_promotion\charts\e08_time_like_residual_promotion_family_pass_e08_final_v1.png

## 备注

- 本实验不主张广义情景回忆，只主张“时间显影下的残差记忆受控晋升”。
- 本实验不主张线索词身份选择性，因为当前实现中，错误 cue 并不会稳定熄灭这条链。

