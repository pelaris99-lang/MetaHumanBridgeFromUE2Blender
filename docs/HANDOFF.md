# MetaForge Handoff

## 2026-05-25 继续工作记录

本轮已在干净 Blender 后台工程验证并修复两个优先问题：

1. 单位爆比例根因不是 FBX 原始导入，而是插件删除 FBX Empty 父级时没有先保留子对象世界矩阵。FBX 导入后 Empty/Armature 链上带有 `0.01` 世界缩放；旧代码直接 `remove(empty, do_unlink=True)` 后，Body 最终会从约 `1.44m` 变成约 `144m`。
2. 已把插件默认 `import_scale` 改为 `1.0`，并把 `normalize_metahuman_unit_scale()` 改成只检测/报告异常，不再缩放根骨架补救单位。
3. 已新增 `remove_empties_keep_children()`，删除导入 Empty 前先让子对象脱父并保持世界矩阵。
4. 体型控制器生成已从超过 `180s` 未完成降到约 `17s` 完成 12 个属性。主要改动是把每顶点多次 `vertex_group.weight()` 查询换成预建 group index lookup 后遍历 `vertex.groups`。
5. 一键流程默认跳过体型控制器，只跑导入和 Control Rig，避免用户点击一键后 UI 长时间卡住。UI 中新增“只处理LOD0体型”和“一键流程生成体型调节器”开关。
6. Control Rig 手柄按 armature 世界缩放换算为米制视觉尺寸，并在此基础上略微放大；干净测试里上臂手柄 bbox 约 `0.136m`，不再是十几米级。

已跑过的后台验证：

- `.tmp/test_import_scale_1_only.py`：导入后 `MH_Body_LOD0` world bbox 高度 `1.440570946`。
- `.tmp/test_pipeline_scale_1.py`：导入、Control Rig、体型控制器后高度均保持约 `1.4405708`；12 个体型属性生成完成。
- `.tmp/test_full_pipeline_default_skip.py`：默认一键流程约 `6.2s` 完成，shape key 数量 `0`，Control Rig 对象存在。
- `.tmp/clean_metahuman_pipeline_test.py`：完整流程通过；本次为释放磁盘空间删除了 `.tmp/clean_metahuman_pipeline_test.blend` 临时副本，正式样例保留在工作区根目录和 handoff examples。

注意：用户后来明确要求“这次做完不要目视检查，我自己来看”。除非用户重新要求，不要主动截图或目视检查。`GraceSwat` 用户工程仍不要作为试错场，避免覆盖用户现场。

## 2026-05-25 二次修正记录

用户指出 Control Rig 仍偏小、长度方向错、躯干粗细影响四肢，并要求胸/腰/胯的粗细方向更符合语义。已在干净工程继续修：

- Control Rig 手柄再次放大，尤其是头/脊柱/手脚小控件；`.tmp/controlrig_visual/front.png` 和 `side.png` 可用于目视检查。
- 长度形态键方向改为按当前主 Control Rig 手柄轴向：`upperarm_l/r`、`lowerarm_l/r`、`thigh_l/r`、`calf_l/r`。不要再让 `upperarm_in_l`、twist、helper 等横向辅助骨骼决定长度方向。
- `probe_length_axis.py` 验证长度 delta 与主控制器轴向点积约 `1.0`。
- 躯干粗细先按顶点主要权重组过滤，排除四肢、手脚、锁骨、脖头等组；`render_controlrig_views.py` 当前记录胸/腰/胯粗细的 limb_changed_ratio 都为 `0.0`。
- 胸部粗细：前后厚度为主，左右少。
- 腰部粗细：左右为主，前面次之，后面很少。
- 胯部粗细：后侧为主，前侧很少，并混入更多水平法向。

本轮仍没有碰 `GraceSwat`。

## 2026-05-25 三次形变数学修正记录

用户指出躯干高度、长度和粗细都需要更明确的数学曲线，而不是硬切或均匀缩放。已继续修：

- 新增分层生成参数，写入“身体比例控制”自定义属性：`四肢.长度.*`、`上肢.长度.*`、`下肢.长度.*`、`四肢.粗细.*`、`躯干.高度.*`、`胸部/腰部/胯部.粗细.法向混合`。
- 四肢长度不再做近似均匀整体位移；改成沿当前主 Control Rig 轴向的曲线场，起端和末端收束到0，中段由“边缘衰减程度”控制更接近均匀或更集中。
- 四肢粗细也改用同一类轴向曲线场，在垂直于骨骼轴向的横截面内变形；径向和法向用总和为1的混合权重。
- 躯干高度改成累计曲线：胯权重默认极小，腰权重最大，胸权重较小。上方头颈/Face 不再被完全落下；Face LOD 现在有高度跟随驱动。
- 后台验证：完整干净流程通过，Face 高度跟随驱动 `8` 个，分层 profile 参数 `15` 个；默认一键流程仍跳过体型调节器并完成。

按用户要求，本轮修完后没有再做目视检查。

## 2026-05-25 四次骨链传播修正记录

用户指出长度调整必须尊重骨骼节点链路：例如大腿应从 `thigh` 向下追到 `calf` 根关节，也就是膝盖，长度增加时膝盖以下整条链要被推出去，而不是只有大腿上半截变形。已继续修：

- 长度形态键不再使用“中段最大、两端为0”的直接位移钟形曲线；改成把该曲线当作拉伸密度，再积分成累计位移。结果是根部位移为0、末端位移为完整长度偏移，同时起末端拉伸趋势仍平滑趋近0。
- 长度段的末端改成按当前侧 `follow_roots` 找真实子关节，例如 `thigh_l -> calf_l.head_local`、`calf_l -> foot_l.head_local`、`upperarm_l -> lowerarm_l.head_local`。
- follow 链顶点现在会拿到末端平移：`大腿长度` 会推动 `calf_l/foot_l/ball_l`，`上臂长度` 会推动 `lowerarm_l/hand_l`。
- 新增 `.tmp/analyze_length_chain_propagation.py`，不截图，只做后台数值验证；当前 `thigh_l` 的 `calf_l/foot_l/ball_l` downstream 位移均已测到，且轴向点积约 `1.0`。
- 用户指出 slider/driver 数值范围偏保守；后续已完成上限放宽，见“参数上限放宽记录”。

## 2026-05-25 五次子链继承修正记录

用户继续指出：大幅拉长时子骨骼节点交接处仍有不均匀拉伸，子骨骼节点不应该被直接按自己的权重/位置修改；它应该因为父骨骼长度变化而整体被推出去。已修：

