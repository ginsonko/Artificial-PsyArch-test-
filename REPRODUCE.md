# 复现实验指南（Reproduction Guide）

## 1. 目录布局

建议使用如下布局：

```text
workspace/
  Artificial-PsyArch/
  Artificial-PsyArch-test实验论文数据集附件/
```

`scripts/*.py` 默认假定 AP 原型目录位于附件仓库的同级目录，名称为 `Artificial-PsyArch`。如果实际目录不同，可以修改脚本顶部的 `AP_ROOT`，也可以在运行前建立同名目录链接。

## 2. 环境准备

1. 安装 Python 3.11 或更新版本。
2. 进入 AP 原型仓库，安装其运行依赖。
3. 确保可以从 Python 导入 `observatory`、`hdb`、`state_pool` 等 AP 原型模块。它们分别对应原型中的观测运行入口、全息深度数据库和状态池等核心模块。

## 3. 重新运行单个实验

每个实验脚本都可以单独执行。示例：

```powershell
python .\scripts\run_paper_e02_label_switch_experiment.py --help
python .\scripts\run_paper_e17_internal_narrative_chain_experiment.py --help
```

不同实验的参数略有差异。建议先运行 `--help`，再按报告中的终稿批次参数执行。默认脚本会把实验结果写入 AP 原型仓库的论文实验输出目录（artifact）；复现者可以直接比较新旧 `summary.json`、CSV 与图表，也可以在脚本顶部调整输出目录以适配自己的工作区。

## 4. 重新生成论文级总览图

```powershell
python .\scripts\make_paper_quality_charts_v02.py
```

该脚本只读取终稿强证据表格，并重新生成 `paper_quality_charts_v02` 中的总览图。若你加入新的强证据实验，应同步更新脚本中的实验索引。

## 5. 校验附件完整性

`manifest.json` 中保存了每个复制文件的 SHA-256。复现者可以用任意哈希工具校验文件是否被修改。正文只引用 `support_level = strong_evidence` 的终稿汇总结果。

## 6. 结果解释口径

这些实验用于验证 AP 原型中若干可运行机制片段：结构复用、标签替换生长、奖惩塑形、行动闭环、时间回投、注意力调制、认知感受、有限能量扩散、Agent 记忆投影、行动阈值、属性化接地和内部候选链。它们共同展示 AP 作为拟人认知闭环架构的可运行路径，并为更长时间、更大规模、多模态具身环境下的后续验证提供基础。
