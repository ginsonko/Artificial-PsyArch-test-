# E12 结构过程态与记忆目标态报告（e12_final_v2）

## 核心结论

- 支持等级：**strong_evidence**
- family 数：12
- case 数：48
- 整体通过比例：1.000
- 符号检验 p 值：0.00048828
- 四分支通过比例：1.000 / 1.000 / 1.000 / 1.000

## 正文可使用的最小命题

在当前 AP 原型中，结构目标与情景记忆目标具有可复查的角色差异。结构目标保留为可继续进入诱发链的过程节点；同一情景记忆目标则以 memory_id 为稳定聚合键，能够汇聚不同来源与不同模式的能量，并在记忆激活池中作为具体经历目标被维护。

## family 级通过情况

| family | 记忆汇聚 | 结构过程 | 不同记忆不合并 | 记忆衰减 | all_ok |
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

## 白箱样例

- 记忆汇聚样例：family `F01`，apply_count=1，snapshot_count=1，hit_count=3，source_count=4。
- 结构过程样例：process_target_count=2，memory_snapshot_count=0。
- 不同记忆不合并样例：apply_count=2，snapshot_count=2。
- 记忆衰减样例：before_ev=1.0，after_ev=0.5，ratio=0.5。

## 图表

- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E12_process_memory_state\charts\e12_process_memory_role_split_e12_final_v2.png
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E12_process_memory_state\charts\e12_memory_convergence_e12_final_v2.png
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E12_process_memory_state\charts\e12_memory_decay_e12_final_v2.png
- H:\PA原型测试\docs\paper_artifacts_2026-05-11\E12_process_memory_state\charts\e12_process_memory_family_pass_e12_final_v2.png

