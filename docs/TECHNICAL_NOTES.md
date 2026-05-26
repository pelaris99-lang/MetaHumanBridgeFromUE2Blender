# Technical Notes

## 2026-05-25 单位链路修复

新测出的关键根因：

- 原始 FBX 用 `global_scale=1.0` 导入时 Body 世界高度就是约 `1.44m`，但导入对象上方还有 FBX Empty 父级，Armature 世界矩阵带约 `0.01` 缩放。
- 旧插件最后直接删除导入 Empty，导致子对象失去父级矩阵贡献，最终 Body 从约 `1.44m` 变成约 `144m`。
- 修复方式是在删除 Empty 前对每个子对象保留 `matrix_world` 后脱父，再删除 Empty。
- `normalize_metahuman_unit_scale()` 现在只报告身高异常，不再改 `body_arm.scale`。

当前验证值：

- 只导入：Body world bbox 高度约 `1.440570946`。
- 生成 Control Rig 后：Body world bbox 高度约 `1.440570806`。
- 生成体型控制器后：Body world bbox 高度约 `1.440570806`。
- Control Rig 手柄 mesh 使用 armature 世界缩放换算骨骼本地长度，避免单位修复后手柄从厘米级变成十几米级。

## 导入与单位

已经测到的关键事实：

- 直接 FBX 导入 Body，`global_scale=1.0` 时世界尺寸约为 `1.022 x 0.382 x 1.441`，这是合理的人体米制尺寸。
- 直接 FBX 导入 Body，`global_scale=0.01` 时世界高度约为 `0.0144`，明显太小。
- 当前插件在导入后会重命名、重挂父级、复制 Face/Body 骨骼约束；这会让 FBX 自带单位矩阵和对象局部缩放更容易变得不直观。
- 之前尝试用 `normalize_metahuman_unit_scale()` 在导入后缩放 `MH_Body_Root`，短期可让测量值看似正确，但后续生成控制器或拆父级后会重新爆比例。

建议：新窗口先让单位修复变成“导入前选择正确 scale”，不要“导入后缩放根骨架”。

## Control Rig

当前 Control Rig 主要是为了替代 UE 原生骨骼那种细点线视觉，生成更粗、更容易选中的 mesh 手柄。用户偏好：

- 八面锥/圆形轴端提示，而不是细箭头线。
- 隐藏 UE 原生骨骼，只看手柄。
- 左右对称操作时，左半边状态能镜像到右半边。
- 手柄整体略小，目前用户反馈是小一点但可接受。

下一步只需轻微调大手柄，不要重做整个 Control Rig。

## 体形调整器

用户想要的体形控制：

- 四肢长度：小臂、大臂、小腿、大腿等，调整时不应把手掌/手指一起缩放。
- 四肢粗细：左右一起调，不单独分左右。
- 躯干三块：腰、胯、胸，能调高度和粗细。
- 中文属性字段，不要英文。
- 粗细方向不应只是简单轴向缩放，后续希望支持“法向混合 + 骨骼轴向缩放”，混合比例可控。

现状：

- 有些形变有效。
- 体形控制器生成很慢，用户操作时几乎卡死。
- 躯干高度之前曾把头颈推到天上，后续有过临时修正，但需要干净工程重测。

性能清理方向：

- 只处理 LOD0。
- 每个控制器不要重复全量扫描顶点。
- 先做少量稳定控制项，别同时生成几十个 shape keys。
- 用 `foreach_get` / `foreach_set` 或 NumPy 风格数组处理，减少 Python per-vertex 写入。
- 把重生成逻辑拆成可取消或分步骤操作，避免 Blender UI 无反馈卡住。

2026-05-25 已做的性能清理：

- `build_shape_key()` 不再用每顶点/每组的 `group.weight(vertex_index)` 查询主权重和 follow 权重。
- 新增 vertex group index lookup，循环顶点时直接遍历 `vert.groups`。
- `MHARP_OT_CreateProportionShapes` 增加进度报告和每个属性耗时 JSON 记录。
- 一键流程默认跳过体型控制器，用户需要时可勾选“一键流程生成体型调节器”。
- 干净后台完整链路脚本已从超过 `180s` 未完成降到约 `17s` 完成 12 个属性。

