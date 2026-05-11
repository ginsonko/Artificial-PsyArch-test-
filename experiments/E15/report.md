# E15 自适应调参稳定性实验报告（e15_final_v1）

## 核心结论

- 支持等级：**strong_evidence**
- family 数：12
- case 数：96
- family 级整体通过比例：1.000
- family 级符号检验 p 值：0.00048828
- 参数方向均值：沉寂 ER保留 0.0038，沉寂 EV保留 0.0038，注意力 CAM -2.0000，EV传播 0.0500，ER诱发 0.0400。

## 正文可使用的最小命题

在当前 AP 原型中，自适应调参器可以根据短窗口指标区分不同失稳类型，并把相应 runtime 参数朝稳定化方向推进：沉寂时提高状态池保留，注意力过热时收紧 CAM，上游传播或诱发偏薄时分别调整 HDB 输入比例，输入比例已饱和时转向提高状态池 EV 保留。

## family 级通过情况

| family | 健康静默 | 沉寂保活 | 注意过热 | EV传播 | ER诱发 | EV保留 | 饱和转保留 | 关闭静默 | all_ok |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F01 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F02 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F03 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F04 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F05 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F06 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F07 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F08 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F09 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F10 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F11 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| F12 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

## 白箱样例

- 健康对照：applied=0，params=``，deltas=``。
- 沉寂保活：applied=1，params=`state_pool.default_er_decay_ratio;state_pool.default_ev_decay_ratio;state_pool.soft_capacity_start_items;state_pool.soft_capacity_full_items;attention.max_cam_items`，deltas=`state_pool.default_er_decay_ratio:0.003570;state_pool.default_ev_decay_ratio:0.003570;state_pool.soft_capacity_start_items:3.000000;state_pool.soft_capacity_full_items:3.000000;attention.max_cam_items:0.600000`。
- 注意力过热：applied=1，params=`attention.max_cam_items`，deltas=`attention.max_cam_items:-1.600000`。
- EV传播偏薄：applied=1，params=`hdb.ev_propagation_ratio`，deltas=`hdb.ev_propagation_ratio:0.047143`。
- ER诱发偏薄：applied=1，params=`hdb.er_induction_ratio`，deltas=`hdb.er_induction_ratio:0.038500`。
- EV保留偏薄：applied=1，params=`state_pool.default_ev_decay_ratio`，deltas=`state_pool.default_ev_decay_ratio:0.002853`。
- 传播饱和转保留：applied=1，params=`state_pool.default_ev_decay_ratio`，deltas=`state_pool.default_ev_decay_ratio:0.004500`。
- 关闭调参：applied=0，params=``，deltas=``。

## 图表

- `charts/e15_branch_param_heatmap_final.png`
- `charts/e15_branch_pass_rates_final.png`
- `charts/e15_family_pass_matrix_final.png`
- `charts/e15_param_delta_directions_final.png`
