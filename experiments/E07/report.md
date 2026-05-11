# E07 复杂度与注意力调制报告（e07_final_v1）

## 核心结论

- 支持等级：**strong_evidence**
- 源状态样本数：60
- 低复杂分支触发发散模式比例：1.000
- 中间分支保持静默比例：1.000
- 高复杂分支触发聚焦模式比例：1.000
- 源状态复杂度均值（低/中/高）：0.2351 / 0.4904 / 0.6944
- probe pair 数：12
- 统一 probe 池容量顺序通过比例：1.000
- 统一 probe 池预算顺序通过比例：1.000
- 统一 probe 池整体通过比例：1.000
- 统一 probe 池整体符号检验 p 值：0.00048828

## 正文可使用的最小命题

在受控白箱条件下，AP 当前原型中的复杂度状态已经可以稳定沿着 `complexity_score -> complexity CFS -> attention_focus_mode / attention_diverge_mode -> 下一拍注意力调制` 这条链传播，并在统一 probe 池上表现为可复现的 `top_n`、`cam_item_count` 与 `attention_energy_budget` 差异。

## 关键均值

- 下一拍 top_n 均值（低/中/高）：21.00 / 16.00 / 11.00
- 下一拍注意力预算均值（低/中/高）：6.00 / 8.00 / 10.00
- 低高分支 top_n 均值差：10.00
- 低高分支 CAM 条目数均值差：10.00
- 高低分支预算均值差：4.00

## 图表

- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E07_attention_complexity\charts\e07_attention_complexity_source_transition_e07_final_v1.png
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E07_attention_complexity\charts\e07_attention_complexity_probe_contrast_e07_final_v1.png

## 备注

- 本实验故意不使用自然语言课程样本作为主要证据，因为那类样本会混入更多旁路机制。
- 本实验也不把“复杂文本更像人”作为已证结论；正文只保留当前实现已经稳固支撑的最小白箱命题。