2026-05-25 二次形体语义修正：

- 长度方向优先使用当前主 Control Rig 手柄轴向，不使用 helper/twist/in/out 这类辅助骨骼轴向。
- 躯干粗细形态键增加顶点主要权重组过滤，避免四肢、手脚、锁骨、脖头被胸/腰/胯粗细带动。
- 胸部粗细偏前后，腰部粗细偏左右和前侧，胯部粗细偏后侧并混入水平法向。

2026-05-25 三次形变数学修正：

- 四肢长度和四肢粗细都改为可调轴向曲线场，使用 `falloff_curve01(t, endpoint, curve)`，起端和末端收束到0，中段平滑过渡。
- 上肢和下肢有独立“边缘衰减程度”参数，四肢长度/粗细有独立“骨骼末端效果衰减范围”参数。
- 法向和轴向/径向方向混合使用总和为1的权重，默认四肢法向混合为 `0.35`。
- 躯干高度改为胸/腰/胯累计曲线：默认胯 `0.04`、腰 `0.74`、胸 `0.22`，并提供区块平滑参数。
- Face LOD 恢复高度跟随驱动，但 delta 按 body mesh 世界缩放和 `躯干高度` driver strength 缩小，避免旧版“推飞头颈”的问题。

2026-05-25 四次骨链传播修正：

- 四肢长度不再把 `falloff_curve01()` 当作直接位移钟形曲线使用；现在把它视为沿骨骼轴向的“拉伸密度”，再通过 `falloff_displacement01()` 做积分，得到根部位移为0、末端位移为1的累计位移曲线。这样起端/末端的拉伸趋势仍趋向0，但末端关节会被推出去。
- 长度区间不再只看当前骨骼自身 tail；会按当前侧的 `follow_roots` 找下一节根关节，例如 `thigh_l -> calf_l.head_local`，把膝盖作为大腿长度的真实末端。
- 下游链顶点现在参与 follow 平移：`大腿长度` 会把 `calf/foot/ball` 组沿大腿 Control Rig 轴向推出，`上臂长度` 会把 `lowerarm/hand` 推出，依此类推。
- 新增 `.tmp/analyze_length_chain_propagation.py`，后台验证 `thigh_l` 的 `calf_l/foot_l/ball_l` downstream 位移存在，且长度段自身满足 `start < middle < end` 的累计位移曲线。
- 用户指出当前数值范围限制偏保守；本轮只修骨链传播和长度数学，范围放宽留到后续参数调校。

2026-05-25 五次子链继承修正：

- 用户指出大幅拉长时子骨骼节点交界处仍会出现不均匀拉伸：问题是 downstream 子链虽然被推出去了，但仍按子链顶点权重混合 offset，等价于又“直接改了子骨骼节点附近的点”。
- 现在长度逻辑改成两层：父段 primary 顶点用父段累计曲线；primary group 属于 downstream 子链时，只继承父段末端 offset，整条子链刚性平移，不再按自身权重或自身位置重新算长度曲线。
- `.tmp/analyze_length_chain_propagation.py` 的断言已收紧：downstream 的 `endpoint_ratio_min/max` 必须接近 `1.0`，`endpoint_spread_ratio` 必须很小。当前 `thigh_l -> calf/foot/ball`、`upperarm_l -> lowerarm/hand` 等均通过。

2026-05-25 参数上限放宽：

