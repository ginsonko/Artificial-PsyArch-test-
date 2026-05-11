# E10 重复疲劳与门控新鲜度报告（e10_final_v1）

## 核心结论

- 支持等级：**strong_evidence**
- family 数：12
- 整体通过比例：1.000
- 符号检验 p 值：0.00048828
- 注意力层立刻重复抑制比例：1.000
- 注意力层变体免继承比例：1.000
- 注意力层跳过后恢复比例：1.000
- boredom 显影比例：1.000
- 高 NOV / 高奖励 / 高复杂度阻断比例：1.000 / 1.000 / 1.000

## 正文可使用的最小命题

在当前 AP 原型中，重复调节并不是一个单层开关，而是至少包含两层白箱链路：一方面，同语义上下文对象若连续入选，会在注意力层被 `repeat_attention_penalty` 即时压低，而跳过若干拍或改成新的语义上下文键后，这个惩罚会分别表现为恢复或不继承；另一方面，高 fatigue 会转成全局 repetition，但 boredom 只有在低 NOV、低奖励、低复杂度同时满足时才会显影。

## 强证据边界

- 本实验不主张“AP 已经具备完整的人类新颖体验”。
- 本实验只主张：当前实现中的重复抑制与门控新鲜度链已经白箱成立。

## family 级通过情况

| family | same_penalty | variant_zero | recovered_lower | boredom_on | high_nov_block | high_reward_block | high_complexity_block | all_ok |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F01 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F02 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F03 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F04 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F05 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F06 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F07 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F08 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F09 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F10 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F11 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F12 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

## 白箱样例

- 注意力样例 family：`F01`；stage：`recovered`
- attention penalty：`0.01171875`； repeat_key：`semctx:ctx:F01:A`；gap_calls：`3`
- boredom 样例 family：`F01`；branch：`boredom_on`
- repetition 强度：`0.82`； boredom 强度：`0.84`； attrs：`cfs_boredom|cfs_complexity|cfs_dissonance|cfs_repetition`

## 图表

- `charts/e10_repeat_fatigue_attention_contrast_final.png`
- `charts/e10_repeat_fatigue_boredom_gating_final.png`
- `charts/e10_repeat_fatigue_family_pass_final.png`

## 备注

- 注意力层和 boredom 层故意分开建模，以避免把“重复惩罚”和“缺少新鲜收益”混成同一件事。
- 这比直接跑一组自然语言重复课程更窄，但因果也更干净。