- `length_delta_for_vertex()` 新增 `primary_is_follow` 判断。父段 primary 顶点仍按父段累计曲线变形；primary group 属于 downstream 子链的顶点，则只继承父段末端 offset。
- 删除了 downstream 子链按 `follow_weight` 混合 offset 的旧策略，避免子链根附近因为权重不满而出现 `0.65-1.0` 的不均匀位移。
- `.tmp/analyze_length_chain_propagation.py` 的检查收紧为 rigid inheritance：downstream 的 `endpoint_ratio_min/max` 接近 `1.0`，`endpoint_spread_ratio` 接近 `0` 才算通过。
- 当前后台结果：`thigh_l -> calf_l/foot_l/ball_l` 的 endpoint ratio 约 `0.9999999-1.0000001`，spread 约 `1e-7`；`upperarm/lowerarm/calf` 链也通过。

## 2026-05-25 参数上限放宽记录

用户指出参数范围限制仍太保守，要求最大值一律调到现有两倍。已修：

- 12 个主控体型属性 UI 范围：`max 1.55 -> 3.10`，`soft_max 1.2 -> 2.4`。
- 15 个 profile 参数：全部 `max/soft_max` 翻倍，例如骨骼末端效果衰减范围 `0.45 -> 0.90`，边缘衰减程度 `2.50 -> 5.00`，法向混合和区块权重 `1.0 -> 2.0`。
- shape key `slider_max 0.8 -> 1.6`，避免更大 dashboard ratio 被 key block slider 截断。
- endpoint 运行时 clamp 从 `0.499` 放宽到 `0.999`，否则骨骼末端效果衰减范围参数虽然 UI 翻倍但实际仍不会超过旧限制。
- 新增 `.tmp/analyze_parameter_limits.py`，当前 `.tmp/parameter_limit_metrics.json` 显示 `failures: []`。

## 2026-05-25 LOD 默认隐藏修正记录

用户提醒默认隐藏 LOD0 以外的网格。导入阶段本来已经按 `hide_non_lod0=True` 处理，但生成 Control Rig 时 `hide_deform_rigs()` 会把 Face/Body 的所有 mesh 子对象重新设为可见。已修：

- 新增 LOD 可见性 helper：`apply_lod_visibility()` / `enforce_metahuman_lod_visibility()`。
- 导入后、隐藏源骨架后都会重新应用 LOD0-only 可见性。
- `hide_deform_rigs()` 脱父 mesh 时不再无条件显示所有 mesh，而是只让 `MH_Body_LOD0` 和 `MH_Face_LOD0` 可见；其他 LOD 现在只用 Outliner 小眼睛隐藏，不再设置 `hide_viewport` / `hide_render` 这种会导致点开小眼睛仍不可见的硬隐藏。
- 新增 `.tmp/analyze_lod_visibility.py`，当前 `.tmp/lod_visibility_metrics.json` 显示导入后和 Control Rig 后均只有 LOD0 可见，`failures: []`。

## 2026-05-25 上臂长度胸侧泄漏修正记录

用户指出 `上臂长度` 会影响胸部外侧靠近手臂的位置。已修：

- 根因：长度形变之前只看顶点是否有当前肢体段的混合权重；胸外侧顶点虽然主权重属于胸/躯干/锁骨，但有一点 `upperarm` 权重，所以被上臂长度带动。
- 新增 `length_primary_role()`，长度形变只处理主权重属于当前肢体段或其下游子链的顶点。
- 上肢允许链：`upperarm/lowerarm/hand/wrist/metacarpal/thumb/index/middle/ring/pinky`。胸、躯干、锁骨主权重点不再参与上臂长度。
- 下肢同理隔离：`thigh/calf/foot/ankle/ball/toe`，`pelvis` 主权重点不再参与大腿长度。
- 新增 `.tmp/analyze_length_torso_leak.py`，当前 `.tmp/length_torso_leak_metrics.json` 显示 `MH_上臂长度` 和 `MH_大腿长度` 的 `disallowed_changed_count=0`，`failures: []`。

## 2026-05-25 四肢粗细基础模式记录

用户指出四肢粗细影响区域仍然有问题，有些地方几乎完全不受影响，并要求先把不均匀缩放和法向混合代码注释隔离，不删。已修：

- 四肢粗细暂时退回基础径向模式：只处理当前段主权重点，按当前段主 Control Rig 骨骼轴建立横截面，统一径向放缩。
- `上臂粗细/小臂粗细/大腿粗细/小腿粗细` 分别只看 `upperarm/lowerarm/thigh/calf` 主权重段，不用 twist/helper 自己的轴。
- 四肢粗细的法向混合和端点不均匀 profile 都已在代码里注释隔离，保留旧逻辑，后续再重新设计。
- 新增 `.tmp/analyze_limb_width_basic_coverage.py`，最初基础模式下四个四肢粗细项 allowed coverage 均为 `1.0`，disallowed changed 均为 `0`。后续已接回末端衰减，因此端点顶点允许淡出到0，测试已改为检查目标区域中段有效且非目标区域不移动。

## 2026-05-25 参数命名与分组记录

用户指出体型参数散落难找，并要求把相关参数集中到一起。已修：

- 插件版本更新到 `0.1.15`。
- profile 参数改名：`不均匀度` 改为 `边缘衰减程度`，`端点收束` 改为 `骨骼末端效果衰减范围`。
- 这里的“骨骼末端效果衰减范围”不是末端最小值；末端最小效果固定为 `0`，该参数控制骨骼两端有多长一段从 `0` 淡入主体效果。
- 旧 dashboard 属性会在重新生成/刷新体型调节器时迁移到新属性名，并删除旧别名。
- N 面板新增 `MH > 体型参数` 子面板，参数最初按 `上肢`、`下肢`、`四肢通用`、`躯干主控`、`躯干粗细策略`、`躯干高度策略` 分组显示；后续已进一步按用户要求改成更贴近使用语义的顺序，见下方 `0.1.17` 记录。
- `.tmp/analyze_parameter_limits.py` 已更新为检查新参数名，同时确认旧别名不会残留。

## 2026-05-25 LOD 小眼睛隐藏修正记录

用户指出低 LOD 默认看不见是对的，但不应该被设成点开 Outliner 小眼睛仍看不见。已修：

- 插件版本更新到 `0.1.16`。
- `set_lods()` / `apply_lod_visibility()` 现在对非 LOD0 只调用 `hide_set(True)`，并保持 `hide_viewport=False`、`hide_render=False`。
- 用户在 Outliner 点开低 LOD 的小眼睛后，低 LOD 会直接显示，不再需要额外打开 viewport disable/render disable。
- `.tmp/analyze_lod_visibility.py` 已加入“小眼睛重新打开”检查：导入后和生成 Control Rig 后，`MH_Body_LOD1` / `MH_Face_LOD1` 都能通过 `hide_set(False)` 恢复可见。

## 2026-05-25 体型参数语义顺序修正记录

用户指出参数仍然乱，给出明确规律：四肢排前、躯干排后；四肢内部应把同一部位的长度主控和长度策略放在一起，再放粗细主控和粗细策略。已修：

