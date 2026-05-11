# E14 CFS/NT 对行动阈值调制实验报告（e14_final_v1）

## 核心结论

- 支持等级：**strong_evidence**
- family 数：12
- case 数：144
- family 级整体通过比例：1.000
- family 级符号检验 p 值：0.00048828
- 阈值均值：基线 0.970，奖励 0.695，期待 NT 0.935，压力 1.321，压力 NT 1.018
- 局部驱动均值：基线 0.313，奖励 0.430，惩罚 0.159

## 正文可使用的最小命题

在当前 AP 原型中，认知感受可以经由先天规则转化为情绪递质更新，递质状态与全局奖惩状态共同改变行动节点的实时阈值；同一目标对象上的局部奖励或惩罚信号则改变该行动节点本轮获得的驱动力。两条链路都能进一步改变首次执行时机。

## family 级通过情况

| family | 奖励阈值 | 期待NT | 压力阈值 | 压力NT | 奖励固定 | 压力固定 | 局部奖 | 局部惩 | 禁用 | all_ok |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F01 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F02 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F03 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F04 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F05 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F06 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F07 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F08 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F09 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F10 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F11 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F12 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

## 白箱样例

- 中性基线：family `F01`，第1 tick 阈值=0.970400，第1 tick drive=0.310000，首次执行 tick=4，IESM emotion_update_abs_total=0.000000，local_scale=1.000000。
- 正确/奖励降阈：family `F01`，第1 tick 阈值=0.711876，第1 tick drive=0.310000，首次执行 tick=3，IESM emotion_update_abs_total=0.218400，local_scale=1.000000。
- 压力/惩罚升阈：family `F01`，第1 tick 阈值=1.298215，第1 tick drive=0.310000，首次执行 tick=5，IESM emotion_update_abs_total=0.216000，local_scale=1.000000。
- 局部奖励增驱动：family `F01`，第1 tick 阈值=1.000000，第1 tick drive=0.418810，首次执行 tick=3，IESM emotion_update_abs_total=0.000000，local_scale=1.351000。
- 局部惩罚降驱动：family `F01`，第1 tick 阈值=1.000000，第1 tick drive=0.166780，首次执行 tick=6，IESM emotion_update_abs_total=0.000000，local_scale=0.538000。

## 图表

- `charts/e14_drive_threshold_curves_final.png`
- `charts/e14_execution_timing_final.png`
- `charts/e14_family_pass_matrix_final.png`
- `charts/e14_local_drive_final.png`
- `charts/e14_threshold_modulation_final.png`
