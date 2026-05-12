# 强证据实验清单（Strong Evidence Manifest）

| 编号 | 实验标题 | 证据级别 | 正文统计入口数 | 汇总文件 | 说明 |
|---|---|---|---:|---|---|
| E01 | 历史特异性局部结构复用 | strong_evidence | 2 | `experiments\E01\tables\summary.json` | 严格交叉探针输入设计；正文使用时按机制级因果控制证据理解。 |
| E02 | 稳定句壳下标签替换导致结构生长 | strong_evidence | 48 | `experiments\E02\tables\summary.json` | 采用 holdout 长句壳终稿确认批次；正文主索引只呈现强证据结果。 |
| E03 | 教师奖惩信号的局部塑形 | strong_evidence | 12 | `experiments\E03\tables\summary.json` |  |
| E04 | 惩罚与奖励的双向纠偏 | strong_evidence | 12 | `experiments\E04\tables\summary.json` |  |
| E05 | 行动执行后的可复用准备痕迹 | strong_evidence | 12 | `experiments\E05\tables\summary.json` |  |
| E06 | 时间间隔感受的注册、到期与回投 | strong_evidence | 12 | `experiments\E06\tables\summary.json` |  |
| E07 | 复杂度状态调制下一拍注意力预算 | strong_evidence | 36 | `experiments\E07\tables\summary.json` |  |
| E08 | 时间显影下残差记忆受控晋升 | strong_evidence | 48 | `experiments\E08\tables\summary.json` |  |
| E09 | 恢复类认知感受的条件分层 | strong_evidence | 84 | `experiments\E09\tables\summary.json` |  |
| E10 | 重复、疲劳与恢复后的再出现 | strong_evidence | 12 | `experiments\E10\tables\summary.json` |  |
| E11 | 有限分层能量图景与阈值剪枝 | strong_evidence | 72 | `experiments\E11\tables\summary.json` |  |
| E12 | 结构过程态与记忆目标态 | strong_evidence | 48 | `experiments\E12\tables\summary.json` |  |
| E13 | Agent 场景下的可审计记忆投影 | strong_evidence | 12 | `experiments\E13\tables\summary.json` |  |
| E14 | 奖惩状态对行动阈值与局部驱动力的调制 | strong_evidence | 144 | `experiments\E14\tables\summary.json` |  |
| E15 | 自适应调参器的方向稳定性 | strong_evidence | 96 | `experiments\E15\tables\summary.json` |  |
| E16 | 多来源属性化接地入口与锚点隔离 | strong_evidence | 72 | `experiments\E16\tables\summary.json` |  |
| E17 | 内部候选链的跨拍承接与续写 | strong_evidence | 192 | `experiments\E17\tables\summary.json` |  |

正文统计入口总数：**914**。不同实验的入口单位按主判据选择，可能是 pair、case、family 或 step；`strong_evidence_overview.csv` 中的 `evidence_entry_count` 与 `entry_unit` 给出机器可读口径，具体解释见各实验 `report.md`。

文件级来源映射与 SHA-256 哈希保存在 `manifest.json`。

AP 原型复现口径：本附件记录的原型基准提交为 `f1a54e84bc2b9575fc41a3e00c5addc5a639c0bf`。完整复现 E01-E17 时，应在该提交上应用 `prototype_delta/Artificial-PsyArch-reproduction-delta-v2026-05-12.patch`。该补丁经审计只覆盖复现实验所需的原型增量，SHA-256 为 `5CA9E14FDCA94C3FA7CF8582A66E040B7B4CA10A9F6D9559BB22F194C0FB8907`。

`manifest.json` 中使用 `ap-paper-artifacts://` 和 `ap-prototype://` 记录可移植来源标识。`ap-paper-artifacts://` 指向论文实验输出分支，`ap-prototype://` 指向 AP 原型仓库内的相对路径；二者用于说明来源关系，不暴露作者本机目录。根清单中的 bytes 与 SHA-256 均按本附件仓库内公开文件重新计算。本清单以 `strong_evidence` 为正文证据准入级别。