- 插件版本更新到 `0.1.17`。
- `PROPORTION_PARAM_GROUPS` 顺序改为：`四肢长度通用`、`上肢长度`、`上肢粗细`、`下肢长度`、`下肢粗细`、`四肢粗细通用`、`躯干高度`、`胸部粗细`、`腰部粗细`、`胯部粗细`、`躯干粗细通用`。
- 上肢长度组包含 `上臂长度`、`小臂长度`、`上肢.长度.边缘衰减程度`；上肢粗细组包含 `上臂粗细`、`小臂粗细`、`上肢.粗细.边缘衰减程度`。下肢和躯干按同一规律展开。
- 面板显示标签会自动去掉 `上肢.长度.`、`四肢.粗细.`、`躯干.高度.` 等前缀，让组内参数名更短。

## 2026-05-25 四肢粗细末端衰减接回记录

用户要求把末端衰减功能带回，并把仍因注释隔离而不能发挥作用的参数前面加 `X` 标记。已修：

- 插件版本更新到 `0.1.18`。
- 四肢粗细现在重新使用 `四肢.粗细.骨骼末端效果衰减范围`、`上肢.粗细.边缘衰减程度`、`下肢.粗细.边缘衰减程度`。
- 粗细末端衰减使用真实段端：上臂到小臂根、小臂到手根、大腿到小腿根、小腿到脚根，而不是只用骨骼自身 tail。
- 四肢粗细法向混合仍保持注释隔离；后续 `0.1.20` 已把真实属性名进一步迁移为 `四肢.粗细.X法向混合`，旧兼容属性会删除。
- 新增 `.tmp/analyze_limb_width_endpoint_fade.py`，当前中段效果接近 `1.0`，起端/末端显著小于中段，`failures: []`。

## 2026-05-25 小臂粗细顺序修正记录

用户指出“小臂放大跑到下面下肢那边”。后台检查显示 `MH_小臂粗细` 的实际变形没有移动下肢主权重点：`moved_lower_count=0`，只移动 `lowerarm` 段。问题根因是生成顺序仍按“所有长度先生成、所有粗细后生成”，导致 shape keys、driver 和原生自定义属性里 `小臂粗细` 被放在 `大腿长度/小腿长度` 之后，看起来像归到了下肢附近。已修：

- 插件版本更新到 `0.1.19`。
- `PROPORTION_DEFS` 顺序改为跟语义面板一致：`上臂长度`、`小臂长度`、`上臂粗细`、`小臂粗细`，然后才是 `大腿长度`、`小腿长度`、`大腿粗细`、`小腿粗细`，最后是躯干。
- 重新生成干净测试工程后，进度输出与 shape key 顺序均为上述顺序。
- 新增 `.tmp/debug_forearm_width_lower_limb_leak.py`，专门验证 `MH_小臂粗细` 不移动下肢主权重点。

## 2026-05-25 边缘衰减与失效参数标记修正记录

用户指出 `边缘衰减程度` 看起来没有起作用，并且仍有该标 `X` 的失效参数没有标出来。已梳理并修：

- 插件版本更新到 `0.1.20`。
- 确认 `边缘衰减程度` 会进入 shape key 顶点生成，但它是生成参数，不是生成后的实时驱动参数；调整后必须重建体型调节器才会改变已烘焙的 shape key 形状。
- 在 `MH > 体型参数` 面板顶部新增 `应用并重建`，让这类生成参数就近应用，不再需要回主面板找生成按钮。
- 失效的四肢粗细法向混合不再只靠 UI 标签临时显示 `X`，真实 dashboard 属性名迁移为 `四肢.粗细.X法向混合`；旧 `四肢.粗细.法向混合`、`X法向混合`、`法向混合` 会迁移并删除。
- 新增 `.tmp/analyze_edge_falloff_param_response.py`：把 `上肢.粗细.边缘衰减程度` 分别设为 `0.20` 和 `5.00` 后重建 `上臂粗细`，边缘平均效果从约 `0.94` 降到约 `0.25`，证明重建后参数有效；同时验证失效参数标签为 `X法向混合` 且旧失效属性已删除。

## 2026-05-25 骨末端衰减命名统一记录

用户指出 `边缘衰减` 和 `骨骼末端效果衰减范围` 这类名字应该统一叫 `骨末端衰减`。已修：

- 插件版本更新到 `0.1.21`。
- 对外 dashboard 属性统一为 `骨末端衰减`：`四肢.长度.骨末端衰减`、`上肢.长度.骨末端衰减`、`下肢.长度.骨末端衰减`、`四肢.粗细.骨末端衰减`、`上肢.粗细.骨末端衰减`、`下肢.粗细.骨末端衰减`。
- 旧名 `边缘衰减程度`、`骨骼末端效果衰减范围`、`端点收束`、`不均匀度` 都作为迁移别名保留，重建 dashboard 后旧属性会被删除。
- 当前干净工程 dashboard 检查结果：旧名列表为空，只剩 `骨末端衰减` 系列属性。

## 2026-05-25 上肢粗细法向混合重新激活记录

用户指出当前整体基本可用，要求把上肢法向混合函数重新激活，并强调法向混合只应用于粗细，不应用于长度。已修：

- 插件版本更新到 `0.1.22`。
- `四肢.粗细.X法向混合` 不再作为失效参数暴露；新有效属性为 `上肢.粗细.法向混合`，放在 `上肢粗细` 分组里。
- `上肢.粗细.法向混合` 只参与 `上臂粗细` / `小臂粗细` 的方向计算：`0` 为骨骼横截面径向，`1` 为顶点法向投影。
- 长度分支没有读取任何法向混合参数，dashboard 检查中 `length_normal_keys=[]`。
- 新增 `.tmp/analyze_upper_limb_normal_mix_response.py`，验证法向混合从 `0` 到 `1` 后，上臂/小臂粗细 delta 方向确实从径向转向法向。

## 2026-05-25 参数提示字段补齐记录

用户指出参数需要有面向使用者的 hint/tooltip，说明它是干嘛的以及怎么用。已修：

- 插件版本更新到 `0.1.23`。
- `PROPORTION_DEFS` 与 `PROPORTION_PROFILE_PARAMS` 的每个面板参数都新增 `hint` 字段。
- Blender 自定义属性 UI 仍使用它支持的 `description` 写入悬停提示，但内容来源改为 `hint`，因此代码层面和 UI 层面都保留“这是给用户看的提示”。
- 每条提示都说明：控制对象、调大/调小效果、主要影响区域，以及必要的注意事项，例如上肢法向混合不影响长度。
- `.tmp/analyze_parameter_limits.py` 现在同时检查参数 tooltip 是否足够长，并且是否解释了 `调大` / `调小` 行为。

## 2026-05-25 ControlRig 体型外观同步记录

用户指出体型变形后 ControlRig 没有跟着同步。已修：