- 12 个中文主控体型属性的自定义属性 UI 上限从 `1.55` 调到 `3.10`，soft max 从 `1.2` 调到 `2.4`。
- 15 个 profile 参数的 `max/soft_max` 全部按原值翻倍，例如骨骼末端效果衰减范围 `0.45 -> 0.90`，边缘衰减程度 `2.50 -> 5.00`，法向混合/区块权重 `1.0 -> 2.0`。
- 形态键 slider max 从 `0.8` 调到 `1.6`，避免较大的 dashboard ratio 被 shape key slider 截断。
- `falloff_curve01()` 和 `falloff_displacement01()` 的 endpoint 运行时上限从 `0.499` 放到 `0.999`，否则 UI 上限翻倍后仍会被内部 clamp 卡住。
- 新增 `.tmp/analyze_parameter_limits.py`，后台读取 Blender 自定义属性 UI 和 shape key slider 范围，验证所有目标上限已生效。

2026-05-25 LOD 默认隐藏修正：

- 导入时 `hide_non_lod0=True` 已经会隐藏低 LOD，但生成 Control Rig 的 `hide_deform_rigs()` 之前会把所有 Face/Body mesh 子对象强制显示，导致非 LOD0 被重新亮出。
- 新增 `apply_lod_visibility()` / `enforce_metahuman_lod_visibility()`，导入后和隐藏源骨架后都会重新应用 LOD 可见性。
- `hide_deform_rigs()` 现在接受 `hide_non_lod0`，脱父保世界矩阵后只保持 `MH_Body_LOD0` / `MH_Face_LOD0` 可见；其他 LOD 只用 `hide_set(True)` 走 Outliner 小眼睛隐藏，保持 `hide_viewport=False`、`hide_render=False`，所以用户点开小眼睛后能直接看见。
- 新增 `.tmp/analyze_lod_visibility.py`，验证导入后和 Control Rig 后 Face/Body 都只有 LOD0 可见。

2026-05-25 长度形变主权重隔离：

- 用户指出 `上臂长度` 会影响胸部外侧靠近手臂的位置。根因是长度 shape 只要顶点有一点 `upperarm` 混合权重就会被移动，即使该顶点主权重属于胸/躯干/锁骨。
- 新增 `length_primary_role()`，长度形变先按顶点主权重判断角色：父段、下游子链、或不参与。主权重不属于当前肢体段/下游链的顶点直接跳过。
- 上肢长度允许 `upperarm/lowerarm/hand/wrist/metacarpal/finger` 链，下肢长度允许 `thigh/calf/foot/ankle/ball/toe` 链；例如胸/躯干/锁骨不会因为少量上臂混合权重被上臂长度带动，`pelvis` 不会因为少量 thigh 权重被大腿长度带动。
- 新增 `.tmp/analyze_length_torso_leak.py`，检查 `MH_上臂长度` 和 `MH_大腿长度` 是否移动了主权重不属于对应肢体链的顶点；当前 `disallowed_changed_count=0`。

2026-05-25 四肢粗细基础模式隔离：

- 用户指出四肢粗细影响区域仍有问题，部分区域几乎完全不受影响。按要求先把“不均匀缩放/端点 profile/法向混合”注释隔离，未删除。
- 四肢粗细现在回退为基础模式：只处理主权重属于当前段的顶点，使用该段主 Control Rig 骨骼轴作为中心轴，在垂直轴的横截面内做统一径向放缩。
- 旧的四肢粗细法向混合和不均匀轴向 profile 保留在 `build_shape_key()` 四肢 width 分支的注释块中，后续重新设计时可恢复参考。
- 新增 `width_primary_role()`，把 `上臂/小臂/大腿/小腿` 粗细分别限制到 `upperarm/lowerarm/thigh/calf` 主权重段，避免因为少量混合权重带动躯干或相邻段。
- 新增 `.tmp/analyze_limb_width_basic_coverage.py`，基础模式最初要求上臂/小臂/大腿/小腿粗细 allowed coverage 全部为 `1.0`，disallowed moved 全部为 `0`。末端衰减接回后，端点区域允许淡出，脚本改为检查目标区域有有效响应且非目标区域不移动。

2026-05-25 参数命名与面板分组：

