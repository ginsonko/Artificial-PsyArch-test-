# E09 恢复类认知感受分层链路报告（e09_final_v1）

## 核心结论

- 支持等级：**strong_evidence**
- family 数：12
- 整体通过比例：1.000
- 符号检验 p 值：0.00048828
- relief-only 通过比例：1.000
- correct_event 通过比例：1.000
- correct_event 阻断静默比例：1.000
- reassurance 通过比例：1.000
- 高惩罚阻断静默比例：1.000
- 低把握阻断静默比例：1.000
- 高复杂阻断静默比例：1.000

## 正文可使用的最小命题

在当前 AP 原型中，恢复类认知感受并不是一个模糊标签，而是沿着 `高认知压 -> relief -> correct_event -> reassurance` 的门槛链路分层显影。只要把同一对象的 `cp_abs` 历史差值与当前 settled 条件构造到位，相关 CFS 信号、属性绑定、局部动作与 NT 调制就会稳定出现；反之，只要把当前认知压、惩罚态、把握感或核心复杂度中的关键门控拉坏，上位恢复信号就会同步熄灭。

## 强证据边界

- 本实验不主张“所有自然语言矛盾场景都已能被 AP 稳定安抚”。
- 本实验只主张：当前实现中的恢复类认知感受门槛链与下游调制链已经白箱成立。
- 特别地，`correct_event` 的门槛依赖同一对象 `cp_abs` 的历史差值，而不是手工填写的 `delta_cp_abs` 字段。

## family 级通过情况

| family | relief_only | correct_on | correct_block | reassure_on | high_punish_block | low_grasp_block | high_complexity_block | all_ok |
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

- 样例 family：`F01`；branch：`reassurance_on`
- prior `cp_abs`：`1.18`；second `cp_abs`：`0.3`
- relief 强度：`0.24`；correct_event 强度：`0.72571429`；reassurance 强度：`0.54492308`
- 绑定属性：`cfs_complexity|cfs_correct_event|cfs_correctness|cfs_dissonance|cfs_reassurance|cfs_relief|cfs_simplicity|reward_signal`
- 动作：`attention_diverge_mode|attention_focus`

## 图表

- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E09_conflict_relief\charts\e09_conflict_relief_branch_contrast_e09_final_v1.png
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E09_conflict_relief\charts\e09_conflict_relief_family_pass_e09_final_v1.png
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E09_conflict_relief\charts\e09_conflict_relief_gating_contrast_e09_final_v1.png

## 备注

- 本实验故意使用双拍白箱构造，以避免把恢复链门槛与更高层的语言理解能力混写。
- 对正文来说，这比一个松散的“安抚故事样本”更窄，但也更硬。