- 插件版本更新到 `0.1.24`。
- 新增 ControlRig 可见网格同步形态键，前缀为 `MH_同步_`。
- 同步范围目前覆盖四肢长度和躯干高度：`上臂长度` 会让小臂/手等下游手柄外观跟随，`小臂长度` 会让手部跟随，`躯干高度` 会让头颈/上肢相关手柄外观跟随。
- 这里刻意只同步 ControlRig 的可见 mesh 外观，不直接移动控制物体 origin 和骨架 Copy Location/Rotation 约束目标，避免体型 shape key 之外再由骨架产生一层二次变形。
- `创建安全体型调节器` 和 `应用并重建` 会自动重建同步形态键；主面板与体型参数面板也新增 `同步ControlRig体型外观` 手动按钮。
- 新增 `.tmp/analyze_controlrig_proportion_visual_sync.py`，验证 `上臂长度=2` 时 `CTRL_MH_lowerarm_l` 可见网格移动、`小臂长度=2` 时 `CTRL_MH_hand_l` 移动、`躯干高度=2` 时 `CTRL_MH_head` 移动。

## 2026-05-25 ControlRig 粗细与显示控制记录

用户指出 ControlRig 当前有点粗，需要插件里给三档粗细，并要求 ControlRig 和 LOD 都能一键隐藏、半透明、显示。已修：

- 插件版本更新到 `0.1.25`。
- 新增 `ControlRig粗细` 三档：`细`、`中`、`粗`。默认仍为 `粗`，也就是之前最大的档位。
- 新增 `应用ControlRig粗细`，会重建 ControlRig 手柄 mesh，但保留控制层级，并重新生成体型外观同步形态键。
- 主面板新增 ControlRig 一键显示按钮：`Rig隐藏`、`半透明`、`显示`。
- 主面板新增低 LOD 一键显示按钮：`LOD隐藏`、`半透明`、`显示`。
- LOD 隐藏仍使用小眼睛隐藏：`hide_set=True`，但 `hide_viewport=False`，所以用户点开小眼睛可以直接看见。
- 低 LOD 半透明会临时替换为 `MH_LOD_Transparent_Display`，切回显示/隐藏时恢复原材质。
- 新增 `.tmp/analyze_controlrig_lod_display_controls.py`，验证 ControlRig 三档半径、Rig 显示模式、低 LOD 显示模式。

## 2026-05-25 体型参数分组恢复默认记录

用户要求每一个体型参数区块都要有一键恢复默认值按钮。已修：

- 插件版本更新到 `0.1.26`。
- `MH > 体型参数` 子面板中，每个参数分组标题旁新增 `恢复默认` 按钮。
- 每组按钮只恢复本组参数：主控参数恢复为 `1.0`，profile/策略参数恢复到 `PROPORTION_PROFILE_PARAMS` 中的 `default`。
- 恢复默认不会自动重建形态键；长度/粗细主控会立即通过已有驱动生效，骨末端衰减、法向混合、躯干权重等生成参数仍需点 `应用并重建` 才会重新烘焙。
- 新增 `.tmp/analyze_reset_group_defaults.py`，当前 `.tmp/reset_group_defaults_metrics.json` 显示 11 个分组全部通过，`failures: []`。

## 2026-05-25 躯干高度上肢跟随修正记录

用户指出 `躯干高度` 拉高时肩和头被拉上去，但肩以下的手臂没有整体跟随，导致肩臂撕裂；同时躯干高度的腰/胸/胯权重和区块平滑看起来没有效果。已修：

- 插件版本更新到 `0.1.27`。
- `clavicle/upperarm/lowerarm/hand/wrist/metacarpal/thumb/index/middle/ring/pinky` 这整条上肢链现在在 `躯干高度` shape key 中刚性继承躯干顶部位移，不再按顶点自身高度衰减。
- 下肢仍不参与躯干高度，避免拉高躯干时腿脚被带动。
- `躯干高度` 策略参数 tooltip 已补充：腰权重、胸权重、胯权重、区块平滑是生成参数，修改后需要点 `应用并重建` 才会重新烘焙 shape key。
- `README_MHARP_Proportion` 也补充了上肢链跟随和策略参数需重建的说明。
- 新增 `.tmp/analyze_torso_height_upper_follow.py`，当前 `.tmp/torso_height_upper_follow_metrics.json` 显示上肢链统一继承顶部位移、下肢不移动，且策略参数改值后重建有可测差异，`failures: []`。

## 2026-05-25 长度关节末端连续性修正记录

用户接受“关节末端连续性”方案：长度形变中，主段顶点靠近子关节时不应再被 skin weight 打折，否则父段末端顶点只走到约 `0.65-0.91`，而 downstream 子链刚性走到 `1.0`，极限拉长时会在肘/膝/腕/踝折叠。已修：

- 插件版本更新到 `0.1.28`。
- 新增 `length_terminal_weight_factor()`：长度主段仍使用 skin weight 过滤区域，但在靠近子关节的末端区间把权重平滑推到 `1.0`。
- 保留 downstream 子链刚性继承父段末端 offset 的策略。
- `README_MHARP_Proportion` 补充说明：长度主段靠近子关节时会抹平 skin weight 打折，减少极限拉长时的关节折叠。
- 新增 `.tmp/analyze_length_endpoint_continuity.py`，当前 `.tmp/length_endpoint_continuity_metrics.json` 显示上臂/小臂/大腿/小腿长度的末端主段 ratio 均约 `0.992-1.0`，downstream 仍约 `1.0`，`failures: []`。

## 2026-05-25 ControlRig 左右镜像状态修正记录

用户指出左侧手柄映射到右侧时会炸，要求它只镜像左右一对一手柄状态，不要动顶点或其他数据本身。已修：

- 插件版本更新到 `0.1.29`。
- 旧镜像逻辑按 `bpy.data.objects` 任意顺序直接写目标 `matrix_world`；如果先写子手柄、后写父手柄，子手柄会被父级再次带飞。
- 新增 `mirror_control_states()`：先快照所有源侧手柄的镜像目标世界矩阵，再按目标控制层级从父到子应用对象 transform。
- 镜像 operator 描述已改为明确只修改 ControlRig 手柄对象姿态状态，不修改顶点、mesh 数据或形态键。
- 新增 `.tmp/analyze_control_mirror_state_only.py`，当前 `.tmp/control_mirror_state_only_metrics.json` 显示 166 对手柄镜像后世界矩阵误差约 `4e-7`，目标 mesh 顶点/shape key 数据未变化，`failures: []`。

## 2026-05-25 参数生效方式动态提示记录

用户要求在体型参数面板中说清楚：哪些参数改了之后需要 `应用并重建`，哪些参数影响 `同步ControlRig体型外观`，并希望提示是动态的。已修：

- 插件版本更新到 `0.1.30`。
- `MH > 体型参数` 顶部新增动态 alert：底层策略参数与上次烘焙快照不一致时，会显示需要 `应用并重建`。
- 新增底层策略快照 `mharp_profile_build_snapshot_json`，在 `创建安全体型调节器` / `应用并重建` 完成后记录。
- 每个参数行右侧新增短标签：
  - `实时`：主控值立即通过 driver 生效。
  - `实时 / Rig外观`：长度和躯干高度主控会实时影响 Body，并通过 `MH_同步_` 形态键影响 ControlRig 可见外观。
  - `需重建`：骨末端、法向、权重、平滑等底层策略参数，修改后需要 `应用并重建` 重新烘焙。
