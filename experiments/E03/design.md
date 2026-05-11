# E03 设计说明（教师奖励塑形）

## 论文口径
- 本实验不主张“奖励已经让 AP 学会了完整天气决策”。
- 本实验只检验更窄、更可复现的命题：在受控监督后，后续相同弱天气壳 probe 的局部行动偏置是否发生方向性变化。

## 因果链
- 训练 tick 触发 weather_stub 或刻意不触发。
- expectation contract 在后续 tick 结算，并生成 synthetic 教师反馈 tick。
- synthetic tick 将 teacher_reward_signal / teacher_punish_signal 绑定到冻结锚点，并写入局部 alias 缓存。
- probe tick 再次出现高度相似的天气壳，action 侧通过 text fallback 读取局部信号，调制 weather_stub 的 drive。

## 为什么使用弱天气 probe
- 弱天气壳本身接近执行边界，中性条件通常不过阈值或刚好在边界附近。
- 因此奖励局部增益更容易把它推高，惩罚局部减益更容易把它压低，三组方向性更清晰。

## 主要反混淆设计
- 关闭全局 reward/punish 阈值调制，只保留局部 drive 调制。
- 关闭行动疲劳，避免 fatigue 额外抬高阈值。
- 将 drive_decay_ratio 设为 0，确保训练分支执行后旧节点 drive 在 probe 前衰减为 0，避免把残留驱动力误判为教师塑形。
- 观察 action_local_lookup_hit / text_fallback_hit 与 reward_bonus / punish_penalty 是否同时出现，确保不是只有表面相关。