- 当前用户面对的 profile 名称为 `边缘衰减程度` 和 `骨骼末端效果衰减范围`；旧名 `不均匀度` / `端点收束` 只作为迁移别名保留在代码里。
- `骨骼末端效果衰减范围` 控制骨骼两端淡入淡出的空间范围，不是最小值；末端效果最小值固定为 `0`。
- 新增 `PROPORTION_PARAM_GROUPS`，并在 N 面板 `MH > 体型参数` 中按语义顺序分组显示 dashboard 自定义属性。当前顺序是四肢在前、躯干在后；四肢内部先长度和长度策略，再粗细和粗细策略。
- `profile_param()` 和 `create_dashboard()` 都支持旧属性迁移，避免已有 `.blend` 文件因为改名丢失用户调过的数值。

2026-05-25 LOD 隐藏交互修正：

- 低 LOD 默认不可见，但不再使用 `obj.hide_viewport=True` 或 `obj.hide_render=True`；这些属于更硬的隐藏层，会让用户打开小眼睛后仍看不见。
- `set_lods()` 和 `apply_lod_visibility()` 都改成：LOD0 `hide_set(False)`，低 LOD `hide_set(True)`，所有 LOD 的 `hide_viewport` / `hide_render` 均保持 `False`。
- `.tmp/analyze_lod_visibility.py` 会模拟用户重新打开低 LOD 小眼睛，确认 `visible_get=True`。

2026-05-25 体型参数语义顺序修正：

- `PROPORTION_PARAM_GROUPS` 不再把上肢/下肢/躯干策略拆成几块孤立区域，而是按用户操作流组织：`四肢长度通用 -> 上肢长度 -> 上肢粗细 -> 下肢长度 -> 下肢粗细 -> 四肢粗细通用 -> 躯干高度 -> 胸部粗细 -> 腰部粗细 -> 胯部粗细 -> 躯干粗细通用`。
- `dashboard_param_label()` 会去掉属性名前缀，例如 `上肢.长度.边缘衰减程度` 在 `上肢长度` 组内显示为 `边缘衰减程度`，减少重复文字。

2026-05-25 四肢粗细末端衰减接回：

- 四肢粗细的法向混合仍隔离，但轴向末端衰减已接回：`endpoint_fade = falloff_curve01(t, endpoint, curve)` 会参与 `上臂/小臂/大腿/小腿粗细` 的径向 delta。
- 粗细衰减的段端使用 `width_chain_axis_data()`，映射为 `upperarm -> lowerarm.head`、`lowerarm -> hand.head`、`thigh -> calf.head`、`calf -> foot.head`，避免只按骨骼自身 tail 导致大片误淡出。
- `四肢.粗细.骨骼末端效果衰减范围`、`上肢.粗细.边缘衰减程度`、`下肢.粗细.边缘衰减程度` 已恢复为有效参数。
- `四肢.粗细.X法向混合` 仍不参与计算；旧 `四肢.粗细.法向混合`、`X法向混合`、`法向混合` 会迁移到新名并删除。
- `.tmp/analyze_limb_width_endpoint_fade.py` 检查粗细 shape key 的归一化效果：中段接近 `1.0`，起端/末端显著低于中段。

2026-05-25 小臂粗细顺序修正：

- `PROPORTION_DEFS` 的生成顺序现在和 `PROPORTION_PARAM_GROUPS` 的语义顺序保持一致，避免 Blender 原生 shape key、driver、自定义属性列表继续按旧的“长度全在前、粗细全在后”排序。
- 当前顺序为：上肢长度主控、上肢粗细主控、下肢长度主控、下肢粗细主控、躯干主控。也就是 `小臂粗细` 紧跟 `上臂粗细`，不会再排到 `大腿长度/小腿长度` 后面。
- `.tmp/debug_forearm_width_lower_limb_leak.py` 验证 `MH_小臂粗细` 的实际变形只落在 `lowerarm` 主权重点，不移动下肢主权重点；这次问题是生成/显示顺序，不是下肢 mesh 被小臂粗细带动。

2026-05-25 边缘衰减与失效参数标记修正：

