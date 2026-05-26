# Test And Debug Index

本轮新增/更新脚本：

- `.tmp/trace_unit_chain.py`：逐步追踪 raw import、LOD 重命名、重挂父级、Face 挂 Body、单位检测。用于定位删除 FBX Empty 后爆比例的根因。
- `.tmp/test_full_pipeline_default_skip.py`：验证一键流程默认跳过体型控制器，只生成导入/贴图/Control Rig。
- `.tmp/clean_metahuman_pipeline_test.py`：完整导入、Control Rig、体型驱动语义验证，并保存干净测试 blend；本次为释放磁盘空间删除了 `.tmp` 临时 blend，正式样例在工作区根目录。
- `.tmp/render_controlrig_views.py`：渲染 Control Rig 正面/侧面/四分之三视图，并输出手柄尺寸、长度方向和躯干粗细隔离指标。
- `.tmp/probe_length_axis.py`：验证长度形态键 delta 与主 Control Rig 控制器轴向是否对齐。
- `.tmp/analyze_proportion_curves.py`：纯数值分析长度/粗细曲线、躯干高度区块和 Face 跟随驱动，不做截图。
- `.tmp/analyze_length_chain_propagation.py`：验证长度形态键是否把 downstream 骨链作为父段末端 offset 的刚性继承者推出去，例如 `大腿长度` 推动 `calf/foot/ball`，并检查长度段满足累计位移曲线。
- `.tmp/analyze_parameter_limits.py`：验证 dashboard 自定义属性 UI 上限和 shape key slider 上限是否已按要求翻倍；同时检查 profile 参数使用新命名、旧别名没有残留，并检查每个参数 tooltip/hint 都说明调大/调小行为。
- `.tmp/analyze_lod_visibility.py`：验证导入后和生成 Control Rig 后，Face/Body 只有 LOD0 可见，LOD0 以外网格默认只用 Outliner 小眼睛隐藏；并模拟重新打开小眼睛后低 LOD 可以直接显示。
- `.tmp/analyze_length_torso_leak.py`：验证 `上臂长度` / `大腿长度` 不移动主权重不属于对应肢体链的胸、躯干、骨盆等顶点。
- `.tmp/analyze_limb_width_basic_coverage.py`：验证四肢粗细基础模式在当前段主权重点内仍有有效响应，并且不移动非当前段主权重点；末端衰减接回后不再要求端点顶点全部发生位移。
- `.tmp/analyze_limb_width_endpoint_fade.py`：验证四肢粗细末端衰减；中段归一化效果接近 `1.0`，起端/末端显著低于中段。
- `.tmp/debug_forearm_width_lower_limb_leak.py`：验证 `MH_小臂粗细` 是否真的移动下肢主权重点；当前结果是 `moved_lower_count=0`，只移动 `lowerarm` 段。
- `.tmp/analyze_edge_falloff_param_response.py`：验证 `骨末端衰减` 调整后重新烘焙 shape key 是否产生可测差异，并验证旧失效法向混合属性已迁移到有效的 `上肢.粗细.法向混合`。
- `.tmp/analyze_upper_limb_normal_mix_response.py`：验证上肢粗细法向混合重新激活后，`上臂粗细/小臂粗细` 会从径向方向转向法向方向，并确认长度参数没有法向混合。
- `.tmp/analyze_controlrig_proportion_visual_sync.py`：验证体型参数改变后 ControlRig 可见 mesh 外观会跟随长度和躯干高度变化，同时存在 `MH_同步_` 形态键。
- `.tmp/analyze_controlrig_lod_display_controls.py`：验证 ControlRig 粗细三档、ControlRig 隐藏/半透明/显示、低 LOD 隐藏/半透明/显示；同时检查低 LOD 隐藏仍可用小眼睛直接重新打开。
- `.tmp/analyze_reset_group_defaults.py`：验证 `体型参数` 面板里参数分组的 `恢复默认并应用` 会恢复本组参数、触发必要重建/同步，并清空底层策略脏状态。
- `.tmp/analyze_torso_height_upper_follow.py`：旧策略验证脚本，曾验证 `0.1.27` 中上肢链直接写进 `躯干高度` Body shape key；`0.1.32` 起已被 runtime ControlRig 跟随策略取代。
- `.tmp/analyze_torso_height_runtime_follow.py`：验证 `躯干高度` 拉高时上肢不再由 Body shape key 直接移动顶点，而是由 ControlRig clavicle transform driver 带动 upperarm/lowerarm/hand/fingers 对象链。
- `.tmp/debug_torso_height_control_follow.py`：临时探针，输出躯干高度跟随 driver、父子链、运行时 world 位移，用于排查 driver 自依赖与 depsgraph 刷新问题。
- `.tmp/analyze_language_builtin_torso_guides.py`：验证界面默认中文和一键切换、ControlRig 对象显示名随语言切换、躯干引导点文字标签随语言切换、无外部路径时内置 MetaHuman fallback、躯干高度权重 2x boost、胸/腰/胯粗细解剖引导点场分布；`0.1.40` 起覆盖中英文 Rig 名称与 3D 标签。
- `.tmp/analyze_builtin_import.py`：从空场景注册插件，DCCExport 目录留空，直接使用内置资源扫描并导入 Face/Body，验证米制高度。
- `.tmp/analyze_torso_guide_handles.py`：验证躯干粗细引导点生成、左侧实控移动后被 shape 生成场读取、右侧虚影实时镜像、中线点锁定 pelvis YZ 面、3D 文字标签生成，并验证引导点隐藏/显示切换。
- `.tmp/analyze_static_bake_copy.py`：验证 `静态网格副本` 生成的 Body/Face LOD0 静态副本不依赖 shape key/driver/modifier/parent；`0.1.39` 起同时验证固化前会自动应用体型并同步 Rig，再逐顶点比较源 Body evaluated 可见结果和固化副本网格。
- `.tmp/render_static_bake_visual_check.py`：生成安全固化副本的临时目视对比渲染；按用户明确要求用于人工检查，不作为默认无请求截图流程。
- `.tmp/analyze_advanced_bake_copy.py`：验证 `新骨架副本` 生成的新身体骨架、新 Body/Face LOD0；`0.1.39` 起同时验证固化前会自动应用体型并同步 Rig；检查新 Body 保留顶点组、绑定到新 Armature、rest evaluated 结果稳定，并用一次小臂 pose 测试确认新骨架能驱动新 Body。
- `.tmp/render_advanced_bake_visual_check.py`：生成高级固化副本的临时目视对比渲染；按用户明确要求用于人工检查。
- `.tmp/analyze_length_endpoint_continuity.py`：验证四肢长度形变在靠近子关节处不会因 skin weight 打折而低于 downstream 刚性继承位移，减少极限拉长时的关节折叠。
- `.tmp/analyze_control_mirror_state_only.py`：验证 ControlRig 左右镜像只修改手柄对象姿态状态，不修改目标 mesh 顶点/shape key 数据，并按层级正确应用最终世界矩阵。
- `.tmp/analyze_param_action_guidance.py`：验证体型参数面板的生效方式标签、底层策略烘焙快照、动态脏状态提示。

