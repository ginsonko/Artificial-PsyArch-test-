# E04 教师惩罚纠偏报告（e04_final_v1）

## 结果摘要
- 支持等级：**strong_evidence**
- pair 数：12
- corrected lookup 比例：1.000
- punished lookup 比例：1.000
- neutral quiet 比例：1.000
- clean causal chain 比例：1.000
- corrected 内部选择性均值：0.0000
- corrected 双向局部信号总量均值：0.7840
- 正确目标奖励效应均值：0.3920
- 错误目标惩罚效应均值：0.3920
- corrected 选择性 sign test p：0.000488
- corrected 总信号 sign test p：0.000488

## 参数
- reward_strength：0.750
- punish_strength：0.700
- reward_coef：0.900
- punish_coef：0.900
- alias_ttl：8

## 图表
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E04_punish_correction\charts\e04_punish_correction_key_drives_e04_final_v1.png
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E04_punish_correction\charts\e04_punish_correction_effects_e04_final_v1.png

## Pair 明细

| case | rep | wrong city | right city | corrected selectivity | corrected total signal | corrected bonus | punished penalty | clean |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: |
| F01 | 1 | 上海 | 北京 | 0.000 | 0.784 | 0.392 | 0.392 | 1 |
| F02 | 1 | 广州 | 杭州 | 0.000 | 0.784 | 0.392 | 0.392 | 1 |
| F03 | 1 | 成都 | 武汉 | 0.000 | 0.784 | 0.392 | 0.392 | 1 |
| F04 | 1 | 西安 | 南京 | 0.000 | 0.784 | 0.392 | 0.392 | 1 |
| F05 | 1 | 苏州 | 长沙 | 0.000 | 0.784 | 0.392 | 0.392 | 1 |
| F06 | 1 | 青岛 | 天津 | 0.000 | 0.784 | 0.392 | 0.392 | 1 |
| F07 | 1 | 福州 | 郑州 | 0.000 | 0.784 | 0.392 | 0.392 | 1 |
| F08 | 1 | 厦门 | 济南 | 0.000 | 0.784 | 0.392 | 0.392 | 1 |
| F09 | 1 | 昆明 | 合肥 | 0.000 | 0.784 | 0.392 | 0.392 | 1 |
| F10 | 1 | 宁波 | 南昌 | 0.000 | 0.784 | 0.392 | 0.392 | 1 |
| F11 | 1 | 太原 | 海口 | 0.000 | 0.784 | 0.392 | 0.392 | 1 |
| F12 | 1 | 兰州 | 大连 | 0.000 | 0.784 | 0.392 | 0.392 | 1 |

## 运行规模
- datasets：36
- runs：36