- 如果场景里有 ControlRig 但没有任何 `MH_同步_` 形态键，会动态提示 `ControlRig外观同步未生成`，并给出同步按钮。
- 新增 `.tmp/analyze_param_action_guidance.py`，当前 `.tmp/param_action_guidance_metrics.json` 验证分类和脏状态检测均通过，`failures: []`。

## 2026-05-25 分组恢复默认并应用记录

用户指出参数分组的 `恢复默认` 只恢复数值，没有立刻应用。已修：

- 插件版本更新到 `0.1.31`。
- 体型参数分组按钮改名为 `恢复默认并应用`。
- 点击后先恢复本组默认值，再根据本组参数类型自动执行后续动作：
  - 本组包含 `需重建` 参数时，自动调用 `创建安全体型调节器`，重新烘焙 shape key 并同步 ControlRig 外观。
  - 本组只包含 `实时 / Rig外观` 参数时，自动调用 `同步ControlRig体型外观`。
  - 本组只有 `实时` 参数时，恢复数值即生效。
- 新增场景记录 `mharp_last_reset_group_apply`，用于后台验证最近一次分组重置执行了什么应用动作。
- `.tmp/analyze_reset_group_defaults.py` 已更新为在正式样例 blend 上验证 `恢复默认并应用` 会触发重建、清空底层策略脏状态；当前 `.tmp/reset_group_defaults_metrics.json` 显示 `failures: []`。

## 2026-05-25 躯干高度运行时 ControlRig 跟随修正记录

用户继续反馈 `躯干高度` 仍没有带着肘以下一起运动，看起来从小臂肘关节往下没有被带动。已修：

- 插件版本更新到 `0.1.32`。
- 上一版 `0.1.27` 把上肢链顶点直接写进 `躯干高度` shape key；这能让 Body 局部顶点动，但 ControlRig 对象 origin 和约束目标仍不动，用户实际操作时会看到手柄/骨链没有跟着躯干上移。
- 新策略：`躯干高度` 不再直接移动 `clavicle/upperarm/lowerarm/hand/finger` 等上肢顶点；上肢由左右 `CTRL_MH_clavicle_l/r` 对象的 transform driver 继承躯干顶部 world 位移，再通过现有父子层级把 `upperarm -> lowerarm -> hand -> fingers` 整链带上去。
- 同时修掉 transform driver 的隐性自依赖：旧表达式从被驱动对象自己的自定义属性读取 `base/delta`，Blender 里会出现 driver 标记有效但不刷新的情况；现在把 `base/delta` 写成表达式常量，只保留 `身体比例控制["躯干高度"]` 作为外部变量。
- `clear_torso_height_object_drivers()` 会恢复并清理 Face LOD 跟随驱动和 ControlRig 跟随驱动，避免重建后残留。
- 新增 `.tmp/analyze_torso_height_runtime_follow.py`，当前 `.tmp/torso_height_runtime_follow_metrics.json` 显示上肢 shape key 直接位移为 `0`，但 `CTRL_MH_clavicle_l/upperarm_l/lowerarm_l/hand_l/index_01_l` runtime world 位移均约 `0.012418m`，`failures: []`。
- `.tmp/analyze_reset_group_defaults.py` 已在 `0.1.32` 重新跑过，分组 `恢复默认并应用` 仍能触发重建并清空策略脏状态，`failures: []`。
- 本轮源码、zip、handoff 快照已同步到工作区和交接包；Blender 5.1 用户插件目录的安装同步因 Codex 审批/用量限制未能执行，需要下一轮补同步。

## 2026-05-25 内置资源、界面语言与躯干引导点场记录

用户要求补执行上一轮因额度卡住的同步，并继续实现：一键切换界面语言、默认中文；躯干高度腰/胸/胯承重调节强度翻倍；躯干粗细从区块圆盘场改为解剖引导点场；将现有 MetaHuman 资源打包进插件作为无外部路径时的内置默认。已修：

- 插件版本更新到 `0.1.33`。
- 新增 `界面语言` 设置与 `切换界面语言` 按钮，默认 `中文`；主面板和体型参数面板的主要按钮/标签会在中文和英文之间切换。
- 新增 `无外部路径时使用内置MetaHuman` 和 `使用内置MetaHuman` 按钮。`DCCExport目录` 为空或不存在且该开关开启时，自动 fallback 到插件内置 `bundled_metahuman/OutPut/DCCExport`。
- 已把当前导入所需资源复制进插件目录：`bundled_metahuman/OutPut`，包含 `DCCExport/Face/Body`，约 `229.56MB`、`76` 个文件；未打包不参与导入的 `Fullbody`。
- `躯干.高度.胯权重`、`腰权重`、`胸权重` 的编辑强度提升为原来的 `2x`：默认值不变，但偏离默认值的效果在生成曲线里加倍。
- `胸部/腰部/胯部.粗细.法向混合` 默认迁移为 `0.85/0.85/0.90`；旧 blend 中如果仍是旧默认 `0.16/0.10/0.48`，会自动迁移到新默认。
- 躯干粗细内部改为紧凑各向异性引导点场：胸部两个胸前点并压低侧肋，腰腹使用左右腰侧和腹部前方三点，胯部使用低位前中线/鼠蹊三角区集中点，后方和侧后方基本不动。
- 新增 `.tmp/analyze_language_builtin_torso_guides.py`：验证默认中文/一键切换、内置资源解析、法向默认、承重 2x boost 和胸/腰/胯引导点前后侧分布；当前 `failures: []`。
- 新增 `.tmp/analyze_builtin_import.py`：从空场景、空外部路径直接使用内置资源扫描并导入，Body 高度约 `1.440570946m`，Face/Body 均存在，`failures: []`。
- `.tmp/analyze_torso_height_runtime_follow.py` 和 `.tmp/analyze_reset_group_defaults.py` 已在 `0.1.33` 重新通过。
- Blender 5.1 用户插件目录已补同步到 `0.1.33`，包含 `__init__.py` 和内置 `DCCExport/Face/Body` 资源。

## 2026-05-25 躯干粗细可摆放引导点记录

用户指出躯干粗细的解剖引导点应该像 ControlRig 一样能摆放修正。已修：