- `边缘衰减程度`、`骨骼末端效果衰减范围`、躯干区块权重等 profile 参数都是 shape key 生成参数；它们会影响顶点坐标烘焙结果，但不会在 shape key 已生成后通过 driver 实时重算顶点。
- `MH > 体型参数` 面板顶部加入 `应用并重建`，调用 `mharp.create_proportion_shapes`，用于在调整 profile 参数后重新烘焙 shape keys。
- 四肢粗细法向混合仍处于隔离状态，真实属性名改为 `四肢.粗细.X法向混合`。`PROFILE_PARAM_ALIASES` 会把旧 `四肢.粗细.法向混合`、`X法向混合`、`法向混合` 迁移到新名并删除旧名，避免原生自定义属性列表里仍出现未标 `X` 的失效项。
- `dashboard_param_label()` 遇到 inactive 参数时会补 `X`，但如果属性名去前缀后已经是 `X法向混合`，不会再变成 `XX法向混合`。
- `.tmp/analyze_edge_falloff_param_response.py` 验证重建后的边缘衰减响应：`上肢.粗细.边缘衰减程度=0.20` 时上臂边缘平均约 `0.94`，设为 `5.00` 后约 `0.25`，中段保持接近 `1.0`。

2026-05-25 骨末端衰减命名统一：

- `边缘衰减程度` 与 `骨骼末端效果衰减范围` 统一为对外名称 `骨末端衰减`。代码内部仍通过 endpoint/curve 两个变量区分“淡入范围”和“曲线指数”，但 dashboard 属性名和面板标签不再暴露这两个旧术语。
- 当前六个有效 profile key：`四肢.长度.骨末端衰减`、`上肢.长度.骨末端衰减`、`下肢.长度.骨末端衰减`、`四肢.粗细.骨末端衰减`、`上肢.粗细.骨末端衰减`、`下肢.粗细.骨末端衰减`。
- `PROFILE_PARAM_ALIASES` 兼容旧名：`边缘衰减程度`、`骨骼末端效果衰减范围`、`端点收束`、`不均匀度`。`create_dashboard()` 会迁移旧值并删除旧属性。
- `.tmp/analyze_parameter_limits.py` 会把这些旧名列为不应残留项；当前干净工程 `OLD_KEYS=[]`。

2026-05-25 上肢粗细法向混合重新激活：

- `上肢.粗细.法向混合` 是 active profile 参数，默认 `0.35`，范围 `0..1`，只用于 `上臂粗细` 和 `小臂粗细`。
- 四肢 width 分支里，只有 `item["prop"] in {"上臂粗细", "小臂粗细"}` 时读取 `profile_param(dashboard, "上肢.粗细.法向混合")`，并通过 `normalized_direction_blend(radial, projected_normal, normal_mix)` 混合方向。
- 下肢粗细仍保持骨骼横截面径向；长度分支仍只使用骨轴累计位移和骨末端衰减，不读取法向混合。
- `PROFILE_PARAM_ALIASES` 会把旧 `四肢.粗细.X法向混合`、`四肢.粗细.法向混合`、`X法向混合`、`法向混合` 迁移到 `上肢.粗细.法向混合`，避免旧失效参数残留。
- `.tmp/analyze_upper_limb_normal_mix_response.py` 验证 `normal_mix=0` 与 `normal_mix=1` 的方向变化，并确认 `length_normal_keys=[]`。

2026-05-25 参数 hint/tooltip 补齐：

- `PROPORTION_DEFS` 和 `PROPORTION_PROFILE_PARAMS` 现在都有面向用户的 `hint` 字段。
- `create_dashboard()` 写 Blender 自定义属性 UI 时使用 `hint` 作为 `description`，因为 Blender 的 ID property UI 实际显示 tooltip 的字段名是 `description`。
- hint 内容统一解释：这个参数控制什么、调大/调小分别怎样、主要作用范围、与相关参数的关系。
- `.tmp/analyze_parameter_limits.py` 会检查每个主控参数和 profile 参数的 tooltip 不为空、不太短，并包含 `调大` 与 `调小` 使用方向。

