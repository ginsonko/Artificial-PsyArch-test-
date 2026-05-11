# E05 先天行动闭环报告（e05_final_v1）

## 核心结论
- 支持等级：**strong_evidence**
- pair 数量：12
- 显式训练触发比例：1.000
- source-visible 执行比例：1.000
- runtime 回投比例：1.000
- probe runtime presence 比例：1.000
- probe drive 优势比例：1.000
- probe margin 优势比例：1.000
- 完整闭环比例：1.000
- probe drive 优势均值：0.1928
- probe margin 优势均值：0.1928
- drive sign test p：0.00048828
- margin sign test p：0.00048828

## 运行参数
- local reward coef：0.900
- local punish coef：0.900
- alias TTL：6
- drive_decay_ratio：0.0
- action_fatigue_enabled：false
- threshold_scale_by_rwd_pun_enabled：false

## 判据解释

本实验不要求后续弱天气 probe 直接跨过 weather_stub 阈值，也不把“是否已经形成完整天气策略”作为命题。
正文只使用更窄的两段链条：

1. 显式查询分支必须形成 source-visible 的原生行动完成与 runtime action-node 回投。
2. 在同样的后续弱天气 probe 下，显式执行史分支必须比弱历史对照分支表现出更高的行动准备度。

由于实验中把 `drive_decay_ratio` 设为 `0.0`，后续 probe 上的优势不能被解释为简单的前一 tick drive 残留。

## 图表

- `charts/e05_action_closure_chain_ratios_final.png`
- `charts/e05_action_closure_probe_drive_final.png`

## Pair 明细

| case | rep | city | event | explicit buffer exec | runtime projection | explicit probe drive | weak probe drive | drive advantage | margin advantage | clean chain |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F01 | 1 | 北京 | 医院复查 | 1 | 1 | 0.325 | 0.135 | 0.190 | 0.190 | 1 |
| F02 | 1 | 杭州 | 外出拍照 | 1 | 1 | 0.326 | 0.133 | 0.193 | 0.193 | 1 |
| F03 | 1 | 武汉 | 学校办手续 | 1 | 1 | 0.327 | 0.133 | 0.193 | 0.193 | 1 |
| F04 | 1 | 南京 | 参加答辩 | 1 | 1 | 0.324 | 0.133 | 0.191 | 0.191 | 1 |
| F05 | 1 | 长沙 | 见客户 | 1 | 1 | 0.323 | 0.133 | 0.190 | 0.190 | 1 |
| F06 | 1 | 天津 | 图书馆自习 | 1 | 1 | 0.326 | 0.188 | 0.138 | 0.138 | 1 |
| F07 | 1 | 郑州 | 参加培训 | 1 | 1 | 0.326 | 0.133 | 0.193 | 0.193 | 1 |
| F08 | 1 | 济南 | 转机出差 | 1 | 1 | 0.326 | 0.133 | 0.193 | 0.193 | 1 |
| F09 | 1 | 合肥 | 去展会 | 1 | 1 | 0.326 | 0.133 | 0.193 | 0.193 | 1 |
| F10 | 1 | 南昌 | 看演出 | 1 | 1 | 0.356 | 0.133 | 0.223 | 0.223 | 1 |
| F11 | 1 | 海口 | 实验室开会 | 1 | 1 | 0.326 | 0.133 | 0.192 | 0.192 | 1 |
| F12 | 1 | 大连 | 探望亲戚 | 1 | 1 | 0.356 | 0.133 | 0.223 | 0.223 | 1 |

## 附件统计
- datasets: 24
- runs: 24