- 插件版本更新到 `0.1.34`。
- 新增 `MH_Torso_Width_Guides` 集合和 `GUIDE_MH_*` 引导点对象，共 `9` 个：胸部 3 个、腰腹 3 个、胯部 3 个。
- 主面板新增 `生成/刷新躯干引导点` 和 `重置躯干引导点`。生成会补齐缺失手柄并保留已有位置；重置会把全部引导点放回默认解剖位置。
- 躯干粗细 shape key 生成时，优先读取这些引导点对象的 world location，再转换回 Body local 参与各向异性 RBF/superellipse bump 计算；没有对象时继续使用内置默认位置。
- 引导点目前只控制位置，不新增半径/强度 UI；摆放后需要点 `应用并重建` 重新烘焙体型形态键。
- 新增 `.tmp/analyze_torso_guide_handles.py`，验证能生成 `9` 个引导点、移动 `chest_l_front` 后场函数读到新位置、重置后恢复默认，当前 `failures: []`。
- `.tmp/analyze_language_builtin_torso_guides.py` 已在 `0.1.34` 重新通过，确认默认引导场语义未被手柄读取改动破坏。

## 2026-05-25 躯干粗细臀后引导点与可见性记录

用户指出胯部后面也就是臀部最好也要有引导点，并且这些引导点要能切换可见性。已修：

- 插件版本更新到 `0.1.35`。
- 胯部粗细引导点从 `3` 个扩展到 `5` 个：保留胯前中线和左右前弱辅助点，新增 `臀后左` / `臀后右` 两个后侧引导点。
- 默认臀后点放在真实后侧 pelvis 顶点范围，方向为向后，强度低于胯前主点；当前分布约为胯前 mean `0.49`、臀后 mean `0.20`，即后侧有支撑但不反客为主。
- 主面板新增 `隐藏引导点` / `显示引导点`，只改变 `GUIDE_MH_*` 引导点对象可见性，不改 mesh、shape key 或已烘焙体型。
- `.tmp/analyze_torso_guide_handles.py` 已更新为验证 `11` 个引导点、臀后点存在、移动/重置和隐藏/显示，当前 `failures: []`。
- `.tmp/analyze_language_builtin_torso_guides.py` 已更新为验证胯部“前方主导 + 臀后受控支撑”的新语义，当前 `failures: []`。
- 本轮源码快照、插件 zip、交接包 zip 和 Blender 5.1 用户插件目录 `__init__.py` 已同步到 `0.1.35`；源码与已安装文件 SHA256 均为 `D748B6A9C8A09B82B1CA562966554ADD88B92CA13994FE858A902E013DEF955F`。

## 2026-05-25 安全固化当前体型副本记录

用户要求先做安全版固化：让当前体型进入编辑模式也是真实形状，但不要直接破坏原始可调角色。已修：

- 插件版本更新到 `0.1.36`。
- 主面板新增 `固化当前体型副本`。
- 新增 `MH_Baked_Proportion` 集合；点击按钮会复制 `MH_Body_LOD0` 和 `MH_Face_LOD0` 的当前 evaluated 可见结果为静态网格。
- 固化副本无 shape key、无 driver、无 modifier、无父级；原始 Body/Face、体型参数、shape keys、ControlRig 不会被替换或删除。
- 这个安全版本质是“当前可见快照”，因此如果用户将来摆了姿势，它会把当前姿势也固化进副本；后续如要“只固化体型不固化姿势”，需要再做进阶版。
- 新增 `.tmp/analyze_static_bake_copy.py`：把多项体型参数调离默认值后固化副本，并逐顶点比较源 Body evaluated 结果和副本网格；当前 `max_body_world_error=0.0`，副本 shape key 数为 `0`，源 Body shape key 数保持 `13`，`failures: []`。
- 新增 `.tmp/render_static_bake_visual_check.py`：生成临时对比渲染 `.tmp/static_bake_visual_check.png`；已按用户本轮要求做目视检查，源可调结果与固化静态副本轮廓一致，未见可视漂移。
- 本轮源码快照、插件 zip、交接包 zip 和 Blender 5.1 用户插件目录 `__init__.py` 已同步到 `0.1.36`；源码与已安装文件 SHA256 均为 `5A17C3570B689A3C09CEF654B6A0CEBF363A12D7ABA81684C34F421E6C74F013`。

## 2026-05-25 高级固化新骨架副本记录

用户要求继续做高级版固化：不仅得到真实网格，也要让骨架 rest pose 承认当前长度/躯干高度比例。已修：

- 插件版本更新到 `0.1.37`。
- 主面板新增 `固化为新骨架副本`，和安全静态按钮分开。
- 新增 `MH_Advanced_Baked_Proportion` 集合；点击后会生成：
  - 新身体骨架 `MH_Advanced_MH_Body_Root_*`，无旧 ControlRig 约束，rest pose 按当前 `上臂长度/小臂长度/大腿长度/小腿长度/躯干高度` 调整。
  - 新 `MH_Advanced_MH_Body_LOD0_*`，顶点为当前 evaluated 体型，保留源 Body 的顶点组，并添加一个指向新骨架的 Armature modifier。
  - 新 `MH_Advanced_MH_Face_LOD0_*` 静态副本，用于保持当前头脸位置；当前版本没有重建完整 FaceRig。
- 胸/腰/胯粗细等纯表面体积参数只固化到网格，不移动骨骼；这是有意的，避免让骨头跟随脂肪/体块厚度乱跑。
- 新增 `.tmp/analyze_advanced_bake_copy.py`：把长度、躯干高度和粗细参数调离默认后生成高级副本；当前结果为 Body 数据误差 `0.0`、rest evaluated 误差约 `2.47e-7`、复制顶点组 `285` 个、Body 有 `ARMATURE` modifier、移动骨骼 `330` 个、pose 约束 `0`、旋转新小臂骨后 Body 有可测变形，`failures: []`。
- 新增 `.tmp/render_advanced_bake_visual_check.py`：生成 `.tmp/advanced_bake_visual_check.png`；已按用户要求目视检查，源可调结果和高级固化副本轮廓一致，未见可视漂移。
- 本轮源码快照、插件 zip、交接包 zip 和 Blender 5.1 用户插件目录 `__init__.py` 已同步到 `0.1.37`；源码与已安装文件 SHA256 均为 `09EE6F1DE74B93A7B6405769D3FDBE8C6327042A53B664F88FCA9DE5B9CB6F3F`。

## 2026-05-25 体型工具 UI 语义简化记录

用户指出主面板的 `同步ControlRig体型外观 / 固化当前体型副本 / 固化为新骨架副本` 和体型参数面板的图例已经难以理解。已修：

- 插件版本更新到 `0.1.38`。
- 主面板把相关按钮分成三块：
  - `体型生成与同步`：`应用体型` / `刷新Rig外观`。
  - `固化副本`：`静态网格副本` / `新骨架副本`。
  - `躯干粗细引导点`：生成、重置、显示、隐藏引导点。
- 体型参数面板去掉旧的三行图例，改成更短的状态提示：
  - `体型已应用`
  - `底层策略已改：点“应用体型”`
  - `Rig外观未同步：点“刷新Rig外观”`