2026-05-25 ControlRig 体型外观同步：

- 新增 `CONTROL_SYNC_SHAPE_PREFIX = "MH_同步_"`。
- `rebuild_control_visual_shape_keys(mesh_obj, armature, dashboard)` 会给每个 `CTRL_MH_*` mesh 手柄重建同步形态键。
- 同步形态键只覆盖 `PROPORTION_DEFS` 中的 `length` 和 `vertical` 项，不覆盖粗细项；粗细改变的是体块半径，ControlRig 骨骼中心线不应该因此横向漂移。
- 同步方式是改变 ControlRig mesh 顶点的可见位置，而不是移动 control object 的 object transform。这样手柄外观能跟随 body 的长度/躯干高度，同时 Copy Location/Rotation 约束目标不被体型参数直接移动，避免 body shape key 和 armature pose 叠加出二次变形。
- `MHARP_OT_build_control_rig` 在已有 dashboard 时会自动生成同步形态键；`MHARP_OT_create_proportion_shapes` 每次重建体型 shape key 后也会自动重建同步形态键。
- 新增 `MHARP_OT_sync_control_rig_visuals`，用于手动重建 ControlRig 外观同步。
- `.tmp/analyze_controlrig_proportion_visual_sync.py` 覆盖 `上臂长度 -> CTRL_MH_lowerarm_l`、`小臂长度 -> CTRL_MH_hand_l`、`躯干高度 -> CTRL_MH_head` 三个可见跟随案例。

2026-05-25 ControlRig 粗细和显示控制：

- 新增 `CONTROL_THICKNESS_LEVELS`：`THIN=0.52`、`MEDIUM=0.74`、`LARGE=1.0`。默认 `LARGE`，保持此前可点击性最强的粗度。
- `create_handle_mesh()` 和 `handle_dimensions()` 现在接受 `thickness_scale`，只缩放横截面半径，不改变骨骼轴向长度。
- `MHARP_Settings.control_rig_thickness` 暴露三档 UI，`MHARP_OT_apply_control_rig_thickness` 会替换现有 ControlRig mesh 数据并重建 `MH_同步_` 形态键。
- `MHARP_OT_set_control_rig_display` 支持 `HIDE`、`TRANSPARENT`、`SHOW`。隐藏使用 `hide_set()`，半透明通过 `MH_Control_Visible_Handle` / `MH_Control_Global` alpha 实现。
- `MHARP_OT_set_lod_display` 支持 `HIDE`、`TRANSPARENT`、`SHOW`。只作用于 LOD0 以外的 `MH_Body_LOD*` / `MH_Face_LOD*`。
- LOD 半透明会把低 LOD material slot 临时设为 `MH_LOD_Transparent_Display`，原材质名保存在 `mharp_original_lod_materials`，切回显示/隐藏时恢复。
- `.tmp/analyze_controlrig_lod_display_controls.py` 验证三档半径排序、ControlRig hide/transparent/show、低 LOD hide/transparent/show，并检查低 LOD 隐藏没有使用 `hide_viewport`。

## 材质贴图

用户指出插件里应参考 AutoRigPro/MetaHuman 的贴图策略，不只是创建材质槽。当前目标是：

- 从 `DCCExport` 附近的 Maps/Textures 目录找贴图。
- BaseColor/Albedo 接颜色。
- Normal 走 normal map。
- Roughness/Specular/SSS/Opacity 按 MetaHuman 贴图命名策略接入。

后续不要只创建空材质。

## 代码清理重点

优先看这些函数/类：

- `import_fbx()`
- `normalize_metahuman_unit_scale()`
- `MHARP_Settings.import_scale`
- `MHARP_OT_ImportMetaHuman`
- `MHARP_OT_RunFullPipeline`
- `MHARP_OT_CreateProportionShapes`
- Control Rig 生成相关 operator

清理时建议先保持 UI 不大改，只改内部逻辑和默认值。