本轮关键输出：

- `.tmp/unit_chain_trace.json`：确认 raw import 和保世界矩阵脱父时高度保持 `1.44m`。
- `.tmp/import_scale_1_only.json`：当前只导入结果，高度约 `1.440570946`。
- `.tmp/pipeline_scale_1_test.json`：当前完整手动链路结果，导入、Control Rig、体型后高度都保持约 `1.4405708`。
- `.tmp/full_pipeline_default_skip.json`：默认一键流程约 `6.2s` 完成，未生成 shape key。
- `.tmp/clean_metahuman_pipeline_test.json`：完整流程通过；正式样例为 `metahuman_pipeline_example_clean.blend`，Body 高度约 `1.440570806`，12 个体型驱动均有响应。
- `.tmp/controlrig_visual/controlrig_visual_metrics.json`：当前长度方向点积约 `1.0`，胸/腰/胯粗细的 `limb_changed_ratio` 为 `0.0`。
- `.tmp/controlrig_visual/front.png`、`side.png`、`three_quarter.png`：当前 Control Rig 目视截图。
- `.tmp/proportion_curve_metrics.json`：三次形变数学修正后的数值指标；Face 高度跟随驱动 `8` 个，profile 参数 `15` 个。
- `.tmp/length_chain_propagation_metrics.json`：骨链传播/子链刚性继承数值指标；`thigh_l`、`calf_l`、`upperarm_l`、`lowerarm_l` downstream 的 endpoint ratio 接近 `1.0`，验证均无失败项。
- `.tmp/parameter_limit_metrics.json`：参数上限和 tooltip 验证；主控属性 `max=3.10`、`soft_max=2.4`，profile max 全部翻倍，`骨末端衰减` 新命名生效，旧衰减名称不残留，所有参数 hint 都解释调大/调小行为，shape key `slider_max=1.6`，当前无失败项。
- `.tmp/lod_visibility_metrics.json`：LOD 可见性验证；导入后和 Control Rig 后 `MH_Body_LOD1+`、`MH_Face_LOD1+` 均隐藏，但 `hide_viewport=false`、`hide_render=false`，重新打开小眼睛后可见，当前无失败项。
- `.tmp/length_torso_leak_metrics.json`：长度主权重隔离验证；`MH_上臂长度` 和 `MH_大腿长度` 的 `disallowed_changed_count=0`，当前无失败项。
- `.tmp/limb_width_basic_coverage_metrics.json`：四肢粗细基础模式验证；上臂/小臂/大腿/小腿粗细均有目标区域响应，disallowed changed 均为 `0`。
- `.tmp/limb_width_endpoint_fade_metrics.json`：四肢粗细末端衰减验证；当前中段平均效果约 `0.997`，起端/末端约 `0.06-0.27`，当前无失败项。
- `.tmp/forearm_width_lower_limb_leak.json`：小臂粗细下肢泄漏检查；`moved_by_prefix.lowerarm=2690`，`moved_lower_count=0`，`moved_non_lowerarm_count=0`，当前无失败项。
- `.tmp/edge_falloff_param_response.json`：骨末端衰减生成参数响应验证；`上肢.粗细.骨末端衰减=0.20` 时边缘平均约 `0.94`，`5.00` 时约 `0.25`，旧失效属性不存在，当前无失败项。
- `.tmp/upper_limb_normal_mix_response.json`：上肢粗细法向混合响应验证；`normal_mix=1` 相比 `0` 增加法向对齐、降低径向对齐，`length_normal_keys=[]`，当前无失败项。
- `.tmp/controlrig_proportion_visual_sync.json`：ControlRig 外观同步验证；`上臂长度=2` 时 `CTRL_MH_lowerarm_l` 可见网格移动，`小臂长度=2` 时 `CTRL_MH_hand_l` 移动，`躯干高度=2` 时 `CTRL_MH_head` 移动，当前无失败项。
- `.tmp/controlrig_lod_display_controls.json`：ControlRig/LOD 显示控制验证；ControlRig 粗/中/细半径约 `0.0408/0.0302/0.0212`，ControlRig 半透明 alpha 约 `0.26`，低 LOD 半透明材质为 `MH_LOD_Transparent_Display`，当前无失败项。
- `.tmp/reset_group_defaults_metrics.json`：体型参数分组恢复默认并应用验证；恢复 `上肢长度` 默认值后自动重建，底层策略脏状态清空，当前无失败项。
- `.tmp/torso_height_upper_follow_metrics.json`：旧策略输出，记录 `0.1.27` 时上肢链直接继承顶部位移；`0.1.32` 起以 `.tmp/torso_height_runtime_follow_metrics.json` 为准。
- `.tmp/torso_height_runtime_follow_metrics.json`：躯干高度运行时跟随验证；上肢相关 Body shape key 直接位移为 `0`，ControlRig 的 `clavicle/upperarm/lowerarm/hand/index` world 位移约 `0.012418m`，当前无失败项。
- `.tmp/torso_height_control_follow_debug.json`：ControlRig 跟随 driver 调试输出；确认左右 clavicle driver 表达式只依赖 dashboard ratio，肘以下通过父子链继承 world 位移。
- `.tmp/language_builtin_torso_guides_metrics.json`：语言/内置资源/躯干引导点场验证；默认法向为 `0.85/0.85/0.90`，ControlRig 可在 `控制_MH_*` 与 `CTRL_MH_*` 之间切换，引导标签可在 `肚脐眼`/`navel` 等语言之间切换，内置 Face/Body/Maps 均可解析，胸/腰/胯前后侧分布符合新语义，当前无失败项。
- `.tmp/builtin_import_metrics.json`：内置资源真实导入验证；空外部路径时 `scan/import` 均 `FINISHED`，Body 高度约 `1.440570946m`，当前无失败项。
- `.tmp/torso_guide_handles_metrics.json`：躯干粗细可摆放引导点验证；`12` 个引导点和 `12` 个文字标签已生成，其中右侧点为不可选择虚影、中线点锁在 pelvis YZ 面、胯部包含臀顶与肛门参考；移动/镜像误差约 `1.5e-5` local units，重置误差 `0`，隐藏/显示均覆盖全部引导点和标签，当前无失败项。
- `.tmp/static_bake_copy_metrics.json`：安全固化副本验证；生成 `MH_Baked_Proportion` 集合内的 Body/Face LOD0 静态副本，总顶点 `66991`，固化前自动应用并同步 Rig，Body 副本与源 evaluated 结果 `max_body_world_error=0.0`，副本 shape key 数为 `0`，源 Body shape key 数保持 `13`，当前无失败项。
- `.tmp/static_bake_visual_check.png`：安全固化副本目视检查图；左侧源可调结果、右侧固化静态副本，当前未见可视形状漂移。
- `.tmp/advanced_bake_copy_metrics.json`：高级固化副本验证；生成 `MH_Advanced_Baked_Proportion` 集合内的新骨架和 Body/Face LOD0，新 Body 数据误差 `0.0`、rest evaluated 误差约 `2.47e-7`、复制顶点组 `285` 个、移动骨骼 `330` 个、pose 约束 `0`、新小臂 pose 能驱动 Body，当前无失败项。
- `.tmp/advanced_bake_visual_check.png`：高级固化副本目视检查图；左侧源可调结果、右侧高级固化副本，当前未见可视形状漂移。
- `.tmp/length_endpoint_continuity_metrics.json`：长度关节末端连续性验证；上臂/小臂/大腿/小腿末端主段 ratio 均约 `0.992-1.0`，downstream 仍约 `1.0`，当前无失败项。
- `.tmp/control_mirror_state_only_metrics.json`：ControlRig 左右镜像验证；166 对手柄镜像后矩阵误差约 `4e-7`，目标 mesh 数据不变，当前无失败项。
- `.tmp/param_action_guidance_metrics.json`：参数生效方式验证；`实时`、`实时 / Rig外观`、`需重建` 分类正确，底层策略脏状态可定位到单个参数，当前无失败项。

已有临时脚本多数在：

`C:\Users\Siyuan Ouyang\OneDrive\Art\3D\CodexWorkSpace\.tmp`

有用脚本：

- `measure_fbx_import_scales.py`：直接测 FBX 不同 `global_scale` 的尺寸。
- `measure_fbx_import_order.py`：测 Face/Body 导入顺序是否影响单位。
- `measure_pipeline_stages.py`：测插件导入、Control Rig、体形控制阶段的尺寸。
- `test_import_scale_1_only.py`：只跑插件导入，设置 `import_scale=1.0`。
- `test_pipeline_scale_1.py`：尝试跑完整插件链路，曾超时，不要直接信任。
- `test_root_unit_scale_fix.py`：验证过缩放根骨架可短期修尺寸，但不是可靠方案。
- `test_apply_unit_scale.py`：验证过直接 apply 根骨架缩放会让 Face 爆炸，不建议使用。

建议新窗口先新写一个最小脚本：

1. 清空场景。
2. 加载插件源码。
3. 设置 DCCExport。
4. 只运行导入。
5. `bpy.context.view_layer.update()`。
6. 输出 Body/Face/Armature 的 world bbox、object scale、parent、matrix_world。

稳定后再逐步加 Control Rig 和体形控制器。