- 按钮语义现在约定：
  - `应用体型`：重建 Body shape keys，应用骨末端/法向/权重/平滑等底层策略。
  - `刷新Rig外观`：只让 ControlRig 手柄显示和跟随驱动匹配当前体型。
  - `静态网格副本`：只生成可编辑静态网格。
  - `新骨架副本`：生成新 rest 骨架和可继续摆姿势的新 Body。
- `.tmp/analyze_param_action_guidance.py`、`.tmp/analyze_static_bake_copy.py`、`.tmp/analyze_advanced_bake_copy.py` 已在 `0.1.38` 通过。
- 本轮源码快照、插件 zip、交接包 zip 和 Blender 5.1 用户插件目录 `__init__.py` 已同步到 `0.1.38`；源码与已安装文件 SHA256 均为 `D597B173C9BC5794731FC832789BFF5E1F9AC64693148EB9EC51C1B72B27D2A8`。

## 2026-05-25 应用体型与Rig同步合并记录

用户指出 `应用体型` 和 `刷新Rig外观` 不应作为两个正常工作流按钮分开，因为没有实际使用场景会希望体型变了但 Rig 不跟。已修：

- 插件版本更新到 `0.1.39`。
- 主面板和体型参数面板只保留一个正常操作按钮：`应用体型并同步Rig`。
- 单独的 `刷新Rig外观` operator 仍保留为内部修复接口，但不再作为主工作流按钮展示。
- 参数行右侧标签进一步简化：主控参数统一显示 `实时`，底层策略参数显示 `需应用`。
- `静态网格副本` 和 `新骨架副本` 执行前会自动调用内部 `ensure_proportion_applied_and_rig_synced()`，如果底层策略未应用或 Rig 外观同步缺失，会先补应用和同步，再固化副本。
- `.tmp/analyze_param_action_guidance.py`、`.tmp/analyze_static_bake_copy.py`、`.tmp/analyze_advanced_bake_copy.py` 已在 `0.1.39` 通过；固化测试确认自动应用后仍能保持 Body 数据误差 `0.0`，高级副本 rest evaluated 误差约 `2.47e-7`。
- 本轮源码快照、插件 zip、交接包 zip 和 Blender 5.1 用户插件目录 `__init__.py` 已同步到 `0.1.39`；源码与已安装文件 SHA256 均为 `64BA9FABDB8584D1A0AACBA90DC6C1714A3EF79D00133814EDCC8B637B131C27`，插件 zip SHA256 为 `A665643E75EE6E3093DBBA2FF93AED71262DCBF4C9516623EFC33A04C133C221`。

## 2026-05-25 ControlRig 名称与对称引导点记录

用户要求插件切换语言时，ControlRig 手柄也同步切换中英文显示名；躯干引导点不要左右都可编辑，而是左侧实控、右侧实时虚影镜像，中线点锁在 pelvis 的 YZ 面，并在 3D 视口显示短解剖文字。已修：

- 插件版本更新到 `0.1.40`。
- ControlRig 对象保留 `mharp_target_bone` 作为底层骨骼 ID；对象显示名随界面语言切换为中文 `控制_MH_*` 或英文 `CTRL_MH_*`。镜像、体型同步、显示/粗细逻辑不再依赖对象英文名。
- 躯干粗细引导点扩展为 `12` 个手柄和 `12` 个文字标签；右侧胸/腰/胯/臀点为不可选择虚影，通过驱动实时镜像左侧点；中线点锁定 X 轴到 pelvis 对称平面。
- 3D 视口文字标签包括 `乳头`、`肚脐眼`、`臀顶`、`肛门` 等解剖短语；切换英文界面时也会切换为英文标签。
- `.tmp/analyze_torso_guide_handles.py`、`.tmp/analyze_language_builtin_torso_guides.py`、`.tmp/analyze_control_mirror_state_only.py`、`.tmp/analyze_param_action_guidance.py` 已在 `0.1.40` 通过。
- 本轮源码快照、插件 zip、交接包 zip 和 Blender 5.1 用户插件目录 `__init__.py` 已同步到 `0.1.40`；源码与已安装文件 SHA256 均为 `BA906CECF2C6D04F191791C3B5EF6E189341C64F4367B189ECDAA23C3AE20BCE`，插件 zip SHA256 为 `90600B0DFA5D04E6BA7AD853245017815EA26E98FD72DC0FA71B76CF849B25F3`。

## 当前目标

用户正在做一套 Blender 内 MetaHuman 工作流插件，显示名已改为 `MetaForge`：从 UE 导出的 `DCCExport` 导入 MetaHuman，自动接材质贴图，生成更容易操作的 Control Rig，并生成中文体形调整控制器。

当前用户希望单独开新窗口继续。这个交接包用于让新窗口快速理解已做内容、现有代码位置、已知错误和下一步目标。

## 建议技能

- `diagnose`：当前是 Blender 插件的缩放、体形控制器慢、局部变形错误等问题，应该先建立干净工程复现和量化反馈。
- `handoff`：如果后续再换窗口，继续更新本文件夹或生成新的交接包。

## 关键路径

- 工作区：`C:\Users\Siyuan Ouyang\OneDrive\Art\3D\CodexWorkSpace`
- 插件源码：`C:\Users\Siyuan Ouyang\OneDrive\Art\3D\CodexWorkSpace\blender_addons\metahuman_blender_pipeline\__init__.py`
- 插件快照：`C:\Users\Siyuan Ouyang\OneDrive\Art\3D\CodexWorkSpace\handoff_metahuman_pipeline_20260525\artifacts\metahuman_blender_pipeline_snapshot\__init__.py`
- 插件 zip：`C:\Users\Siyuan Ouyang\OneDrive\Art\3D\CodexWorkSpace\blender_addons\metahuman_blender_pipeline.zip`
- UE 单次导出固定入口：`C:\Users\Siyuan Ouyang\OneDrive\CODE\CodexUEWorkSpace\UEProjects\MetaHumanRetopo\OutPut\DCCExport`
- 用户 Blender 工程：`C:\Users\Siyuan Ouyang\OneDrive\Art\3D\Blender\ProJect\GraceSwat`
- 干净样例 blend：`C:\Users\Siyuan Ouyang\OneDrive\Art\3D\CodexWorkSpace\metahuman_pipeline_example_clean.blend`
- Blender：`C:\SiyuanApps\Art\blender.exe`

## 已做成果

