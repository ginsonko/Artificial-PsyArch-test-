# E12 设计逻辑

本实验把“结构过程态与记忆目标态”收窄为三个白箱命题：同一 memory_id 可以汇聚来自不同结构和不同模式的能量；只含结构目标的过程路径不会写入记忆激活池；不同 memory_id 即使同时被赋能，也不会被错误合并成同一个记忆目标。

实验避免使用宽泛自然语言判断，而是直接观察 `apply_memory_activation_targets`、`get_memory_activation_snapshot` 和 induction 结构目标。记忆目标以 memory_id 为聚合键；结构目标以 target_structure_id 保留为可继续展开的过程节点。
