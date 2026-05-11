# E16 多模态/符号接地入口实验报告

## 结论摘要

- 支持等级：**strong_evidence**
- family 数：12
- case 数：72
- family 级整体通过比例：1.000
- case 级通过比例：1.000
- family 级符号检验 p 值：0.00048828

## 正文可使用的最小命题

当前 AP 原型已经提供多来源属性化接地入口。属性刺激元可以来自 vision/tactile/tool 等非文本来源，进入同一状态池；锚点对象能够获得 packet 属性或 runtime 绑定属性的可复查视图；错误锚点和非法角色对照保持静默。该结论不扩写为完整视觉理解能力。

## family 判据矩阵

| family | packet绑定 | 错锚对照 | 折叠对照 | runtime绑定 | 错目标对照 | 非法角色 | 全部通过 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F01 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F02 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F03 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F04 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F05 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F06 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F07 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F08 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F09 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F10 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F11 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F12 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

## 图表

- `charts/e16_anchor_isolation_final.png`
- `charts/e16_attribute_integrity_final.png`
- `charts/e16_branch_pass_rates_final.png`
- `charts/e16_family_pass_matrix_final.png`