1. `metahuman_blender_pipeline` / 显示名 `MetaForge` 插件已经推进到 `0.1.40`。
2. 单位链路已修：默认 `import_scale=1.0`，删除 FBX Empty 前保留子对象世界矩阵，`normalize_metahuman_unit_scale()` 只报告异常，不再缩放根骨架补救。
3. 体型控制器性能已做过一轮清理：一键流程默认跳过体型生成，完整生成在干净后台工程约 `17s` 完成 12 个主控。
4. 长度形变已改为沿主 Control Rig 骨骼轴向的累计位移；下游子链刚性继承父段末端 offset，不再直接按子骨骼节点位置乱拉。
5. 四肢粗细当前是基础径向模式加骨末端衰减；上肢粗细的法向混合已重新激活，且只用于 `上臂粗细` / `小臂粗细`，长度不读法向混合。
6. 体型参数已按用户要求重排：四肢在前、躯干在后；同一部位的长度主控和长度策略放一起，再放粗细主控和粗细策略。所有参数已有 `hint`/tooltip。
7. ControlRig 已增加体型外观同步、三档粗细，以及隐藏/半透明/显示按钮；低 LOD 也有隐藏/半透明/显示按钮。
8. 插件 zip、源码快照、内置 MetaHuman 资源包、正式干净样例 blend 都已放进工作区和交接包；Blender 5.1 用户插件目录也已同步到当前工作版。

## 当前插件状态

插件版本当前为 `0.1.40`。这是工作版，不是稳定发布版，但当前已通过一轮后台数值验证。

最近通过的验证包括：

- `.tmp/clean_metahuman_pipeline_test.py`：完整干净流程通过，正式样例为工作区根目录和 handoff examples 的 `metahuman_pipeline_example_clean.blend`。
- `.tmp/analyze_controlrig_lod_display_controls.py`：ControlRig 三档粗细、Rig 显示模式、低 LOD 显示模式均无失败。
- `.tmp/analyze_reset_group_defaults.py`：体型参数每个分组的一键恢复默认值均无失败。
- `.tmp/analyze_torso_height_runtime_follow.py`：躯干高度拉高时上肢不再靠 Body shape key 直接拉顶点，而是由 ControlRig clavicle transform driver 带动整条手臂对象链。
- `.tmp/analyze_language_builtin_torso_guides.py`：默认中文/语言切换、内置 MetaHuman fallback、躯干粗细解剖引导点场和默认法向验证均无失败。
- `.tmp/analyze_torso_guide_handles.py`：躯干粗细引导点生成、读取移动位置、重置默认位置、隐藏/显示均无失败。
- `.tmp/analyze_static_bake_copy.py`：安全固化当前体型副本，确认副本网格和源 evaluated 结果逐顶点一致，且原始可调角色未被破坏。
- `.tmp/analyze_advanced_bake_copy.py`：高级固化新骨架副本，确认副本网格和源 evaluated 结果一致、新 Body 绑定到新 rest 骨架、复制顶点组且可由新骨架姿势驱动。
- `.tmp/analyze_builtin_import.py`：空场景无外部路径时可直接从内置资源扫描并导入 Face/Body，Body 高度保持约 `1.44m`。
- `.tmp/analyze_length_endpoint_continuity.py`：四肢长度在子关节末端的主段顶点和 downstream 子链 offset 连续。
- `.tmp/analyze_control_mirror_state_only.py`：ControlRig 左右镜像只改对象姿态，不改 mesh 顶点/shape key 数据。
- `.tmp/analyze_param_action_guidance.py`：体型参数生效方式标签、底层策略脏状态、烘焙快照检测均无失败。
- `.tmp/analyze_reset_group_defaults.py`：分组 `恢复默认并应用` 会恢复默认值、触发必要重建，并清空底层策略脏状态。
- `.tmp/analyze_controlrig_proportion_visual_sync.py`：ControlRig 外观同步长度和躯干高度均无失败。
- `.tmp/analyze_parameter_limits.py`：参数上限、命名、tooltip/hint 均无失败。
- `.tmp/analyze_upper_limb_normal_mix_response.py`：上肢粗细法向混合有效，长度无 normal mix。
- `.tmp/analyze_lod_visibility.py`：低 LOD 默认只用小眼睛隐藏，点开可显示。

环境风险：

- C 盘空间在上一轮末尾只剩约 `0.12GB`，Blender 保存失败会表现成迷惑性的 `Error: No error` / `No such file or directory`。继续跑保存类脚本前先检查磁盘空间。
- `.tmp\clean_metahuman_pipeline_test.blend` 已为释放空间删除；正式样例在 `metahuman_pipeline_example_clean.blend` 和 handoff `examples` 里。

## 用户近期反馈

按时间靠近当前状态的反馈：

- 不要再主动目视检查，用户自己看。
- 插件要顺手安装并激活，不能只改源码。
- 参数要集中分组，并统一使用“骨末端衰减”命名。
- 参数需要 hint/tooltip，说明干嘛的、怎么用。
- ControlRig 要随体型外观同步。
- ControlRig 需要三档粗细，以及隐藏/半透明/显示；低 LOD 也一样。
- 当前窗口变卡，用户要求准备 handoff 并给新窗口交接提示词。

## 下一步建议顺序

1. 新窗口先读取本交接包，不要重新从旧结论推演。
2. 先确认磁盘空间，再决定是否运行 Blender 保存类验证；若空间仍很低，优先只做源码/文档/轻量分析。
3. 如用户继续测试反馈，优先围绕当前 `0.1.40` 工作版调：高级固化副本、安全固化副本、躯干粗细可摆放引导点、ControlRig 跟随/粗细档位、体型同步、LOD 显示、体型参数语义和内置资源默认流程。
4. 需要验证时优先跑 `.tmp/analyze_*.py` 数值脚本；除非用户要求，不做目视截图。
5. 不要在 `GraceSwat` 用户工程里试错；必须动用户工程前先说明目的，并尽量基于已有正式样例复现。

## 不要做的事

- 不要直接覆盖用户已经打开并修改过的工程。
- 不要再把 AutoRigPro 当作运行依赖。
- 不要用缩放根骨架的方式修单位，除非已经证明后续 Control Rig、父级、驱动和 shape key 全部不会再受影响。
- 不要把低 LOD 用 `hide_viewport=True` / `hide_render=True` 做硬隐藏；用户要能点开小眼睛直接看见。
- 不要在长度形变里直接修改子链交界处的位置；下游子链应该由父段长度变化整体推出。
- 不要主动目视检查或截图，除非用户重新要求。

## 新窗口启动提示

可以把下面这段直接发给新窗口：

```text
读取并遵守这个交接文档：
C:\Users\Siyuan Ouyang\OneDrive\Art\3D\CodexWorkSpace\handoff_metahuman_pipeline_20260525\docs\HANDOFF.md

继续接手 MetaForge / metahuman_blender_pipeline。当前源码/zip/交接快照约为 0.1.40，正式样例 blend 和插件内置 MetaHuman 资源包都已准备好；Blender 5.1 用户插件目录也已同步到当前版本。每做完一个可用版本后，按用户要求自动打开 Blender。先不要碰用户 GraceSwat 工程；只有用户明确要求时才做目视检查。若继续验证，优先跑 handoff 文档列出的后台 analyze 脚本，并先检查 C 盘空间。下一步主要等用户基于当前版本的实际反馈，围绕高级固化副本、安全固化副本、躯干粗细可摆放引导点、ControlRig 跟随/粗细/显示、LOD 显示、体型同步、内置资源默认流程和参数语义继续微调。
```
