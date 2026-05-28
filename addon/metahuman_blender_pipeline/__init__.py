bl_info = {
    "name": "MetaForge",
    "author": "Codex / Siyuan Ouyang",
    "version": (0, 1, 50),
    "blender": (4, 2, 0),
    "location": "3D View > Sidebar > MetaForge",
    "description": "Forge MetaHuman imports into Blender-ready materials, control rigs, and body-shape tools.",
    "category": "Rigging",
}

import json
import math
import re
import shutil
import time
import traceback
from datetime import datetime
from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

try:
    from bpy_extras import node_shader_utils
except Exception:
    node_shader_utils = None


CONTROL_PREFIX = "CTRL_MH_"
CONTROL_SYNC_SHAPE_PREFIX = "MH_同步_"
CONTROL_COLLECTION = "MH_Control_Rig"
TORSO_GUIDE_COLLECTION = "MH_Torso_Width_Guides"
TORSO_GUIDE_PREFIX = "GUIDE_MH_"
TORSO_GUIDE_LABEL_PREFIX = "LABEL_MH_"
BAKED_PROPORTION_COLLECTION = "MH_Baked_Proportion"
ADVANCED_BAKED_COLLECTION = "MH_Advanced_Baked_Proportion"
SHAPE_COLLECTION = "MH_Proportion_Rig"
DASHBOARD_NAME = "身体比例控制"
PROFILE_BUILD_SNAPSHOT_PROP = "mharp_profile_build_snapshot_json"
DEFORM_HIDDEN_COLLECTION = "MH_Deform_Rigs_Hidden"
COPY_LOCATION_NAME = "MH_ControlRig_CopyLocation"
COPY_ROTATION_NAME = "MH_ControlRig_CopyRotation"
LOD_TRANSPARENT_MATERIAL = "MH_LOD_Transparent_Display"
SIDE_RE = r"_(l|r)$"
TOES = ("bigtoe", "indextoe", "middletoe", "ringtoe", "littletoe")

CONTROL_THICKNESS_LEVELS = {
    "THIN": 0.52,
    "MEDIUM": 0.74,
    "LARGE": 1.0,
}

TORSO_HEIGHT_CONTROL_FOLLOW_ROOTS = ("clavicle_l", "clavicle_r")
BUILTIN_METAHUMAN_RELATIVE_ROOT = Path("bundled_metahuman") / "OutPut"
DEFAULT_INTERFACE_LANGUAGE = "ZH"
TEXTURE_FILE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".tga", ".exr", ".bmp", ".dds")
METAHUMAN_TEXTURE_SPECS = (
    ("head", "MH_Head_Skin", "Head_Basecolor.png", "Head_Normal.png"),
    ("body", "MH_Body_Skin", "Body_Basecolor.png", "Body_Normal.png"),
    ("eye_left", "MH_Eye_Left", "Eyes_Color.png", "Eyes_Normal.png"),
    ("eye_right", "MH_Eye_Right", "Eyes_Color.png", "Eyes_Normal.png"),
    ("teeth", "MH_Teeth", "Teeth_Color.png", "Teeth_Normal.png"),
    ("lashes", "MH_Eyelashes", "Eyelashes_Color.png", None),
)
METAHUMAN_EXPECTED_TEXTURES = tuple(
    dict.fromkeys(
        texture_name
        for _key, _material_name, base_color, normal in METAHUMAN_TEXTURE_SPECS
        for texture_name in (base_color, normal)
        if texture_name
    )
)

UI_TEXT = {
    "ZH": {
        "language_switch": "切换英文",
        "language_name": "界面语言",
        "builtin_toggle": "无外部路径时使用内置MetaHuman",
        "use_builtin": "使用内置MetaHuman",
        "dcc_export_root": "DCCExport目录",
        "character_name": "角色名",
        "armature_name": "身体骨架",
        "body_mesh_name": "身体网格",
        "import_scale": "导入缩放",
        "hide_non_lod0": "用小眼睛隐藏低LOD",
        "make_backup": "操作前备份当前blend",
        "hide_source_armature": "隐藏原骨架，只看手柄",
        "proportion_lod0_only": "只处理LOD0体型",
        "run_proportion_shapes_in_full_pipeline": "一键流程生成体型调节器",
        "control_rig_thickness": "ControlRig粗细",
        "apply_control_rig_thickness": "应用ControlRig粗细",
        "rig_hide": "Rig隐藏",
        "transparent": "半透明",
        "show": "显示",
        "lod_hide": "LOD隐藏",
        "run_full_pipeline": "一键生成MetaForge",
        "scan": "扫描DCCExport",
        "import": "导入MetaHuman并接贴图",
        "repair_textures": "修复MetaHuman贴图索引",
        "bind_selected_clothes": "绑定选中衣服到身体",
        "paint_cloth_weights": "用ControlRig刷衣服权重",
        "apply_pose_as_rest": "应用当前姿势为Rest Pose",
        "build_rig": "生成专用ControlRig",
        "create_shapes": "应用体型并同步Rig",
        "sync_visuals": "刷新Rig外观（修复）",
        "bake_static_copy": "静态网格副本",
        "bake_advanced_copy": "新骨架副本",
        "body_workflow": "体型生成与同步",
        "body_workflow_hint": "重建底层策略，并自动同步Rig外观",
        "bake_workflow": "固化副本",
        "bake_workflow_hint": "静态网格只给编辑；新骨架副本可继续摆姿势",
        "guide_workflow": "躯干粗细引导点",
        "create_torso_guides": "生成/刷新躯干引导点",
        "reset_torso_guides": "重置躯干引导点",
        "hide_torso_guides": "隐藏引导点",
        "show_torso_guides": "显示引导点",
        "mirror_l_to_r": "左到右镜像",
        "mirror_r_to_l": "右到左镜像",
        "status_default": "未扫描",
        "params_panel": "体型参数",
        "build_first": "先生成体型调节器",
        "snapshot_missing": "旧文件缺少体型应用记录：建议应用体型并同步Rig",
        "dirty_params": "{count} 个底层策略已改：需要应用体型并同步Rig",
        "params_clean": "体型和Rig已同步",
        "sync_missing": "Rig外观未同步：应用体型并同步Rig即可修复",
        "apply_rebuild": "应用体型并同步Rig",
        "param_usage_hint": "主控值实时；骨末端/法向/权重/平滑改完点一次应用",
        "reset_apply": "恢复默认并应用",
    },
    "EN": {
        "language_switch": "Switch to Chinese",
        "language_name": "Interface Language",
        "builtin_toggle": "Use bundled MetaHuman when no external path is set",
        "use_builtin": "Use Bundled MetaHuman",
        "dcc_export_root": "DCCExport Folder",
        "character_name": "Character",
        "armature_name": "Body Armature",
        "body_mesh_name": "Body Mesh",
        "import_scale": "Import Scale",
        "hide_non_lod0": "Hide Low LODs",
        "make_backup": "Back Up Blend First",
        "hide_source_armature": "Hide Source Armature",
        "proportion_lod0_only": "Body Shapes LOD0 Only",
        "run_proportion_shapes_in_full_pipeline": "Build Body Shapes in One-Click",
        "control_rig_thickness": "ControlRig Thickness",
        "apply_control_rig_thickness": "Apply ControlRig Thickness",
        "rig_hide": "Hide Rig",
        "transparent": "Transparent",
        "show": "Show",
        "lod_hide": "Hide LODs",
        "run_full_pipeline": "Run MetaForge",
        "scan": "Scan DCCExport",
        "import": "Import MetaHuman + Materials",
        "repair_textures": "Repair MetaHuman Texture Index",
        "bind_selected_clothes": "Bind Selected Clothes to Body",
        "paint_cloth_weights": "Paint Cloth Weights from ControlRig",
        "apply_pose_as_rest": "Apply Current Pose as Rest",
        "build_rig": "Build ControlRig",
        "create_shapes": "Apply Body + Rig",
        "sync_visuals": "Refresh Rig Look (Repair)",
        "bake_static_copy": "Static Mesh Copy",
        "bake_advanced_copy": "New Rig Copy",
        "body_workflow": "Body Build + Sync",
        "body_workflow_hint": "Rebuild body strategy and sync rig look automatically.",
        "bake_workflow": "Bake Copies",
        "bake_workflow_hint": "Static mesh is for editing; new rig copy can still pose.",
        "guide_workflow": "Torso Width Guides",
        "create_torso_guides": "Create/Refresh Torso Guides",
        "reset_torso_guides": "Reset Torso Guides",
        "hide_torso_guides": "Hide Guides",
        "show_torso_guides": "Show Guides",
        "mirror_l_to_r": "Mirror L to R",
        "mirror_r_to_l": "Mirror R to L",
        "status_default": "Not scanned",
        "params_panel": "Body Shape Parameters",
        "build_first": "Build body-shape controls first",
        "snapshot_missing": "Old file has no body bake record: apply body + rig.",
        "dirty_params": "{count} strategy parameters changed: apply body + rig.",
        "params_clean": "Body and rig are synced",
        "sync_missing": "Rig look is missing; Apply Body + Rig repairs it.",
        "apply_rebuild": "Apply Body + Rig",
        "param_usage_hint": "Main sliders are realtime; endpoint/normal/weight/smoothing need one apply.",
        "reset_apply": "Reset + Apply",
    },
}


CONTROL_BONE_ZH_TOKENS = {
    "root": "根",
    "pelvis": "骨盆",
    "spine": "脊柱",
    "neck": "颈",
    "head": "头",
    "clavicle": "锁骨",
    "upperarm": "上臂",
    "lowerarm": "小臂",
    "hand": "手",
    "wrist": "腕",
    "metacarpal": "掌骨",
    "thumb": "拇指",
    "index": "食指",
    "middle": "中指",
    "ring": "无名指",
    "pinky": "小指",
    "thigh": "大腿",
    "calf": "小腿",
    "foot": "脚",
    "ball": "前脚掌",
    "ankle": "踝",
    "toe": "趾",
    "bigtoe": "拇趾",
    "indextoe": "二趾",
    "middletoe": "中趾",
    "ringtoe": "四趾",
    "littletoe": "小趾",
    "twist": "扭转",
    "breast": "胸",
    "facial": "面部",
    "FACIAL": "面部",
    "C": "中",
    "L": "左",
    "R": "右",
}

TORSO_GUIDE_LABELS = {
    "ZH": {
        "chest_l_front": "乳头（左）",
        "chest_r_front": "乳头（右虚影）",
        "chest_back_soft": "胸背中线",
        "waist_l_side": "腰侧（左）",
        "waist_r_side": "腰侧（右虚影）",
        "abdomen_front": "肚脐眼",
        "pelvis_front_center": "鼠蹊三角区",
        "pelvis_l_front_soft": "胯前侧（左）",
        "pelvis_r_front_soft": "胯前侧（右虚影）",
        "pelvis_l_back_glute": "臀顶（左）",
        "pelvis_r_back_glute": "臀顶（右虚影）",
        "pelvis_back_center": "肛门",
    },
    "EN": {
        "chest_l_front": "left nipple",
        "chest_r_front": "right nipple ghost",
        "chest_back_soft": "chest back midline",
        "waist_l_side": "left waist side",
        "waist_r_side": "right waist ghost",
        "abdomen_front": "navel",
        "pelvis_front_center": "inguinal triangle",
        "pelvis_l_front_soft": "left front pelvis",
        "pelvis_r_front_soft": "right front pelvis ghost",
        "pelvis_l_back_glute": "left glute crest",
        "pelvis_r_back_glute": "right glute crest ghost",
        "pelvis_back_center": "anus",
    },
}


PRIMARY_CENTER_BONES = {
    "root",
    "pelvis",
    "spine_01",
    "spine_02",
    "spine_03",
    "spine_04",
    "spine_05",
    "neck_01",
    "neck_02",
    "head",
}

PRIMARY_SIDE_BASES = {
    "clavicle",
    "upperarm",
    "lowerarm",
    "hand",
    "index_metacarpal",
    "middle_metacarpal",
    "ring_metacarpal",
    "pinky_metacarpal",
    "thigh",
    "calf",
    "foot",
    "ball",
    "thumb_01",
    "thumb_02",
    "thumb_03",
    "index_01",
    "index_02",
    "index_03",
    "middle_01",
    "middle_02",
    "middle_03",
    "ring_01",
    "ring_02",
    "ring_03",
    "pinky_01",
    "pinky_02",
    "pinky_03",
    "bigtoe_01",
    "bigtoe_02",
    "indextoe_01",
    "indextoe_02",
    "middletoe_01",
    "middletoe_02",
    "ringtoe_01",
    "ringtoe_02",
    "littletoe_01",
    "littletoe_02",
}


PROPORTION_DEFS = [
    {
        "prop": "上臂长度",
        "kind": "length",
        "bones": ["upperarm_l", "upperarm_r", "upperarm_twist_01_l", "upperarm_twist_01_r", "upperarm_twist_02_l", "upperarm_twist_02_r"],
        "axis_bones": ["upperarm_l", "upperarm_r"],
        "follow_roots": ["lowerarm_l", "lowerarm_r"],
        "driver_strength": 0.20,
        "description": "形态键式上臂局部长度，默认 1.0。",
        "hint": "控制肩到肘这一段的长度；调大上臂变长并把小臂和手一起推出去，调小上臂变短。若肩/肘交界太硬，配合上肢长度的骨末端衰减调整。",
    },
    {
        "prop": "小臂长度",
        "kind": "length",
        "bones": ["lowerarm_l", "lowerarm_r", "lowerarm_twist_01_l", "lowerarm_twist_01_r", "lowerarm_twist_02_l", "lowerarm_twist_02_r"],
        "axis_bones": ["lowerarm_l", "lowerarm_r"],
        "follow_roots": ["hand_l", "hand_r"],
        "driver_strength": 0.20,
        "description": "形态键式小臂局部长度，默认 1.0。",
        "hint": "控制肘到腕这一段的长度；调大小臂变长并把手一起推出去，调小小臂变短。主要用于前臂比例，不应该改变上臂长度。",
    },
    {
        "prop": "上臂粗细",
        "kind": "width",
        "bones": ["upperarm_l", "upperarm_r", "upperarm_twist_01_l", "upperarm_twist_01_r", "upperarm_twist_02_l", "upperarm_twist_02_r"],
        "axis_bones": ["upperarm_l", "upperarm_r"],
        "driver_strength": 0.55,
        "description": "沿骨骼横截面放大/缩小上臂。",
        "hint": "控制上臂粗细；调大上臂变粗，调小上臂变细。只沿上臂骨骼横截面扩张，肩胸边界由上肢粗细的骨末端衰减和法向混合一起控制。",
    },
    {
        "prop": "小臂粗细",
        "kind": "width",
        "bones": ["lowerarm_l", "lowerarm_r", "lowerarm_twist_01_l", "lowerarm_twist_01_r", "lowerarm_twist_02_l", "lowerarm_twist_02_r"],
        "axis_bones": ["lowerarm_l", "lowerarm_r"],
        "driver_strength": 0.55,
        "description": "沿骨骼横截面放大/缩小小臂。",
        "hint": "控制小臂粗细；调大小臂变粗，调小小臂变细。只影响肘到腕附近的前臂体积，肘/腕边界由上肢粗细的骨末端衰减控制。",
    },
    {
        "prop": "大腿长度",
        "kind": "length",
        "bones": ["thigh_l", "thigh_r", "thigh_twist_01_l", "thigh_twist_01_r"],
        "axis_bones": ["thigh_l", "thigh_r"],
        "follow_roots": ["calf_l", "calf_r"],
        "driver_strength": 0.12,
        "description": "形态键式大腿局部长度，默认 1.0。",
        "hint": "控制胯到膝这一段的长度；调大大腿变长并把小腿和脚一起推出去，调小大腿变短。膝盖附近过渡由下肢长度的骨末端衰减控制。",
    },
    {
        "prop": "小腿长度",
        "kind": "length",
        "bones": ["calf_l", "calf_r", "calf_twist_01_l", "calf_twist_01_r", "calf_twist_02_l", "calf_twist_02_r"],
        "axis_bones": ["calf_l", "calf_r"],
        "follow_roots": ["foot_l", "foot_r"],
        "driver_strength": 0.12,
        "description": "形态键式小腿局部长度，默认 1.0。",
        "hint": "控制膝到踝这一段的长度；调大小腿变长并把脚一起推出去，调小小腿变短。主要用于下腿比例，不应该直接改大腿。",
    },
    {
        "prop": "大腿粗细",
        "kind": "width",
        "bones": ["thigh_l", "thigh_r", "thigh_twist_01_l", "thigh_twist_01_r"],
        "axis_bones": ["thigh_l", "thigh_r"],
        "driver_strength": 0.48,
        "description": "沿骨骼横截面放大/缩小大腿。",
        "hint": "控制大腿粗细；调大大腿变粗，调小大腿变细。主要作用在胯到膝之间，胯根和膝盖交界由下肢粗细的骨末端衰减控制。",
    },
    {
        "prop": "小腿粗细",
        "kind": "width",
        "bones": ["calf_l", "calf_r", "calf_twist_01_l", "calf_twist_01_r", "calf_twist_02_l", "calf_twist_02_r"],
        "axis_bones": ["calf_l", "calf_r"],
        "driver_strength": 0.48,
        "description": "沿骨骼横截面放大/缩小小腿。",
        "hint": "控制小腿粗细；调大小腿变粗，调小小腿变细。主要作用在膝到踝之间，膝盖和脚踝交界由下肢粗细的骨末端衰减控制。",
    },
    {
        "prop": "躯干高度",
        "kind": "vertical",
        "bones": ["pelvis", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05"],
        "axis_bones": ["spine_01", "spine_05"],
        "driver_strength": 0.04,
        "description": "形态键式躯干高度，默认 1.0。",
        "hint": "控制躯干整体高度；调大主要拉高腰腹，其次胸腔，并带动颈头过渡；调小则压低躯干。胯部默认几乎不参与，比例分配用胯/腰/胸权重调。",
    },
    {
        "prop": "胸部粗细",
        "kind": "width",
        "bones": ["spine_04", "spine_05"],
        "axis_bones": ["spine_04", "spine_05"],
        "driver_strength": 0.32,
        "description": "胸腔体积，默认主要前后方向更明显。",
        "hint": "控制胸腔体积；调大胸部变厚，默认前后方向变化多、左右变化少，调小则收窄胸腔。适合先调体块，再用胸部法向混合微调表面鼓起方向。",
    },
    {
        "prop": "腰部粗细",
        "kind": "width",
        "bones": ["spine_02", "spine_03"],
        "axis_bones": ["spine_02", "spine_03"],
        "driver_strength": 0.35,
        "description": "腰腹体积，主要作用于中段躯干。",
        "hint": "控制腰腹体积；调大腰部主要左右变宽，前方少量变化、后方几乎不动，调小则收腰。用于中段躯干，不应该带着四肢变形。",
    },
    {
        "prop": "胯部粗细",
        "kind": "width",
        "bones": ["pelvis", "spine_01"],
        "axis_bones": ["pelvis", "spine_01"],
        "driver_strength": 0.35,
        "description": "胯部横向和前后体积。",
        "hint": "控制胯部体积；调大后侧和法向方向变化更多，前方变化很少，调小则收胯。用于骨盆和髋部体块，不应该拉动大腿长度。",
    },
]


PROPORTION_PROFILE_PARAMS = {
    "四肢.长度.骨末端衰减": {
        "default": 0.18,
        "min": 0.02,
        "max": 0.90,
        "description": "长度在骨末端从0过渡到主体效果的范围比例；端点最小值固定为0。",
        "hint": "四肢长度端点保护范围；调大时肩/肘/腕/胯/膝/踝附近更早衰减，交界更稳但主体有效区变短；调小时更多骨段参与长度变化。端点效果固定为0。",
    },
    "上肢.长度.骨末端衰减": {
        "default": 0.55,
        "min": 0.20,
        "max": 5.00,
        "description": "上肢长度靠近骨末端时的衰减曲线指数；小值更接近均匀，大值更集中。",
        "hint": "上肢长度的骨末端衰减曲线；调大时长度变化更集中在骨段中部，肩/肘/腕端更保守；调小时分布更接近均匀。用于上臂/小臂长度。",
    },
    "下肢.长度.骨末端衰减": {
        "default": 0.45,
        "min": 0.20,
        "max": 5.00,
        "description": "下肢长度靠近骨末端时的衰减曲线指数；小值更接近均匀，大值更集中。",
        "hint": "下肢长度的骨末端衰减曲线；调大时长度变化更集中在骨段中部，胯/膝/踝端更保守；调小时分布更接近均匀。用于大腿/小腿长度。",
    },
    "四肢.粗细.骨末端衰减": {
        "default": 0.16,
        "min": 0.02,
        "max": 0.90,
        "description": "四肢粗细在骨末端从0过渡到主体效果的范围比例。",
        "hint": "四肢粗细端点保护范围；调大时关节附近更早衰减，肩/肘/腕/胯/膝/踝交界更稳但变粗区域更短；调小时粗细变化覆盖更长。",
    },
    "上肢.粗细.骨末端衰减": {
        "default": 0.65,
        "min": 0.20,
        "max": 5.00,
        "description": "上肢粗细靠近骨末端时的衰减曲线指数；小值更接近均匀，大值更集中。",
        "hint": "上肢粗细的骨末端衰减曲线；调大时上臂/小臂中段更明显，肩/肘/腕更少受影响；调小时粗细变化更平均。",
    },
    "下肢.粗细.骨末端衰减": {
        "default": 0.55,
        "min": 0.20,
        "max": 5.00,
        "description": "下肢粗细靠近骨末端时的衰减曲线指数；小值更接近均匀，大值更集中。",
        "hint": "下肢粗细的骨末端衰减曲线；调大时大腿/小腿中段更明显，胯/膝/踝更少受影响；调小时粗细变化更平均。",
    },
    "上肢.粗细.法向混合": {
        "default": 0.35,
        "min": 0.0,
        "max": 1.0,
        "description": "上肢粗细方向，0为骨骼横截面径向，1为顶点法向投影；只作用于上臂/小臂粗细。",
        "hint": "上肢粗细的推出方向混合，只作用于上臂/小臂粗细；0=沿骨骼横截面径向变粗，1=更贴近顶点法向鼓起。调大更顺表面，调小更像圆柱横截面缩放；不影响任何长度参数。",
    },
    "躯干.粗细.边界平滑": {
        "default": 0.34,
        "min": 0.10,
        "max": 1.60,
        "description": "胸/腰/胯粗细区块边界的空间过渡宽度。",
        "hint": "胸/腰/胯粗细区块之间的边界过渡；调大时区块融合更宽更软，调小时区块更独立但可能更硬。用于躯干粗细，不影响四肢。",
    },
    "胸部.粗细.法向混合": {
        "default": 0.85,
        "min": 0.0,
        "max": 2.0,
        "description": "胸部粗细方向的法向混合。",
        "hint": "胸部粗细的法向推出比例；默认以顶点法向为主，语义引导只负责把效果集中到胸前并压低侧肋。调大更顺表面，调小更像内部引导方向推出。",
    },
    "腰部.粗细.法向混合": {
        "default": 0.85,
        "min": 0.0,
        "max": 2.0,
        "description": "腰部粗细方向的法向混合。",
        "hint": "腰腹粗细的法向推出比例；默认以顶点法向为主，语义引导把效果集中到左右腰侧和腹部前方，背后接近不动。调大更顺表面，调小更受侧向/前向引导。",
    },
    "胯部.粗细.法向混合": {
        "default": 0.90,
        "min": 0.0,
        "max": 2.0,
        "description": "胯部粗细方向的法向混合。",
        "hint": "胯部粗细的法向推出比例；默认以顶点法向为主，语义引导把效果集中到低位前中线和鼠蹊三角区，后方和侧后方基本不动。调大更顺表面。",
    },
    "躯干.高度.胯权重": {
        "default": 0.04,
        "min": 0.0,
        "max": 2.0,
        "description": "躯干高度由胯部区块贡献的比例，默认几乎不参与。",
        "hint": "躯干高度中胯部参与比例；调大时骨盆附近也会参与拉高，调小时胯部更稳定。通常保持很低，只在需要胯根一起过渡时少量增加。修改后点应用并重建生效。",
    },
    "躯干.高度.腰权重": {
        "default": 0.74,
        "min": 0.0,
        "max": 2.0,
        "description": "躯干高度由腰腹区块贡献的比例，默认主要贡献。",
        "hint": "躯干高度中腰腹参与比例；调大时腰腹承担更多身高变化，调小时躯干高度更多交给胸部或胯部。通常这是躯干高度的主控制。修改后点应用并重建生效。",
    },
    "躯干.高度.胸权重": {
        "default": 0.22,
        "min": 0.0,
        "max": 2.0,
        "description": "躯干高度由胸腔区块贡献的比例，默认少量贡献。",
        "hint": "躯干高度中胸腔参与比例；调大时胸腔和颈头过渡更跟随躯干高度，调小时胸部更稳定。通常少量参与，避免胸口被过度拉长。修改后点应用并重建生效。",
    },
    "躯干.高度.区块平滑": {
        "default": 0.42,
        "min": 0.10,
        "max": 1.80,
        "description": "躯干高度胸/腰/胯区块之间的过渡平滑度。",
        "hint": "躯干高度在胯/腰/胸之间的过渡宽度；调大时头颈胸腰过渡更软，调小时区块更分明。用于解决躯干高度变化时的断层感。修改后点应用并重建生效。",
    },
}


PROFILE_PARAM_ALIASES = {
    "四肢.长度.骨末端衰减": ("四肢.长度.骨骼末端效果衰减范围", "四肢.长度.端点收束"),
    "上肢.长度.骨末端衰减": ("上肢.长度.边缘衰减程度", "上肢.长度.不均匀度"),
    "下肢.长度.骨末端衰减": ("下肢.长度.边缘衰减程度", "下肢.长度.不均匀度"),
    "四肢.粗细.骨末端衰减": ("四肢.粗细.骨骼末端效果衰减范围", "四肢.粗细.端点收束"),
    "上肢.粗细.骨末端衰减": ("上肢.粗细.边缘衰减程度", "上肢.粗细.不均匀度"),
    "下肢.粗细.骨末端衰减": ("下肢.粗细.边缘衰减程度", "下肢.粗细.不均匀度"),
    "上肢.粗细.法向混合": ("四肢.粗细.X法向混合", "四肢.粗细.法向混合", "X法向混合", "法向混合"),
}

PROFILE_PARAM_DEFAULT_MIGRATIONS = {
    "胸部.粗细.法向混合": (0.16, 0.85),
    "腰部.粗细.法向混合": (0.10, 0.85),
    "胯部.粗细.法向混合": (0.48, 0.90),
}


PROPORTION_PARAM_GROUPS = [
    (
        "四肢长度通用",
        [
            "四肢.长度.骨末端衰减",
        ],
    ),
    (
        "上肢长度",
        [
            "上臂长度",
            "小臂长度",
            "上肢.长度.骨末端衰减",
        ],
    ),
    (
        "上肢粗细",
        [
            "上臂粗细",
            "小臂粗细",
            "上肢.粗细.骨末端衰减",
            "上肢.粗细.法向混合",
        ],
    ),
    (
        "下肢长度",
        [
            "大腿长度",
            "小腿长度",
            "下肢.长度.骨末端衰减",
        ],
    ),
    (
        "下肢粗细",
        [
            "大腿粗细",
            "小腿粗细",
            "下肢.粗细.骨末端衰减",
        ],
    ),
    (
        "四肢粗细通用",
        [
            "四肢.粗细.骨末端衰减",
        ],
    ),
    (
        "躯干高度",
        [
            "躯干高度",
            "躯干.高度.腰权重",
            "躯干.高度.胸权重",
            "躯干.高度.胯权重",
            "躯干.高度.区块平滑",
        ],
    ),
    (
        "胸部粗细",
        [
            "胸部粗细",
            "胸部.粗细.法向混合",
        ],
    ),
    (
        "腰部粗细",
        [
            "腰部粗细",
            "腰部.粗细.法向混合",
        ],
    ),
    (
        "胯部粗细",
        [
            "胯部粗细",
            "胯部.粗细.法向混合",
        ],
    ),
    (
        "躯干粗细通用",
        [
            "躯干.粗细.边界平滑",
        ],
    ),
]


INACTIVE_PROPORTION_PARAMS = set()


def proportion_param_default(prop_name):
    if prop_name in PROPORTION_PROFILE_PARAMS:
        return PROPORTION_PROFILE_PARAMS[prop_name]["default"]
    if any(item["prop"] == prop_name for item in PROPORTION_DEFS):
        return 1.0
    return None


def proportion_group_props(group_name):
    for name, prop_names in PROPORTION_PARAM_GROUPS:
        if name == group_name:
            return list(prop_names)
    return []


def proportion_def_for_prop(prop_name):
    for item in PROPORTION_DEFS:
        if item["prop"] == prop_name:
            return item
    return None


def param_action_kind(prop_name):
    if prop_name in PROPORTION_PROFILE_PARAMS:
        return "REBUILD"
    item = proportion_def_for_prop(prop_name)
    if item and item["kind"] in {"length", "vertical"}:
        return "REALTIME_RIG"
    if item:
        return "REALTIME"
    return "UNKNOWN"


def param_action_label(prop_name):
    kind = param_action_kind(prop_name)
    if kind == "REBUILD":
        return "需应用"
    if kind == "REALTIME_RIG":
        return "实时"
    if kind == "REALTIME":
        return "实时"
    return ""


def has_control_visual_sync_shape_keys():
    for obj in control_objects():
        if obj.type != "MESH" or not obj.data.shape_keys:
            continue
        for key in obj.data.shape_keys.key_blocks:
            if key.name.startswith(CONTROL_SYNC_SHAPE_PREFIX):
                return True
    return False


def current_profile_param_snapshot(dashboard):
    return {name: profile_param(dashboard, name) for name in PROPORTION_PROFILE_PARAMS}


def record_profile_build_snapshot(dashboard):
    dashboard[PROFILE_BUILD_SNAPSHOT_PROP] = json.dumps(current_profile_param_snapshot(dashboard), ensure_ascii=False)


def dirty_profile_params(dashboard):
    raw = dashboard.get(PROFILE_BUILD_SNAPSHOT_PROP)
    if not raw:
        return list(PROPORTION_PROFILE_PARAMS), True
    try:
        snapshot = json.loads(raw)
    except Exception:
        return list(PROPORTION_PROFILE_PARAMS), True
    dirty = []
    current = current_profile_param_snapshot(dashboard)
    for name, value in current.items():
        old_value = snapshot.get(name)
        if old_value is None or abs(float(old_value) - float(value)) > 1e-6:
            dirty.append(name)
    return dirty, False


def path_from_blender(value):
    if not value:
        return None
    return Path(bpy.path.abspath(value)).expanduser()


def addon_directory():
    return Path(__file__).resolve().parent


def bundled_metahuman_export_root():
    return addon_directory() / BUILTIN_METAHUMAN_RELATIVE_ROOT


def bundled_metahuman_dcc_export():
    return bundled_metahuman_export_root() / "DCCExport"


def ui_language(settings):
    value = getattr(settings, "interface_language", DEFAULT_INTERFACE_LANGUAGE)
    return value if value in UI_TEXT else DEFAULT_INTERFACE_LANGUAGE


def ui_text(settings, key, **kwargs):
    language = ui_language(settings)
    template = UI_TEXT.get(language, UI_TEXT[DEFAULT_INTERFACE_LANGUAGE]).get(key)
    if template is None:
        template = UI_TEXT[DEFAULT_INTERFACE_LANGUAGE].get(key, key)
    return template.format(**kwargs) if kwargs else template


def apply_scene_language_artifacts(settings):
    language = ui_language(settings)
    control_result = {"controls": 0, "renamed": 0}
    guide_result = {"labels": 0}
    if "apply_control_rig_language" in globals():
        control_result = apply_control_rig_language(language)
    if "apply_torso_guide_language" in globals():
        guide_result = apply_torso_guide_language(language)
    return {"language": language, "control_rig": control_result, "guides": guide_result}


def interface_language_updated(self, context):
    try:
        apply_scene_language_artifacts(self)
    except Exception:
        pass


def resolve_metahuman_source(settings):
    dcc_root = path_from_blender(settings.dcc_export_root)
    use_builtin = bool(getattr(settings, "use_builtin_metahuman", True))
    if use_builtin and (not dcc_root or not dcc_root.exists()):
        dcc_root = bundled_metahuman_dcc_export()
    if not dcc_root:
        raise RuntimeError("DCCExport目录为空")

    explicit_character_dir = None
    if dcc_root.name.lower() == "dccexport":
        dcc_export = dcc_root
    elif (dcc_root / "DCCExport").is_dir():
        dcc_export = dcc_root / "DCCExport"
    elif (dcc_root / "Maps").is_dir() and (dcc_root / "ExportManifest.json").is_file():
        explicit_character_dir = dcc_root
        dcc_export = dcc_root.parent
    else:
        dcc_export = dcc_root

    if not dcc_export.exists():
        raise RuntimeError(f"找不到DCCExport目录: {dcc_export}")

    character = (settings.character_name or "").strip()
    character_dir = explicit_character_dir
    if character_dir is None and character:
        preferred = dcc_export / character
        if preferred.exists():
            character_dir = preferred

    candidates = [
        item
        for item in dcc_export.iterdir()
        if item.is_dir() and ((item / "Maps").is_dir() or (item / "ExportManifest.json").is_file())
    ]
    if character_dir is None:
        if len(candidates) == 1:
            character_dir = candidates[0]
        elif not candidates:
            raise RuntimeError(f"{dcc_export} 下没有找到角色目录")
        else:
            names = ", ".join(item.name for item in candidates[:8])
            raise RuntimeError(f"DCCExport下有多个角色目录，请填写角色名: {names}")

    maps_dir = character_dir / "Maps"
    manifest_path = character_dir / "ExportManifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}

    character_name = manifest.get("metaHumanName") or character_dir.name
    export_root = dcc_export.parent

    def find_export_fbx(kind):
        folder = export_root / kind
        if not folder.exists():
            return None
        stems = list(dict.fromkeys([character_name, character_dir.name, character]))
        for stem in stems:
            if not stem:
                continue
            for suffix in (".FBX", ".fbx"):
                path = folder / f"{stem}_Exported{kind}{suffix}"
                if path.exists():
                    return path
        matches = sorted(folder.glob(f"*_Exported{kind}.FBX")) + sorted(folder.glob(f"*_Exported{kind}.fbx"))
        return matches[0] if len(matches) == 1 else None

    return {
        "dcc_export": dcc_export,
        "character_dir": character_dir,
        "character": character_name,
        "manifest": manifest_path,
        "maps": maps_dir,
        "face_fbx": find_export_fbx("Face"),
        "body_fbx": find_export_fbx("Body"),
        "export_root": export_root,
    }


def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_name(name):
    return re.sub(r"[^A-Za-z0-9_\u4e00-\u9fff]+", "_", name)


def zh_bone_display_name(bone_name):
    base = str(bone_name or "")
    side = ""
    if base.endswith("_l"):
        side = "左"
        base = base[:-2]
    elif base.endswith("_r"):
        side = "右"
        base = base[:-2]
    parts = []
    for token in base.split("_"):
        if not token:
            continue
        if token.isdigit():
            parts.append(token)
        else:
            parts.append(CONTROL_BONE_ZH_TOKENS.get(token, token))
    return side + "".join(parts) if parts else side + "控制"


def control_display_name_for_bone(bone_name, language):
    if str(language or DEFAULT_INTERFACE_LANGUAGE) == "ZH":
        return f"控制_MH_{zh_bone_display_name(bone_name)}"
    return f"{CONTROL_PREFIX}{safe_name(bone_name)}"


def control_global_display_name(language):
    return "控制_MH_全局" if str(language or DEFAULT_INTERFACE_LANGUAGE) == "ZH" else f"{CONTROL_PREFIX}Global"


def tag_control_object(obj, bone_name=None, role="BONE"):
    obj["mharp_is_control_rig"] = True
    obj["mharp_control_role"] = role
    if bone_name:
        obj["mharp_target_bone"] = bone_name
        obj["mharp_control_name_en"] = control_display_name_for_bone(bone_name, "EN")
        obj["mharp_control_name_zh"] = control_display_name_for_bone(bone_name, "ZH")
    else:
        obj["mharp_control_name_en"] = control_global_display_name("EN")
        obj["mharp_control_name_zh"] = control_global_display_name("ZH")
    if getattr(obj, "data", None):
        obj.data["mharp_is_control_mesh"] = True


def desired_control_name(obj, language):
    bone_name = obj.get("mharp_target_bone")
    if bone_name:
        return control_display_name_for_bone(str(bone_name), language)
    if obj.get("mharp_control_role") == "GLOBAL" or obj.name in {f"{CONTROL_PREFIX}Global", "控制_MH_全局"}:
        return control_global_display_name(language)
    return obj.name


def control_object_candidates():
    return [
        obj
        for obj in bpy.data.objects
        if obj.get("mharp_is_control_rig") or obj.get("mharp_target_bone") or obj.name.startswith(CONTROL_PREFIX)
    ]


def apply_control_rig_language(language):
    language = language if language in UI_TEXT else DEFAULT_INTERFACE_LANGUAGE
    renamed = 0
    for obj in control_object_candidates():
        if obj.name.startswith(CONTROL_PREFIX) and not obj.get("mharp_is_control_rig"):
            if obj.name == f"{CONTROL_PREFIX}Global":
                tag_control_object(obj, role="GLOBAL")
            elif obj.get("mharp_target_bone"):
                tag_control_object(obj, str(obj.get("mharp_target_bone")))
        target_name = desired_control_name(obj, language)
        if target_name and obj.name != target_name:
            obj.name = target_name
            renamed += 1
        if getattr(obj, "data", None) and obj.data.get("mharp_is_control_mesh"):
            obj.data.name = safe_name(f"{obj.name}_Mesh")
        obj["mharp_control_language"] = language
    return {"language": language, "renamed": renamed, "controls": len(control_object_candidates())}


def ensure_collection(name, parent=None):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
    parent = parent or bpy.context.scene.collection
    if collection.name not in {child.name for child in parent.children}:
        parent.children.link(collection)
    return collection


def move_to_collection(obj, collection):
    if obj.name not in collection.objects:
        collection.objects.link(obj)
    for old_collection in list(obj.users_collection):
        if old_collection != collection:
            old_collection.objects.unlink(obj)


def preserve_parent(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted() if parent else Matrix.Identity(4)
    obj.matrix_world = world


def detach_keep_world(obj):
    world = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_world = world


def remove_empties_keep_children(objects):
    removed = 0
    empties = [obj for obj in objects if obj.type == "EMPTY" and obj.name in bpy.data.objects]
    for empty in empties:
        for child in list(empty.children):
            detach_keep_world(child)
    bpy.context.view_layer.update()
    for empty in empties:
        if empty.name in bpy.data.objects:
            bpy.data.objects.remove(empty, do_unlink=True)
            removed += 1
    bpy.context.view_layer.update()
    return removed


def make_backup_if_saved():
    if not bpy.data.filepath:
        return None
    src = Path(bpy.data.filepath)
    if not src.exists():
        return None
    backup = src.with_name(f"{src.stem}_mharp_backup_{timestamp()}{src.suffix}")
    shutil.copy2(src, backup)
    return backup


def load_image(path, data=False):
    if not path or not Path(path).exists():
        return None
    image = bpy.data.images.load(str(path), check_existing=True)
    try:
        image.colorspace_settings.name = "Non-Color" if data else "sRGB"
    except Exception:
        pass
    return image


def set_input(material, names, value):
    if isinstance(names, str):
        names = [names]
    if not material.use_nodes or not material.node_tree:
        return
    node = next((n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if not node:
        return
    for name in names:
        if name in node.inputs:
            node.inputs[name].default_value = value
            return


def make_principled_material(
    name,
    base_color=None,
    normal=None,
    roughness=0.5,
    specular=0.35,
    alpha=1.0,
    tint=(1.0, 1.0, 1.0),
    normal_strength=0.55,
    subsurface=0.0,
    alpha_from_base=False,
):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (tint[0], tint[1], tint[2], alpha)
    material.blend_method = "HASHED" if alpha < 1.0 or alpha_from_base else "OPAQUE"
    material.show_transparent_back = True

    if node_shader_utils is not None:
        wrapper = node_shader_utils.PrincipledBSDFWrapper(material, is_readonly=False)
        wrapper.base_color = tint
        wrapper.roughness = roughness
        wrapper.specular = specular
        wrapper.alpha = alpha
        image = load_image(base_color)
        if image:
            wrapper.base_color_texture.image = image
            if alpha_from_base:
                try:
                    wrapper.alpha_texture.image = image
                except Exception:
                    pass
        image = load_image(normal, data=True)
        if image:
            wrapper.normalmap_strength = normal_strength
            wrapper.normalmap_texture.image = image
    else:
        nodes = material.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        if bsdf:
            if "Base Color" in bsdf.inputs:
                bsdf.inputs["Base Color"].default_value = material.diffuse_color
            if "Roughness" in bsdf.inputs:
                bsdf.inputs["Roughness"].default_value = roughness
            if "Alpha" in bsdf.inputs:
                bsdf.inputs["Alpha"].default_value = alpha

    set_input(material, ["Subsurface Weight", "Subsurface"], subsurface)
    return material


def make_materials(map_dir):
    return {
        "head": make_principled_material("MH_Head_Skin", map_dir / "Head_Basecolor.png", map_dir / "Head_Normal.png", roughness=0.5, specular=0.42, subsurface=0.28),
        "body": make_principled_material("MH_Body_Skin", map_dir / "Body_Basecolor.png", map_dir / "Body_Normal.png", roughness=0.52, specular=0.38, subsurface=0.22),
        "eye_left": make_principled_material("MH_Eye_Left", map_dir / "Eyes_Color.png", map_dir / "Eyes_Normal.png", roughness=0.08, specular=0.75),
        "eye_right": make_principled_material("MH_Eye_Right", map_dir / "Eyes_Color.png", map_dir / "Eyes_Normal.png", roughness=0.08, specular=0.75),
        "eye_occlusion": make_principled_material("MH_Eye_Occlusion", None, None, alpha=0.22, roughness=0.72, tint=(0.08, 0.045, 0.035), specular=0.0),
        "lacrimal": make_principled_material("MH_Lacrimal_Fluid", None, None, alpha=0.26, roughness=0.02, tint=(0.95, 0.88, 0.78), specular=0.85),
        "teeth": make_principled_material("MH_Teeth", map_dir / "Teeth_Color.png", map_dir / "Teeth_Normal.png", roughness=0.36, specular=0.45),
        "lashes": make_principled_material("MH_Eyelashes", map_dir / "Eyelashes_Color.png", None, roughness=0.6, specular=0.18, alpha_from_base=True),
        "hidden": make_principled_material("MH_Hidden_Transparent", None, None, alpha=0.0),
    }


def path_identity(path):
    try:
        return str(Path(path).resolve()).lower()
    except Exception:
        return str(path).lower()


def add_maps_dir(candidates, seen, path):
    if not path:
        return
    try:
        maps_dir = Path(path)
    except Exception:
        return
    key = path_identity(maps_dir)
    if key in seen:
        return
    seen.add(key)
    candidates.append(maps_dir)


def add_maps_from_dcc_export(candidates, seen, root, character=""):
    if not root:
        return
    try:
        root = Path(root)
    except Exception:
        return
    if root.name.lower() == "maps":
        add_maps_dir(candidates, seen, root)
        return
    if root.name.lower() != "dccexport":
        add_maps_dir(candidates, seen, root / "Maps")
        root = root / "DCCExport"
    if not root.is_dir():
        return
    if character:
        add_maps_dir(candidates, seen, root / character / "Maps")
    try:
        children = sorted(root.iterdir(), key=lambda item: item.name.lower())
    except Exception:
        return
    for child in children:
        if child.is_dir():
            add_maps_dir(candidates, seen, child / "Maps")


def metahuman_texture_search_candidates(settings, context):
    candidates = []
    seen = set()
    character = (getattr(settings, "character_name", "") or "").strip()

    try:
        source = resolve_metahuman_source(settings)
        add_maps_dir(candidates, seen, source.get("maps"))
    except Exception:
        pass

    configured_root = path_from_blender(getattr(settings, "dcc_export_root", ""))
    if configured_root:
        add_maps_from_dcc_export(candidates, seen, configured_root, character)

    scene = getattr(context, "scene", None)
    if scene:
        character_dir = scene.get("mharp_character_dir")
        if character_dir:
            add_maps_dir(candidates, seen, Path(character_dir) / "Maps")
        dcc_export = scene.get("mharp_dcc_export")
        if dcc_export:
            add_maps_from_dcc_export(candidates, seen, dcc_export, character)

    if bpy.data.filepath:
        blend_dir = Path(bpy.data.filepath).parent
        for root in (blend_dir, blend_dir / "OutPut", blend_dir.parent):
            add_maps_from_dcc_export(candidates, seen, root, character)
            add_maps_from_dcc_export(candidates, seen, root / "OutPut", character)

    add_maps_from_dcc_export(candidates, seen, bundled_metahuman_dcc_export(), character)
    return candidates


def texture_dir_score(map_dir):
    expected = {name.lower() for name in METAHUMAN_EXPECTED_TEXTURES}
    found_expected = 0
    image_count = 0
    try:
        files = list(Path(map_dir).iterdir())
    except Exception:
        return 0, 0
    for path in files:
        if not path.is_file() or path.suffix.lower() not in TEXTURE_FILE_EXTENSIONS:
            continue
        image_count += 1
        if path.name.lower() in expected:
            found_expected += 1
    return found_expected, image_count


def find_metahuman_maps_dir(settings, context):
    best = None
    for index, maps_dir in enumerate(metahuman_texture_search_candidates(settings, context)):
        if not maps_dir.is_dir():
            continue
        found_expected, image_count = texture_dir_score(maps_dir)
        if best is None or (found_expected, image_count, -index) > (best["found_expected"], best["image_count"], -best["index"]):
            best = {
                "maps_dir": maps_dir,
                "found_expected": found_expected,
                "image_count": image_count,
                "index": index,
            }
    if best is None:
        raise RuntimeError("找不到可用的 Maps 贴图目录")
    if best["found_expected"] == 0:
        raise RuntimeError(f"Maps目录里没有找到MetaForge预期贴图: {best['maps_dir']}")
    best["expected_total"] = len(METAHUMAN_EXPECTED_TEXTURES)
    return best


def build_texture_file_index(map_dir):
    texture_index = {}
    for path in Path(map_dir).iterdir():
        if path.is_file() and path.suffix.lower() in TEXTURE_FILE_EXTENSIONS:
            texture_index.setdefault(path.name.lower(), path)
    return texture_index


def texture_lookup_names(value):
    if not value:
        return set()
    raw = str(value).strip()
    if not raw:
        return set()
    name = Path(raw).name or raw.replace("\\", "/").rsplit("/", 1)[-1]
    names = {name.lower()}
    if re.search(r"\.\d{3}$", name):
        name = name[:-4]
        names.add(name.lower())
    if not Path(name).suffix:
        for ext in TEXTURE_FILE_EXTENSIONS:
            names.add(f"{name}{ext}".lower())
    return names


def image_texture_lookup_names(image):
    names = set()
    names.update(texture_lookup_names(getattr(image, "filepath", "")))
    names.update(texture_lookup_names(getattr(image, "name", "")))
    return names


def is_data_texture(path):
    stem = Path(path).stem.lower()
    return any(token in stem for token in ("normal", "cavity", "roughness", "metallic", "mask", "opacity", "alpha", "specular", "ao"))


def relink_existing_images(texture_index):
    relinked = 0
    reloaded = 0
    for image in bpy.data.images:
        replacement = None
        for name in image_texture_lookup_names(image):
            replacement = texture_index.get(name)
            if replacement:
                break
        if not replacement:
            continue
        old_path = bpy.path.abspath(image.filepath) if image.filepath else ""
        if path_identity(old_path) != path_identity(replacement):
            image.filepath = str(replacement)
            relinked += 1
        try:
            image.colorspace_settings.name = "Non-Color" if is_data_texture(replacement) else "sRGB"
        except Exception:
            pass
        try:
            image.reload()
            reloaded += 1
        except Exception:
            pass
    return {"relinked": relinked, "reloaded": reloaded}


def metahuman_material_meshes():
    return [
        obj
        for obj in bpy.data.objects
        if obj.type == "MESH" and (obj.name.startswith("MH_Face") or obj.name.startswith("MH_Body"))
    ]


def repair_metahuman_texture_index(settings, context):
    maps_info = find_metahuman_maps_dir(settings, context)
    map_dir = maps_info["maps_dir"]
    texture_index = build_texture_file_index(map_dir)
    missing = [name for name in METAHUMAN_EXPECTED_TEXTURES if name.lower() not in texture_index]

    image_result = relink_existing_images(texture_index)
    materials = make_materials(map_dir)
    meshes = metahuman_material_meshes()
    before = {
        (obj.name, index): slot.material.name if slot.material else ""
        for obj in meshes
        for index, slot in enumerate(obj.material_slots)
    }
    if meshes:
        assign_metahuman_materials(meshes, materials)
    changed_slots = sum(
        1
        for obj in meshes
        for index, slot in enumerate(obj.material_slots)
        if before.get((obj.name, index), "") != (slot.material.name if slot.material else "")
    )
    return {
        "maps_dir": map_dir,
        "found_expected": maps_info["found_expected"],
        "expected_total": maps_info["expected_total"],
        "image_count": maps_info["image_count"],
        "missing": missing,
        "relinked_images": image_result["relinked"],
        "reloaded_images": image_result["reloaded"],
        "materials": len(materials),
        "meshes": len(meshes),
        "changed_slots": changed_slots,
    }


def assign_metahuman_materials(meshes, materials):
    face_slot_materials = {
        0: "head",
        1: "teeth",
        2: "hidden",
        3: "eye_left",
        4: "eye_right",
        5: "eye_occlusion",
        6: "lashes",
        7: "lacrimal",
        8: "hidden",
        9: "head",
        10: "lashes",
        11: "head",
        12: "head",
        13: "head",
        14: "head",
    }
    for obj in meshes:
        key = obj.name.lower()
        if key.startswith("mh_face"):
            for index, slot in enumerate(obj.material_slots):
                slot.material = materials[face_slot_materials.get(index, "head")]
        elif key.startswith("mh_body"):
            for slot in obj.material_slots:
                slot.material = materials["body"]
        else:
            for slot in obj.material_slots:
                old = slot.material.name.lower() if slot.material else ""
                combined = f"{old} {key}"
                if "eyelash" in combined:
                    slot.material = materials["lashes"]
                elif "teeth" in combined:
                    slot.material = materials["teeth"]
                elif "hide" in combined or "occlusion" in combined:
                    slot.material = materials["hidden"]
                elif "lacrimal" in combined:
                    slot.material = materials["lacrimal"]
                elif "eye_r" in combined or "eyeright" in combined:
                    slot.material = materials["eye_right"]
                elif "eye_l" in combined or "eyeleft" in combined or "eye" in combined:
                    slot.material = materials["eye_left"]
                elif "head" in combined or "face" in combined:
                    slot.material = materials["head"]
                else:
                    slot.material = materials["body"]


def import_fbx(path, global_scale=1.0):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(
        filepath=str(path),
        automatic_bone_orientation=False,
        use_custom_normals=True,
        global_scale=global_scale,
    )
    return [obj for obj in bpy.data.objects if obj not in before]


def set_lods(meshes, prefix, hide_non_lod0=True):
    sorted_meshes = sorted(meshes, key=lambda item: len(item.data.vertices), reverse=True)
    for index, obj in enumerate(sorted_meshes):
        obj.name = f"{prefix}_LOD{index}"
        obj.data.name = f"{obj.name}_Mesh"
        obj.hide_viewport = False
        obj.hide_render = False
        try:
            obj.hide_set(bool(hide_non_lod0 and index != 0))
        except Exception:
            pass
    return sorted_meshes


def is_metahuman_lod0_mesh(obj):
    return obj.type == "MESH" and (obj.name.startswith("MH_Body_LOD0") or obj.name.startswith("MH_Face_LOD0"))


def is_metahuman_lod_mesh(obj):
    return obj.type == "MESH" and (obj.name.startswith("MH_Body_LOD") or obj.name.startswith("MH_Face_LOD"))


def apply_lod_visibility(obj, hide_non_lod0=True):
    if not is_metahuman_lod_mesh(obj):
        return
    hidden = bool(hide_non_lod0 and not is_metahuman_lod0_mesh(obj))
    obj.hide_viewport = False
    obj.hide_render = False
    try:
        obj.hide_set(hidden)
    except Exception:
        pass


def enforce_metahuman_lod_visibility(hide_non_lod0=True):
    for obj in bpy.data.objects:
        apply_lod_visibility(obj, hide_non_lod0)


def object_bbox_world_size(obj):
    coords = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return [
        max(vertex[i] for vertex in coords) - min(vertex[i] for vertex in coords)
        for i in range(3)
    ]


def normalize_metahuman_unit_scale(body_arm, body_meshes):
    if not body_arm or not body_meshes:
        return {"scale_factor": 1.0, "height_before": 0.0, "height_after": 0.0, "warning": ""}
    bpy.context.view_layer.update()
    body_mesh = max(body_meshes, key=lambda obj: len(obj.data.vertices))
    height = object_bbox_world_size(body_mesh)[2]
    warning = ""
    if height > 10.0:
        warning = "身高异常偏大，请检查导入缩放；插件不会缩放根骨架补救。"
    elif 0.0 < height < 0.1:
        warning = "身高异常偏小，请检查导入缩放；插件不会缩放根骨架补救。"
    return {
        "scale_factor": 1.0,
        "height_before": height,
        "height_after": height,
        "warning": warning,
    }


def get_armature(name="MH_Body_Root"):
    obj = bpy.data.objects.get(name)
    if obj and obj.type == "ARMATURE":
        return obj
    active = bpy.context.object
    if active and active.type == "ARMATURE":
        return active
    return next((obj for obj in bpy.data.objects if obj.type == "ARMATURE" and (obj.name.startswith("MH_Body") or obj.name.startswith("MH_ARP"))), None)


def is_primary_bone(name):
    if name in PRIMARY_CENTER_BONES:
        return True
    if name.endswith("_l") or name.endswith("_r"):
        return name[:-2] in PRIMARY_SIDE_BASES
    return False


def bone_rest_matrix(armature, bone):
    pose_bone = armature.pose.bones.get(bone.name) if armature.pose else None
    world = armature.matrix_world @ (pose_bone.matrix if pose_bone else bone.matrix_local)
    loc, rot, _scale = world.decompose()
    return Matrix.Translation(loc) @ rot.to_matrix().to_4x4()


def average_matrix_scale(matrix):
    m3 = matrix.to_3x3()
    values = [m3.col[index].length for index in range(3)]
    return max(sum(values) / 3.0, 0.0001)


def sign_side(name):
    if name.endswith("_l"):
        return "l"
    if name.endswith("_r"):
        return "r"
    return ""


def preferred_child_name(name, children):
    side = sign_side(name)
    child_names = {child.name for child in children}
    explicit = {
        "pelvis": "spine_01",
        "spine_01": "spine_02",
        "spine_02": "spine_03",
        "spine_03": "spine_04",
        "spine_04": "spine_05",
        "spine_05": "neck_01",
        "neck_01": "neck_02",
        "neck_02": "head",
    }
    if name in explicit and explicit[name] in child_names:
        return explicit[name]
    if side:
        base_map = {
            f"clavicle_{side}": f"upperarm_{side}",
            f"upperarm_{side}": f"lowerarm_{side}",
            f"lowerarm_{side}": f"hand_{side}",
            f"hand_{side}": f"middle_metacarpal_{side}",
            f"thigh_{side}": f"calf_{side}",
            f"calf_{side}": f"foot_{side}",
            f"foot_{side}": f"ball_{side}",
            f"ball_{side}": f"middletoe_01_{side}",
        }
        if name in base_map and base_map[name] in child_names:
            return base_map[name]
        for finger in ("index", "middle", "ring", "pinky"):
            chain = [
                f"{finger}_metacarpal_{side}",
                f"{finger}_01_{side}",
                f"{finger}_02_{side}",
                f"{finger}_03_{side}",
            ]
            if name in chain[:-1]:
                nxt = chain[chain.index(name) + 1]
                if nxt in child_names:
                    return nxt
        thumb_chain = [f"thumb_01_{side}", f"thumb_02_{side}", f"thumb_03_{side}"]
        if name in thumb_chain[:-1]:
            nxt = thumb_chain[thumb_chain.index(name) + 1]
            if nxt in child_names:
                return nxt
        for toe in TOES:
            chain = [f"{toe}_01_{side}", f"{toe}_02_{side}"]
            if name == chain[0] and chain[1] in child_names:
                return chain[1]

    helper_tokens = (
        "twist",
        "twistCor",
        "corrective",
        "bulge",
        "half",
        "side",
        "palm",
        "slide",
        "dip",
        "pip",
        "mcp",
        "fwd",
        "bck",
        "out",
        "inn",
        "latissimus",
        "pec",
        "knee",
        "wrist",
        "ankle",
    )
    for child in children:
        if not any(token in child.name for token in helper_tokens):
            return child.name
    return children[0].name if children else None


def direction_to_primary_child(bone):
    child_name = preferred_child_name(bone.name, bone.children)
    if child_name:
        child = next((candidate for candidate in bone.children if candidate.name == child_name), None)
        if child:
            direction = child.head_local - bone.head_local
            if direction.length <= 1e-8:
                direction = child.tail_local - bone.head_local
            if direction.length > 1e-8:
                return direction.normalized(), child_name, float(direction.length)
    own = bone.tail_local - bone.head_local
    if own.length > 1e-8:
        return own.normalized(), None, float(own.length)
    return Vector((1.0, 0.0, 0.0)), None, 0.05


def local_direction_for_shape(bone, target_direction):
    if target_direction is None or target_direction.length <= 1e-8:
        return Vector((1.0, 0.0, 0.0))
    local = bone.matrix_local.to_3x3().inverted() @ target_direction
    if local.length <= 1e-8:
        return Vector((1.0, 0.0, 0.0))
    return local.normalized()


def perpendiculars(direction):
    seed = Vector((0.0, 0.0, 1.0))
    if abs(float(direction.dot(seed))) > 0.92:
        seed = Vector((1.0, 0.0, 0.0))
    perp_a = direction.cross(seed)
    if perp_a.length <= 1e-8:
        perp_a = Vector((1.0, 0.0, 0.0))
    perp_a.normalize()
    perp_b = direction.cross(perp_a)
    if perp_b.length <= 1e-8:
        perp_b = Vector((0.0, 1.0, 0.0))
    perp_b.normalize()
    return perp_a, perp_b


def control_thickness_scale(level):
    if isinstance(level, (int, float)):
        return float(level)
    return CONTROL_THICKNESS_LEVELS.get(str(level or "LARGE"), CONTROL_THICKNESS_LEVELS["LARGE"])


def handle_dimensions(bone_name, target_length, thickness_scale=1.0):
    bone_length = max(float(target_length), 0.001)
    visible_length = max(bone_length * 0.82, 0.052)
    width = max(visible_length * 0.18, bone_length * 0.07, 0.012)
    if (
        bone_name.startswith(("index_", "middle_", "ring_", "pinky_", "thumb_"))
        or "toe" in bone_name
    ):
        visible_length = max(bone_length * 0.72, 0.028)
        width = max(visible_length * 0.18, 0.006)
    elif bone_name.startswith(("spine_", "neck_")) or bone_name == "pelvis":
        visible_length = max(visible_length, 0.07)
        width = max(width, bone_length * 0.09, 0.018)
    elif bone_name.startswith(("hand_", "foot_", "ball_")):
        width = max(width, bone_length * 0.075, 0.012)
    width *= control_thickness_scale(thickness_scale)
    return visible_length, width


def create_handle_mesh(name, bone_name, direction_local, target_length, thickness_scale=1.0):
    length, width = handle_dimensions(bone_name, target_length, thickness_scale)
    direction = direction_local.normalized() if direction_local.length > 1e-8 else Vector((1.0, 0.0, 0.0))
    perp_a, perp_b = perpendiculars(direction)
    start = Vector((0.0, 0.0, 0.0))
    end = direction * length
    mid = direction * length * 0.44
    ring_radius = width
    pivot_radius = width * 1.35

    verts = [
        tuple(start),
        tuple(end),
        tuple(mid + ring_radius * perp_a),
        tuple(mid + ring_radius * perp_b),
        tuple(mid - ring_radius * perp_a),
        tuple(mid - ring_radius * perp_b),
    ]
    faces = [
        (0, 2, 3),
        (0, 3, 4),
        (0, 4, 5),
        (0, 5, 2),
        (1, 3, 2),
        (1, 4, 3),
        (1, 5, 4),
        (1, 2, 5),
    ]
    edges = [
        (0, 2),
        (0, 3),
        (0, 4),
        (0, 5),
        (1, 2),
        (1, 3),
        (1, 4),
        (1, 5),
        (2, 3),
        (3, 4),
        (4, 5),
        (5, 2),
    ]
    segments = 16
    base = len(verts)
    for index in range(segments):
        angle = 2.0 * math.pi * index / segments
        verts.append(tuple(pivot_radius * (math.cos(angle) * perp_a + math.sin(angle) * perp_b)))
    edges.extend((base + i, base + ((i + 1) % segments)) for i in range(segments))
    edges.extend((0, base + i) for i in range(0, segments, 4))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, edges, faces)
    mesh.update()
    return mesh


def create_guide_mesh(name, radius=0.035):
    r = float(radius)
    verts = [
        (r, 0.0, 0.0),
        (-r, 0.0, 0.0),
        (0.0, r, 0.0),
        (0.0, -r, 0.0),
        (0.0, 0.0, r),
        (0.0, 0.0, -r),
    ]
    faces = [
        (0, 2, 4),
        (2, 1, 4),
        (1, 3, 4),
        (3, 0, 4),
        (2, 0, 5),
        (1, 2, 5),
        (3, 1, 5),
        (0, 3, 5),
    ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def ensure_material(name, color):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = color
    alpha = float(color[3]) if len(color) > 3 else 1.0
    if alpha < 0.999:
        material.use_nodes = True
        material.blend_method = "BLEND"
        material.show_transparent_back = True
        if material.node_tree:
            principled = material.node_tree.nodes.get("Principled BSDF")
            if principled and "Alpha" in principled.inputs:
                principled.inputs["Alpha"].default_value = alpha
    else:
        material.blend_method = "OPAQUE"
        if material.use_nodes and material.node_tree:
            principled = material.node_tree.nodes.get("Principled BSDF")
            if principled and "Alpha" in principled.inputs:
                principled.inputs["Alpha"].default_value = 1.0
    return material


def material_with_alpha(material, alpha):
    if not material:
        return
    rgba = list(material.diffuse_color)
    while len(rgba) < 4:
        rgba.append(1.0)
    rgba[3] = alpha
    ensure_material(material.name, tuple(rgba))


def set_object_eye_hidden(obj, hidden):
    obj.hide_viewport = False
    try:
        obj.hide_set(bool(hidden))
    except Exception:
        pass


def control_is_primary_visible(obj):
    if obj.get("mharp_control_role") == "GLOBAL" or obj.name in {f"{CONTROL_PREFIX}Global", "控制_MH_全局"}:
        return True
    bone_name = obj.get("mharp_target_bone")
    return bool(bone_name and is_primary_bone(str(bone_name)))


def control_objects():
    return control_object_candidates()


def apply_control_rig_display_mode(mode):
    mode = str(mode or "SHOW")
    visible_alpha = 0.26 if mode == "TRANSPARENT" else 1.0
    material_with_alpha(bpy.data.materials.get("MH_Control_Visible_Handle"), visible_alpha)
    material_with_alpha(bpy.data.materials.get("MH_Control_Global"), visible_alpha)
    for obj in control_objects():
        primary = control_is_primary_visible(obj)
        if mode == "HIDE":
            set_object_eye_hidden(obj, True)
            obj.hide_select = True
            continue
        if primary:
            obj.hide_viewport = False
            set_object_eye_hidden(obj, False)
            obj.hide_select = False
            obj.display_type = "TEXTURED"
            obj.show_in_front = True
        else:
            obj.hide_viewport = True
            set_object_eye_hidden(obj, True)
            obj.hide_select = True
    return {"mode": mode, "objects": len(control_objects())}


def transparent_lod_material():
    return ensure_material(LOD_TRANSPARENT_MATERIAL, (0.18, 0.55, 1.0, 0.22))


def low_lod_meshes():
    return [obj for obj in bpy.data.objects if is_metahuman_lod_mesh(obj) and not is_metahuman_lod0_mesh(obj)]


def store_original_lod_materials(obj):
    if "mharp_original_lod_materials" in obj:
        return
    obj["mharp_original_lod_materials"] = json.dumps(
        [slot.material.name if slot.material else "" for slot in obj.material_slots],
        ensure_ascii=False,
    )


def restore_original_lod_materials(obj):
    raw = obj.get("mharp_original_lod_materials")
    if not raw:
        return
    try:
        names = json.loads(raw)
    except Exception:
        names = []
    for index, name in enumerate(names):
        if index >= len(obj.material_slots):
            break
        obj.material_slots[index].material = bpy.data.materials.get(name) if name else None


def apply_lod_display_mode(mode):
    mode = str(mode or "HIDE")
    transparent = transparent_lod_material()
    lods = low_lod_meshes()
    for obj in lods:
        obj.hide_viewport = False
        obj.hide_render = False
        if mode == "HIDE":
            restore_original_lod_materials(obj)
            set_object_eye_hidden(obj, True)
        elif mode == "TRANSPARENT":
            store_original_lod_materials(obj)
            set_object_eye_hidden(obj, False)
            obj.display_type = "TEXTURED"
            if obj.material_slots:
                for slot in obj.material_slots:
                    slot.material = transparent
            else:
                obj.data.materials.append(transparent)
        else:
            restore_original_lod_materials(obj)
            set_object_eye_hidden(obj, False)
            obj.display_type = "TEXTURED"
    return {"mode": mode, "objects": len(lods)}


def remove_existing_control_rig():
    collection = bpy.data.collections.get(CONTROL_COLLECTION)
    if collection:
        for obj in list(collection.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(collection)
    for obj in list(bpy.data.objects):
        if obj.name.startswith(CONTROL_PREFIX) or obj.get("mharp_is_control_rig"):
            bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.name.startswith(CONTROL_PREFIX) or mesh.get("mharp_is_control_mesh"):
            bpy.data.meshes.remove(mesh)


def hide_deform_rigs(primary_armature=None, hide_non_lod0=True):
    hidden_collection = ensure_collection(DEFORM_HIDDEN_COLLECTION)
    hidden_collection.hide_viewport = True
    hidden_collection.hide_render = True
    hidden = []
    detached_children = []
    primary_name = primary_armature.name if primary_armature else ""
    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        is_metahuman_rig = (
            obj.name == primary_name
            or obj.name.startswith("MH_Face_Root")
            or obj.name.startswith("MH_Body_Root")
            or obj.name.startswith("MH_ARP_Root")
        )
        if not is_metahuman_rig:
            continue
        for child in list(obj.children):
            if child.type == "MESH" and (child.name.startswith("MH_Body") or child.name.startswith("MH_Face")):
                world = child.matrix_world.copy()
                child.parent = None
                child.matrix_parent_inverse = Matrix.Identity(4)
                child.matrix_world = world
                apply_lod_visibility(child, hide_non_lod0)
                for collection in child.users_collection:
                    collection.hide_viewport = False
                detached_children.append(child.name)
        obj.hide_viewport = True
        obj.hide_select = True
        obj.hide_render = True
        for view_layer in bpy.context.scene.view_layers:
            try:
                obj.hide_set(True, view_layer=view_layer)
            except Exception:
                pass
        try:
            obj.data.display_type = "WIRE"
            for bone in obj.data.bones:
                bone.hide = True
                bone.hide_select = True
        except Exception:
            pass
        move_to_collection(obj, hidden_collection)
        hidden.append(obj.name)

    shape_collection = bpy.data.collections.get("MH_UI_Custom_Bone_Shapes")
    if shape_collection:
        shape_collection.hide_viewport = True
        shape_collection.hide_render = True
        for obj in shape_collection.objects:
            obj.hide_viewport = True
            obj.hide_render = True
            obj.hide_select = True
            try:
                obj.hide_set(True)
            except Exception:
                pass
    return {"hidden_rigs": hidden, "detached_mesh_children": detached_children}


def create_global_control(armature, collection, material):
    coords = []
    for bone in armature.data.bones:
        coords.append(armature.matrix_world @ bone.head_local)
        coords.append(armature.matrix_world @ bone.tail_local)
    if coords:
        min_x = min(v.x for v in coords)
        max_x = max(v.x for v in coords)
        min_y = min(v.y for v in coords)
        max_y = max(v.y for v in coords)
        min_z = min(v.z for v in coords)
        center = Vector(((min_x + max_x) * 0.5, (min_y + max_y) * 0.5, min_z))
        radius = max(max_x - min_x, max_y - min_y) * 0.16
    else:
        center = Vector((0.0, 0.0, 0.0))
        radius = 0.45
    radius = max(radius, 0.08)
    verts = []
    edges = []
    segments = 48
    for index in range(segments):
        angle = 2.0 * math.pi * index / segments
        verts.append((math.cos(angle) * radius, math.sin(angle) * radius, 0.0))
        edges.append((index, (index + 1) % segments))
    mesh = bpy.data.meshes.new(f"{CONTROL_PREFIX}Global_Mesh")
    mesh.from_pydata(verts, edges, [])
    mesh.update()
    obj = bpy.data.objects.new(f"{CONTROL_PREFIX}Global", mesh)
    obj.matrix_world = Matrix.Translation(center)
    obj.show_in_front = True
    obj.hide_render = True
    obj.display_type = "WIRE"
    obj.data.materials.append(material)
    tag_control_object(obj, role="GLOBAL")
    collection.objects.link(obj)
    return obj, obj.matrix_world.copy()


def clear_control_constraints(armature):
    removed = 0
    for pose_bone in armature.pose.bones:
        for constraint in list(pose_bone.constraints):
            if constraint.name in {COPY_LOCATION_NAME, COPY_ROTATION_NAME}:
                pose_bone.constraints.remove(constraint)
                removed += 1
    return removed


def add_control_constraints(armature, controls):
    count = 0
    for pose_bone in armature.pose.bones:
        control = controls.get(pose_bone.name)
        if not control:
            continue
        loc = pose_bone.constraints.new(type="COPY_LOCATION")
        loc.name = COPY_LOCATION_NAME
        loc.target = control
        loc.target_space = "WORLD"
        loc.owner_space = "WORLD"
        rot = pose_bone.constraints.new(type="COPY_ROTATION")
        rot.name = COPY_ROTATION_NAME
        rot.target = control
        rot.target_space = "WORLD"
        rot.owner_space = "WORLD"
        if hasattr(rot, "mix_mode"):
            rot.mix_mode = "REPLACE"
        count += 2
    return count


def get_mirror_operator(armature):
    reflect_x = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))
    if armature:
        return armature.matrix_world @ reflect_x @ armature.matrix_world.inverted()
    return reflect_x


def counterpart_name(name, source_suffix, target_suffix):
    if not name.startswith(CONTROL_PREFIX):
        return None
    base = name
    numeric = ""
    if len(name) > 4 and name[-4] == "." and name[-3:].isdigit():
        base = name[:-4]
        numeric = name[-4:]
    if not base.endswith(source_suffix):
        return None
    candidate = base[: -len(source_suffix)] + target_suffix + numeric
    if bpy.data.objects.get(candidate):
        return candidate
    return base[: -len(source_suffix)] + target_suffix


def control_hierarchy_depth(obj):
    depth = 0
    parent = obj.parent
    while parent:
        depth += 1
        parent = parent.parent
    return depth


def mirror_control_states(source_suffix, target_suffix, armature):
    mirror_op = get_mirror_operator(armature)
    desired_worlds = {}
    pairs = []
    for source in control_objects():
        bone_name = str(source.get("mharp_target_bone") or "")
        if not bone_name.endswith(source_suffix):
            continue
        target_bone_name = bone_name[: -len(source_suffix)] + target_suffix
        target = control_object_for_bone(target_bone_name)
        if not target or target == source:
            continue
        desired_worlds[target.name] = mirror_op @ source.matrix_world.copy() @ mirror_op
        pairs.append((source, target))

    pairs.sort(key=lambda item: control_hierarchy_depth(item[1]))
    current_depth = None
    for _source, target in pairs:
        depth = control_hierarchy_depth(target)
        if current_depth is not None and depth != current_depth:
            bpy.context.view_layer.update()
        current_depth = depth
        target.matrix_world = desired_worlds[target.name]
        target.update_tag()
    bpy.context.view_layer.update()
    return len(pairs)


def get_vertex_group_weight(obj, vertex_index, names):
    best = 0.0
    for name in names:
        group = obj.vertex_groups.get(name)
        if not group:
            continue
        try:
            best = max(best, float(group.weight(vertex_index)))
        except RuntimeError:
            pass
    return best


def side_base_name(name):
    if name.endswith("_l") or name.endswith("_r"):
        return name[:-2], name[-1]
    return name, ""


def expanded_vertex_group_names(mesh_obj, bone_names):
    groups = {group.name for group in mesh_obj.vertex_groups}
    matched = set()
    for bone_name in bone_names:
        if bone_name in groups:
            matched.add(bone_name)
        base, side = side_base_name(bone_name)
        for group_name in groups:
            if group_name == bone_name or group_name.startswith(bone_name + "_"):
                matched.add(group_name)
                continue
            if side and group_name.startswith(base + "_") and group_name.endswith("_" + side):
                matched.add(group_name)
                continue
            if not side and (group_name == base or group_name.startswith(base + "_")):
                matched.add(group_name)
    return sorted(matched)


def best_weighted_group(obj, vertex_index, names):
    best_name = None
    best = 0.0
    for name in names:
        group = obj.vertex_groups.get(name)
        if not group:
            continue
        try:
            weight = float(group.weight(vertex_index))
        except RuntimeError:
            continue
        if weight > best:
            best = weight
            best_name = name
    return best_name, best


def vertex_group_index_lookup(mesh_obj, names):
    lookup = {}
    for name in names:
        group = mesh_obj.vertex_groups.get(name)
        if group:
            lookup[group.index] = name
    return lookup


def best_weighted_group_for_vertex(vertex, group_lookup):
    best_name = None
    best = 0.0
    if not group_lookup:
        return best_name, best
    for item in vertex.groups:
        group_name = group_lookup.get(item.group)
        if group_name and item.weight > best:
            best = float(item.weight)
            best_name = group_name
    return best_name, best


def clamp01(value):
    return min(max(float(value), 0.0), 1.0)


def smoothstep01(value):
    value = clamp01(value)
    return value * value * (3.0 - 2.0 * value)


def profile_param(dashboard, name):
    meta = PROPORTION_PROFILE_PARAMS[name]
    raw = dashboard.get(name)
    if raw is None:
        for old_name in PROFILE_PARAM_ALIASES.get(name, ()):
            if old_name in dashboard:
                raw = dashboard.get(old_name)
                break
    if raw is None:
        raw = meta["default"]
    return min(max(float(raw), meta["min"]), meta["max"])


def boosted_profile_weight(dashboard, name, boost=2.0):
    meta = PROPORTION_PROFILE_PARAMS[name]
    default = float(meta["default"])
    raw = profile_param(dashboard, name)
    boosted = default + (raw - default) * boost
    return min(max(boosted, meta["min"]), meta["max"])


def falloff_curve01(t, endpoint=0.16, curve=0.6):
    t = clamp01(t)
    endpoint = min(max(float(endpoint), 0.001), 0.999)
    curve = max(float(curve), 0.05)
    edge = smoothstep01(t / endpoint) * smoothstep01((1.0 - t) / endpoint)
    bell = max(math.sin(math.pi * t), 0.0) ** curve
    return clamp01(edge * bell)


_FALLOFF_INTEGRAL_CACHE = {}


def falloff_displacement01(t, endpoint=0.16, curve=0.6, steps=96):
    t = clamp01(t)
    endpoint = min(max(float(endpoint), 0.001), 0.999)
    curve = max(float(curve), 0.05)
    steps = max(int(steps), 8)
    key = (round(endpoint, 4), round(curve, 4), steps)
    cumulative = _FALLOFF_INTEGRAL_CACHE.get(key)
    if cumulative is None:
        samples = [falloff_curve01(index / steps, endpoint, curve) for index in range(steps + 1)]
        cumulative = [0.0]
        total = 0.0
        for index in range(1, steps + 1):
            total += (samples[index - 1] + samples[index]) * 0.5 / steps
            cumulative.append(total)
        if total > 1e-8:
            cumulative = [value / total for value in cumulative]
        else:
            cumulative = [index / steps for index in range(steps + 1)]
        _FALLOFF_INTEGRAL_CACHE[key] = cumulative
    position = t * steps
    low = min(int(math.floor(position)), steps)
    high = min(low + 1, steps)
    if low == high:
        return cumulative[low]
    blend = position - low
    return cumulative[low] * (1.0 - blend) + cumulative[high] * blend


def length_terminal_weight_factor(segment_weight, t, endpoint):
    base_weight = math.pow(clamp01(segment_weight), 0.35)
    if base_weight <= 1e-6:
        return 0.0
    terminal_start = min(0.78, 1.0 - max(float(endpoint) * 1.5, 0.02))
    terminal_full = min(0.90, 1.0 - max(float(endpoint) * 0.35, 0.04))
    if terminal_full <= terminal_start:
        terminal_blend = 1.0 if t >= terminal_full else 0.0
    else:
        terminal_blend = smoothstep01((t - terminal_start) / (terminal_full - terminal_start))
    return base_weight * (1.0 - terminal_blend) + terminal_blend


def prop_limb_family(prop):
    if prop.startswith(("上臂", "小臂")):
        return "上肢"
    if prop.startswith(("大腿", "小腿")):
        return "下肢"
    return "四肢"


def torso_height_item_def():
    return next((item for item in PROPORTION_DEFS if item["prop"] == "躯干高度"), None)


def length_primary_role(prop, group_name):
    if not group_name:
        return None
    lowered = group_name.lower()
    configs = {
        "上臂长度": (
            ("upperarm",),
            ("lowerarm", "hand", "wrist", "metacarpal", "thumb_", "index_", "middle_", "ring_", "pinky_"),
        ),
        "小臂长度": (
            ("lowerarm",),
            ("hand", "wrist", "metacarpal", "thumb_", "index_", "middle_", "ring_", "pinky_"),
        ),
        "大腿长度": (
            ("thigh",),
            ("calf", "foot", "ankle", "ball", "toe"),
        ),
        "小腿长度": (
            ("calf",),
            ("foot", "ankle", "ball", "toe"),
        ),
    }
    segment_tokens, follow_tokens = configs.get(prop, ((), ()))
    if any(token in lowered for token in segment_tokens):
        return "segment"
    if any(token in lowered for token in follow_tokens):
        return "follow"
    return None


def width_primary_role(prop, group_name):
    if not group_name:
        return None
    lowered = group_name.lower()
    configs = {
        "上臂粗细": ("upperarm",),
        "小臂粗细": ("lowerarm",),
        "大腿粗细": ("thigh",),
        "小腿粗细": ("calf",),
    }
    tokens = configs.get(prop, ())
    if any(token in lowered for token in tokens):
        return "segment"
    return None


def vertex_group_side(name):
    if name.endswith("_l") or "_l_" in name:
        return "l"
    if name.endswith("_r") or "_r_" in name:
        return "r"
    return ""


def first_existing_bone(armature, names):
    for name in names:
        bone = armature.data.bones.get(name)
        if bone:
            return bone
    return None


def axis_bone_for_group(armature, item, group_name):
    if group_name and group_name in armature.data.bones:
        return armature.data.bones[group_name]
    side = vertex_group_side(group_name or "")
    axis_bones = item.get("axis_bones", [])
    if side:
        side_bone = first_existing_bone(armature, [name for name in axis_bones if name.endswith("_" + side)])
        if side_bone:
            return side_bone
    return first_existing_bone(armature, axis_bones)


def axis_bone_for_length_group(armature, item, segment_group_name, follow_group_name=None):
    side = vertex_group_side(segment_group_name or "") or vertex_group_side(follow_group_name or "")
    axis_bones = item.get("axis_bones", [])
    if side:
        side_bone = first_existing_bone(armature, [name for name in axis_bones if name.endswith("_" + side)])
        if side_bone:
            return side_bone
    return first_existing_bone(armature, axis_bones)


def bone_axis_data(mesh_obj, armature, bone):
    head = mesh_obj.matrix_world.inverted() @ (armature.matrix_world @ bone.head_local)
    tail = mesh_obj.matrix_world.inverted() @ (armature.matrix_world @ bone.tail_local)
    vector = tail - head
    length = vector.length
    if length <= 1e-8:
        return head, Vector((0.0, 0.0, 1.0)), 0.0
    return head, vector.normalized(), length


def control_object_for_bone(bone_name):
    expected = bpy.data.objects.get(f"{CONTROL_PREFIX}{safe_name(bone_name)}")
    if expected:
        return expected
    for obj in control_object_candidates():
        if str(obj.get("mharp_target_bone") or "") == str(bone_name):
            return obj
    return None


def control_axis_local_vector(control):
    if control and control.type == "MESH" and len(control.data.vertices) > 1:
        return control.data.vertices[1].co.copy()
    if control and control.type == "MESH" and control.data.vertices:
        return max((vert.co.copy() for vert in control.data.vertices), key=lambda co: co.length)
    return None


def control_axis_data(mesh_obj, armature, bone, axis_cache=None):
    if axis_cache is not None and bone.name in axis_cache:
        return axis_cache[bone.name]
    head, fallback_axis, length = bone_axis_data(mesh_obj, armature, bone)
    control = control_object_for_bone(bone.name)
    if control and control.type == "MESH" and control.data.vertices:
        axis_hint = control_axis_local_vector(control)
        axis_world = control.matrix_world.to_3x3() @ axis_hint
        axis_local = mesh_obj.matrix_world.inverted().to_3x3() @ axis_world
        control_head = mesh_obj.matrix_world.inverted() @ control.matrix_world.translation
        if axis_local.length > 1e-8:
            result = (control_head, axis_local.normalized(), length)
            if axis_cache is not None:
                axis_cache[bone.name] = result
            return result
    result = (head, fallback_axis, length)
    if axis_cache is not None:
        axis_cache[bone.name] = result
    return result


def length_follow_root_name(item, side):
    roots = item.get("follow_roots", [])
    if side:
        for name in roots:
            if name.endswith("_" + side):
                return name
    return roots[0] if roots else None


WIDTH_FADE_FOLLOW_ROOTS = {
    "上臂粗细": ["lowerarm_l", "lowerarm_r"],
    "小臂粗细": ["hand_l", "hand_r"],
    "大腿粗细": ["calf_l", "calf_r"],
    "小腿粗细": ["foot_l", "foot_r"],
}


def width_chain_axis_data(mesh_obj, armature, item, bone, side, axis_cache=None):
    fade_item = dict(item)
    fade_item["follow_roots"] = WIDTH_FADE_FOLLOW_ROOTS.get(item["prop"], [])
    return length_chain_axis_data(mesh_obj, armature, fade_item, bone, side, axis_cache)


def length_chain_axis_data(mesh_obj, armature, item, bone, side, axis_cache=None):
    cache_key = ("length_chain", bone.name, side or "")
    if axis_cache is not None and cache_key in axis_cache:
        return axis_cache[cache_key]

    head_world = armature.matrix_world @ bone.head_local
    end_bone = None
    follow_root = length_follow_root_name(item, side)
    if follow_root:
        end_bone = armature.data.bones.get(follow_root)
    if end_bone is None:
        child_name = preferred_child_name(bone.name, bone.children)
        if child_name:
            end_bone = armature.data.bones.get(child_name)

    if end_bone:
        tail_world = armature.matrix_world @ end_bone.head_local
    else:
        tail_world = armature.matrix_world @ bone.tail_local

    head = mesh_obj.matrix_world.inverted() @ head_world
    tail = mesh_obj.matrix_world.inverted() @ tail_world
    chain_vector = tail - head
    chain_length = chain_vector.length
    if chain_length <= 1e-8:
        result = control_axis_data(mesh_obj, armature, bone, axis_cache)
        if axis_cache is not None:
            axis_cache[cache_key] = result
        return result

    _control_head, axis, _control_length = control_axis_data(mesh_obj, armature, bone, axis_cache)
    if axis.dot(chain_vector) < 0.0:
        axis = -axis
    result = (head, axis.normalized(), chain_length)
    if axis_cache is not None:
        axis_cache[cache_key] = result
    return result


def descendants_from_roots(armature, roots):
    names = set()
    stack = [armature.data.bones.get(name) for name in roots]
    stack = [bone for bone in stack if bone]
    while stack:
        bone = stack.pop()
        if bone.name in names:
            continue
        names.add(bone.name)
        stack.extend(list(bone.children))
    return sorted(names)


def follow_vertex_group_names(mesh_obj, armature, item):
    roots = item.get("follow_roots", [])
    if not roots:
        return []
    return expanded_vertex_group_names(mesh_obj, descendants_from_roots(armature, roots))


def length_delta_for_vertex(
    mesh_obj,
    armature,
    dashboard,
    item,
    co,
    segment_group_name,
    follow_group_name,
    segment_weight,
    follow_weight,
    primary_is_follow=False,
    axis_cache=None,
):
    bone = axis_bone_for_length_group(armature, item, segment_group_name, follow_group_name)
    if not bone:
        return Vector((0.0, 0.0, 0.0))
    side = vertex_group_side(segment_group_name or "") or vertex_group_side(follow_group_name or "")
    head, axis, length = length_chain_axis_data(mesh_obj, armature, item, bone, side, axis_cache)
    if length <= 1e-8:
        return Vector((0.0, 0.0, 0.0))
    if primary_is_follow:
        return axis * length
    t = clamp01((co - head).dot(axis) / length)
    family = prop_limb_family(item["prop"])
    endpoint = profile_param(dashboard, "四肢.长度.骨末端衰减")
    curve = profile_param(dashboard, f"{family}.长度.骨末端衰减")
    profile = falloff_displacement01(t, endpoint, curve)
    segment_weight = length_terminal_weight_factor(segment_weight, t, endpoint)
    factor = clamp01(segment_weight * profile)
    if factor <= 1e-6:
        return Vector((0.0, 0.0, 0.0))
    return axis * (length * factor)


def average_axis_center_local(mesh_obj, armature, bone_names):
    center_world = average_bone_center_world(armature, bone_names)
    return mesh_obj.matrix_world.inverted() @ center_world


TORSO_EXCLUDE_TOKENS = (
    "clavicle",
    "upperarm",
    "lowerarm",
    "hand",
    "metacarpal",
    "thumb_",
    "index_",
    "middle_",
    "ring_",
    "pinky_",
    "neck",
    "head",
    "thigh",
    "calf",
    "foot",
    "ball",
    "toe",
)


def is_torso_width_vertex_group(group_name):
    if not group_name:
        return True
    lowered = group_name.lower()
    if any(token in lowered for token in TORSO_EXCLUDE_TOKENS):
        return False
    return lowered.startswith(("pelvis", "spine", "breast", "abdomen", "torso", "root"))


def normalized_direction_blend(primary, normal, normal_weight):
    normal_weight = clamp01(normal_weight)
    primary_weight = 1.0 - normal_weight
    direction = primary * primary_weight + normal * normal_weight
    if direction.length <= 1e-8:
        direction = primary if primary.length > 1e-8 else normal
    if direction.length > 1e-8:
        direction.normalize()
    return direction


def torso_width_guide_specs(prop, unit):
    if prop == "胸部粗细":
        return [
            {"id": "chest_l_front", "label": "乳头（左）", "side": "L", "offset": (-unit * 0.17, unit * 0.24, unit * 0.02), "radii": (unit * 0.17, unit * 0.21, unit * 0.16), "direction": (0.0, 1.0, 0.0), "strength": 1.0, "amplitude": 0.32, "color": (0.25, 0.62, 1.0, 1.0)},
            {"id": "chest_r_front", "label": "乳头（右虚影）", "side": "R", "mirror_of": "chest_l_front", "offset": (unit * 0.17, unit * 0.24, unit * 0.02), "radii": (unit * 0.17, unit * 0.21, unit * 0.16), "direction": (0.0, 1.0, 0.0), "strength": 1.0, "amplitude": 0.32, "color": (0.25, 0.62, 1.0, 0.42)},
            {"id": "chest_back_soft", "label": "胸背中线", "side": "C", "offset": (0.0, -unit * 0.12, 0.0), "radii": (unit * 0.20, unit * 0.11, unit * 0.14), "direction": (0.0, -1.0, 0.0), "strength": 0.16, "amplitude": 0.18, "color": (0.38, 0.45, 0.70, 0.78)},
        ]
    if prop == "腰部粗细":
        return [
            {"id": "waist_l_side", "label": "腰侧（左）", "side": "L", "offset": (-unit * 0.29, -unit * 0.02, 0.0), "radii": (unit * 0.14, unit * 0.17, unit * 0.18), "direction": (-1.0, 0.0, 0.0), "strength": 0.92, "amplitude": 0.31, "color": (0.25, 0.92, 0.64, 1.0)},
            {"id": "waist_r_side", "label": "腰侧（右虚影）", "side": "R", "mirror_of": "waist_l_side", "offset": (unit * 0.29, -unit * 0.02, 0.0), "radii": (unit * 0.14, unit * 0.17, unit * 0.18), "direction": (1.0, 0.0, 0.0), "strength": 0.92, "amplitude": 0.31, "color": (0.25, 0.92, 0.64, 0.42)},
            {"id": "abdomen_front", "label": "肚脐眼", "side": "C", "offset": (0.0, unit * 0.23, -unit * 0.02), "radii": (unit * 0.22, unit * 0.17, unit * 0.20), "direction": (0.0, 1.0, 0.0), "strength": 0.78, "amplitude": 0.29, "color": (0.32, 0.88, 0.42, 1.0)},
        ]
    return [
        {"id": "pelvis_front_center", "label": "鼠蹊三角区", "side": "C", "offset": (0.0, unit * 0.20, -unit * 0.07), "radii": (unit * 0.20, unit * 0.18, unit * 0.18), "direction": (0.0, 1.0, 0.0), "strength": 1.0, "amplitude": 0.26, "color": (1.0, 0.62, 0.22, 1.0)},
        {"id": "pelvis_l_front_soft", "label": "胯前侧（左）", "side": "L", "offset": (-unit * 0.12, unit * 0.17, -unit * 0.05), "radii": (unit * 0.13, unit * 0.13, unit * 0.14), "direction": (0.0, 1.0, 0.0), "strength": 0.32, "amplitude": 0.18, "color": (1.0, 0.74, 0.34, 0.86)},
        {"id": "pelvis_r_front_soft", "label": "胯前侧（右虚影）", "side": "R", "mirror_of": "pelvis_l_front_soft", "offset": (unit * 0.12, unit * 0.17, -unit * 0.05), "radii": (unit * 0.13, unit * 0.13, unit * 0.14), "direction": (0.0, 1.0, 0.0), "strength": 0.32, "amplitude": 0.18, "color": (1.0, 0.74, 0.34, 0.42)},
        {"id": "pelvis_l_back_glute", "label": "臀顶（左）", "side": "L", "offset": (-unit * 0.13, -unit * 0.45, -unit * 0.04), "radii": (unit * 0.15, unit * 0.20, unit * 0.22), "direction": (0.0, -1.0, 0.0), "strength": 0.40, "amplitude": 0.20, "color": (1.0, 0.50, 0.20, 0.92)},
        {"id": "pelvis_r_back_glute", "label": "臀顶（右虚影）", "side": "R", "mirror_of": "pelvis_l_back_glute", "offset": (unit * 0.13, -unit * 0.45, -unit * 0.04), "radii": (unit * 0.15, unit * 0.20, unit * 0.22), "direction": (0.0, -1.0, 0.0), "strength": 0.40, "amplitude": 0.20, "color": (1.0, 0.50, 0.20, 0.42)},
        {"id": "pelvis_back_center", "label": "肛门", "side": "C", "offset": (0.0, -unit * 0.38, -unit * 0.13), "radii": (unit * 0.11, unit * 0.15, unit * 0.16), "direction": (0.0, -1.0, 0.0), "strength": 0.18, "amplitude": 0.12, "color": (1.0, 0.44, 0.24, 0.82)},
    ]


def torso_guide_object_name(guide_id):
    return f"{TORSO_GUIDE_PREFIX}{safe_name(guide_id)}"


def torso_guide_label_object_name(guide_id):
    return f"{TORSO_GUIDE_LABEL_PREFIX}{safe_name(guide_id)}"


def torso_guide_label_text(guide_id, language):
    language = language if language in TORSO_GUIDE_LABELS else DEFAULT_INTERFACE_LANGUAGE
    return TORSO_GUIDE_LABELS.get(language, TORSO_GUIDE_LABELS[DEFAULT_INTERFACE_LANGUAGE]).get(guide_id, guide_id)


def torso_symmetry_plane_x_local(mesh_obj, armature=None):
    if mesh_obj and armature and armature.type == "ARMATURE":
        pelvis = armature.data.bones.get("pelvis")
        if pelvis:
            center_world = armature.matrix_world @ ((pelvis.head_local + pelvis.tail_local) * 0.5)
            return (mesh_obj.matrix_world.inverted() @ center_world).x
    return 0.0


def mirror_local_x(local, plane_x):
    mirrored = local.copy()
    mirrored.x = plane_x * 2.0 - mirrored.x
    return mirrored


def torso_guide_world_location(mesh_obj, spec, default_center, plane_x=0.0):
    if spec.get("mirror_of"):
        source = bpy.data.objects.get(torso_guide_object_name(spec["mirror_of"]))
        if source:
            source_local = mesh_obj.matrix_world.inverted() @ source.matrix_world.translation
            return mirror_local_x(source_local, plane_x)
    obj = bpy.data.objects.get(torso_guide_object_name(spec["id"]))
    if obj:
        local = mesh_obj.matrix_world.inverted() @ obj.matrix_world.translation
        if spec.get("side") == "C":
            local.x = plane_x
        return local
    if spec.get("side") == "C":
        default_center = default_center.copy()
        default_center.x = plane_x
    return default_center


def torso_width_guides(mesh_obj, prop, center, torso_height, smooth, plane_x=0.0):
    unit = max(float(torso_height), 1.0)
    soft = 1.0 + clamp01(smooth / 1.6) * 0.55

    def guide(spec):
        offset = spec["offset"]
        radii = spec["radii"]
        default_center = center + Vector(offset)
        return {
            "id": spec["id"],
            "center": torso_guide_world_location(mesh_obj, spec, default_center, plane_x),
            "radii": Vector((max(radii[0] * soft, 0.001), max(radii[1] * soft, 0.001), max(radii[2] * soft, 0.001))),
            "direction": Vector(spec["direction"]),
            "strength": float(spec["strength"]),
            "amplitude": unit * float(spec["amplitude"]),
        }

    return [guide(spec) for spec in torso_width_guide_specs(prop, unit)]


def anisotropic_bump_weight(co, guide):
    rel = co - guide["center"]
    radii = guide["radii"]
    q = (rel.x / radii.x) ** 2 + (rel.y / radii.y) ** 2 + (rel.z / radii.z) ** 2
    if q >= 1.0:
        return 0.0
    return smoothstep01(1.0 - q) * guide["strength"]


def guided_torso_width_delta(mesh_obj, prop, co, center, normal, normal_weight, torso_height, smooth, plane_x=0.0):
    guides = torso_width_guides(mesh_obj, prop, center, torso_height, smooth, plane_x)
    combined = 0.0
    semantic = Vector((0.0, 0.0, 0.0))
    amplitude_sum = 0.0
    weight_sum = 0.0
    for guide in guides:
        weight = clamp01(anisotropic_bump_weight(co, guide))
        if weight <= 0.0001:
            continue
        combined = 1.0 - (1.0 - combined) * (1.0 - weight)
        guide_direction = guide["direction"]
        if guide_direction.length > 1e-8:
            semantic += guide_direction.normalized() * weight
        amplitude_sum += guide["amplitude"] * weight
        weight_sum += weight
    if combined <= 0.0001 or weight_sum <= 0.0001:
        return Vector((0.0, 0.0, 0.0)), 0.0
    if semantic.length <= 1e-8:
        semantic = co - center
        semantic.z = 0.0
    if semantic.length > 1e-8:
        semantic.normalize()
    normal_direction = Vector((normal.x, normal.y, normal.z * 0.35))
    if normal_direction.length > 1e-8:
        normal_direction.normalize()
    direction = normalized_direction_blend(semantic, normal_direction, normal_weight)
    amplitude = amplitude_sum / weight_sum
    return direction * amplitude * combined, combined


def torso_width_delta(mesh_obj, armature, dashboard, item, co, normal, group_name):
    if not is_torso_width_vertex_group(group_name):
        return Vector((0.0, 0.0, 0.0)), 0.0
    prop = item["prop"]
    center = average_axis_center_local(mesh_obj, armature, item["axis_bones"])
    low_z, high_z, torso_height = torso_height_data(mesh_obj, armature)
    plane_x = torso_symmetry_plane_x_local(mesh_obj, armature)
    smooth = profile_param(dashboard, "躯干.粗细.边界平滑")
    if prop == "胯部粗细":
        normal_weight = profile_param(dashboard, "胯部.粗细.法向混合")
    elif prop == "腰部粗细":
        normal_weight = profile_param(dashboard, "腰部.粗细.法向混合")
    else:
        normal_weight = profile_param(dashboard, "胸部.粗细.法向混合")
    return guided_torso_width_delta(mesh_obj, prop, co, center, normal, normal_weight, torso_height, smooth, plane_x)


def torso_height_data(mesh_obj, armature):
    low_bone = first_existing_bone(armature, ["spine_01", "pelvis"])
    high_bone = first_existing_bone(armature, ["spine_05", "spine_04", "spine_03"])
    if not low_bone or not high_bone:
        return 0.0, 1.0, 1.0
    low = mesh_obj.matrix_world.inverted() @ (armature.matrix_world @ low_bone.head_local)
    high = mesh_obj.matrix_world.inverted() @ (armature.matrix_world @ high_bone.tail_local)
    low_z = min(low.z, high.z)
    high_z = max(low.z, high.z)
    height = max(high_z - low_z, 1.0)
    return low_z, high_z, height


def torso_height_cumulative_factor(t, dashboard):
    hip_weight = boosted_profile_weight(dashboard, "躯干.高度.胯权重")
    waist_weight = boosted_profile_weight(dashboard, "躯干.高度.腰权重")
    chest_weight = boosted_profile_weight(dashboard, "躯干.高度.胸权重")
    smoothing = profile_param(dashboard, "躯干.高度.区块平滑")
    total = max(hip_weight + waist_weight + chest_weight, 1e-6)
    hip_end = 0.20 + smoothing * 0.16
    waist_start = 0.18
    waist_end = 0.58 + smoothing * 0.18
    chest_start = 0.56
    chest_end = 0.86 + smoothing * 0.12
    value = hip_weight * smoothstep01(t / max(hip_end, 0.01))
    value += waist_weight * smoothstep01((t - waist_start) / max(waist_end - waist_start, 0.01))
    value += chest_weight * smoothstep01((t - chest_start) / max(chest_end - chest_start, 0.01))
    return clamp01(value / total)


def is_torso_height_upper_follow_group(group_name):
    if not group_name:
        return False
    lowered = group_name.lower()
    if lowered.startswith(("clavicle", "upperarm", "lowerarm", "hand", "wrist", "metacarpal")):
        return True
    return any(token in lowered for token in ("thumb_", "index_", "middle_", "ring_", "pinky_"))


def torso_height_factor(co, group_name, weight, low_z, high_z, dashboard):
    if group_name:
        lowered = group_name.lower()
        if lowered.startswith(("thigh", "calf", "foot", "ball")) or "toe" in lowered:
            return 0.0
        if is_torso_height_upper_follow_group(group_name):
            return 0.0
        if group_name.startswith(("neck", "head")):
            return 1.0
    span = max(high_z - low_z, 1.0)
    return torso_height_cumulative_factor((co.z - low_z) / span, dashboard)


def iter_layer_collections(layer_collection):
    yield layer_collection
    for child in layer_collection.children:
        yield from iter_layer_collections(child)


def collection_parent_map():
    parents = {}

    def walk(parent):
        for child in parent.children:
            parents.setdefault(child, []).append(parent)
            walk(child)

    walk(bpy.context.scene.collection)
    return parents


def reveal_collection_and_ancestors(collection):
    parents = collection_parent_map()
    stack = [collection]
    seen = set()
    while stack:
        item = stack.pop()
        if item.name in seen:
            continue
        seen.add(item.name)
        item.hide_viewport = False
        for view_layer in bpy.context.scene.view_layers:
            for layer_collection in iter_layer_collections(view_layer.layer_collection):
                if layer_collection.collection != item:
                    continue
                layer_collection.exclude = False
                layer_collection.hide_viewport = False
                if hasattr(layer_collection, "holdout"):
                    layer_collection.holdout = False
                if hasattr(layer_collection, "indirect_only"):
                    layer_collection.indirect_only = False
        stack.extend(parents.get(item, []))


def average_bone_axis(armature, bone_names, fallback=Vector((0.0, 0.0, 1.0))):
    axes = []
    for name in bone_names:
        bone = armature.data.bones.get(name)
        if not bone:
            continue
        axis = bone.tail_local - bone.head_local
        if axis.length > 1e-6:
            axes.append(axis.normalized())
    if not axes:
        return fallback.normalized()
    axis = Vector((0.0, 0.0, 0.0))
    for item in axes:
        axis += item
    if axis.length < 1e-6:
        axis = axes[0]
    return axis.normalized()


def average_bone_center_world(armature, bone_names):
    points = []
    for name in bone_names:
        bone = armature.data.bones.get(name)
        if bone:
            points.append(armature.matrix_world @ ((bone.head_local + bone.tail_local) * 0.5))
    if not points:
        return armature.matrix_world.translation
    total = Vector((0.0, 0.0, 0.0))
    for point in points:
        total += point
    return total / len(points)


def reveal_object_and_collections(obj):
    obj.hide_viewport = False
    obj.hide_render = False
    for view_layer in bpy.context.scene.view_layers:
        try:
            obj.hide_set(False, view_layer=view_layer)
        except Exception:
            pass
    for collection in obj.users_collection:
        reveal_collection_and_ancestors(collection)


def find_body_mesh(settings=None):
    candidates = []
    preferred = getattr(settings, "body_mesh_name", "") if settings else ""
    if preferred:
        obj = bpy.data.objects.get(preferred)
        if obj and obj.type == "MESH":
            return obj
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.name.startswith("MH_Body_LOD0"):
            candidates.append(obj)
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.name.startswith("MH_Body"):
            candidates.append(obj)
    if not candidates:
        return None
    candidates = sorted(
        set(candidates),
        key=lambda item: (not item.visible_get(), -len(item.data.vertices)),
    )
    return candidates[0]


def find_face_lod0_mesh():
    candidates = [obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith("MH_Face_LOD0")]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (not item.visible_get(), -len(item.data.vertices)))[0]


def create_dashboard():
    obj = bpy.data.objects.get(DASHBOARD_NAME)
    if obj is None:
        obj = bpy.data.objects.new(DASHBOARD_NAME, None)
        obj.empty_display_type = "SPHERE"
        obj.empty_display_size = 0.12
        obj.location = (0.8, -0.55, 1.15)
        ensure_collection(SHAPE_COLLECTION).objects.link(obj)
    elif not obj.users_collection:
        ensure_collection(SHAPE_COLLECTION).objects.link(obj)
    reveal_object_and_collections(obj)
    for item in PROPORTION_DEFS:
        prop = item["prop"]
        if prop not in obj:
            obj[prop] = 1.0
        obj.id_properties_ui(prop).update(
            min=0.65,
            max=3.10,
            soft_min=0.85,
            soft_max=2.4,
            description=item.get("hint", item["description"]),
        )
    for name, meta in PROPORTION_PROFILE_PARAMS.items():
        if name not in obj:
            migrated_value = None
            for old_name in PROFILE_PARAM_ALIASES.get(name, ()):
                if old_name in obj:
                    migrated_value = obj[old_name]
                    break
            obj[name] = meta["default"] if migrated_value is None else migrated_value
        else:
            old_default, new_default = PROFILE_PARAM_DEFAULT_MIGRATIONS.get(name, (None, None))
            if old_default is not None and abs(float(obj.get(name, new_default)) - old_default) <= 1e-6:
                obj[name] = new_default
        obj.id_properties_ui(name).update(
            min=meta["min"],
            max=meta["max"],
            soft_min=meta["min"],
            soft_max=meta["max"],
            description=meta.get("hint", meta["description"]),
        )
    for old_names in PROFILE_PARAM_ALIASES.values():
        for old_name in old_names:
            if old_name in obj:
                del obj[old_name]
    return obj


def ensure_basis_shape_key(mesh_obj):
    if mesh_obj.data.shape_keys is None:
        mesh_obj.shape_key_add(name="Basis")


def add_shape_key_driver(mesh_obj, shape_name, dashboard, item):
    prop = item["prop"]
    strength = float(item.get("driver_strength", 1.0))
    key_data = mesh_obj.data.shape_keys
    data_path = f'key_blocks["{shape_name}"].value'
    try:
        key_data.driver_remove(data_path)
    except (TypeError, RuntimeError):
        pass
    fcurve = key_data.driver_add(data_path)
    driver = fcurve.driver
    driver.type = "SCRIPTED"
    driver.expression = f"(ratio-1.0)*{strength:.6f}"
    while driver.variables:
        driver.variables.remove(driver.variables[0])
    var = driver.variables.new()
    var.name = "ratio"
    var.type = "SINGLE_PROP"
    target = var.targets[0]
    target.id_type = "OBJECT"
    target.id = dashboard
    target.data_path = f'["{prop}"]'


def add_control_visual_shape_driver(control, shape_name, dashboard, item):
    prop = item["prop"]
    strength = float(item.get("driver_strength", 1.0))
    key_data = control.data.shape_keys
    data_path = f'key_blocks["{shape_name}"].value'
    try:
        key_data.driver_remove(data_path)
    except (TypeError, RuntimeError):
        pass
    fcurve = key_data.driver_add(data_path)
    driver = fcurve.driver
    driver.type = "SCRIPTED"
    driver.expression = f"(ratio-1.0)*{strength:.6f}"
    while driver.variables:
        driver.variables.remove(driver.variables[0])
    variable = driver.variables.new()
    variable.name = "ratio"
    variable.type = "SINGLE_PROP"
    target = variable.targets[0]
    target.id_type = "OBJECT"
    target.id = dashboard
    target.data_path = f'["{prop}"]'


def driver_float_literal(value):
    value = float(value)
    if not math.isfinite(value):
        value = 0.0
    return format(value, ".17g")


def add_object_z_driver(obj, dashboard, prop, delta_z):
    obj["mharp_base_location_z"] = float(obj.location.z)
    obj["mharp_torso_height_delta_z"] = float(delta_z)
    try:
        obj.driver_remove("location", 2)
    except (TypeError, RuntimeError):
        pass
    fcurve = obj.driver_add("location", 2)
    driver = fcurve.driver
    driver.type = "SCRIPTED"
    driver.expression = (
        f"{driver_float_literal(obj.location.z)}"
        f" + (ratio-1.0)*{driver_float_literal(delta_z)}"
    )
    while driver.variables:
        driver.variables.remove(driver.variables[0])
    ratio = driver.variables.new()
    ratio.name = "ratio"
    ratio.type = "SINGLE_PROP"
    ratio.targets[0].id_type = "OBJECT"
    ratio.targets[0].id = dashboard
    ratio.targets[0].data_path = f'["{prop}"]'


def add_object_axis_driver(obj, axis_index, dashboard, prop, base, delta):
    obj[f"mharp_torso_height_base_location_{axis_index}"] = float(base)
    obj[f"mharp_torso_height_delta_location_{axis_index}"] = float(delta)
    try:
        obj.driver_remove("location", axis_index)
    except (TypeError, RuntimeError):
        pass
    fcurve = obj.driver_add("location", axis_index)
    driver = fcurve.driver
    driver.type = "SCRIPTED"
    driver.expression = (
        f"{driver_float_literal(base)}"
        f" + (ratio-1.0)*{driver_float_literal(delta)}"
    )
    while driver.variables:
        driver.variables.remove(driver.variables[0])
    ratio = driver.variables.new()
    ratio.name = "ratio"
    ratio.type = "SINGLE_PROP"
    ratio.targets[0].id_type = "OBJECT"
    ratio.targets[0].id = dashboard
    ratio.targets[0].data_path = f'["{prop}"]'


def add_torso_height_control_follow_drivers(mesh_obj, armature, dashboard, item):
    world_scale = average_matrix_scale(mesh_obj.matrix_world)
    _low_z, _high_z, torso_height = torso_height_data(mesh_obj, armature)
    delta_world = Vector((0.0, 0.0, torso_height * world_scale * float(item.get("driver_strength", 1.0))))
    driven = []
    for bone_name in TORSO_HEIGHT_CONTROL_FOLLOW_ROOTS:
        obj = control_object_for_bone(bone_name)
        if not obj:
            continue
        parent_matrix = obj.parent.matrix_world if obj.parent else Matrix.Identity(4)
        delta_local = parent_matrix.inverted().to_3x3() @ delta_world
        for axis_index, delta in enumerate((delta_local.x, delta_local.y, delta_local.z)):
            add_object_axis_driver(obj, axis_index, dashboard, "躯干高度", obj.location[axis_index], delta)
        driven.append(obj.name)
    return driven


def add_torso_height_object_drivers(mesh_obj, armature, dashboard, item):
    _low_z, _high_z, torso_height = torso_height_data(mesh_obj, armature)
    world_scale = average_matrix_scale(mesh_obj.matrix_world)
    delta_z = torso_height * world_scale * float(item.get("driver_strength", 1.0))
    driven = []
    for obj in bpy.data.objects:
        if obj.type != "MESH" or not obj.name.startswith("MH_Face_LOD"):
            continue
        add_object_z_driver(obj, dashboard, "躯干高度", delta_z)
        driven.append(obj.name)
    driven.extend(add_torso_height_control_follow_drivers(mesh_obj, armature, dashboard, item))
    return driven


def clear_torso_height_object_drivers():
    cleared = []
    for obj in bpy.data.objects:
        touched = False
        if obj.type == "MESH" and obj.name.startswith("MH_Face_LOD"):
            base_z = obj.get("mharp_base_location_z")
            if base_z is not None:
                obj.location.z = float(base_z)
            try:
                obj.driver_remove("location", 2)
                touched = True
            except (TypeError, RuntimeError):
                pass
            if "mharp_base_location_z" in obj:
                del obj["mharp_base_location_z"]
            if "mharp_torso_height_delta_z" in obj:
                del obj["mharp_torso_height_delta_z"]
        if obj.get("mharp_is_control_rig") or obj.get("mharp_target_bone") or obj.name.startswith(CONTROL_PREFIX):
            for axis_index in range(3):
                base_key = f"mharp_torso_height_base_location_{axis_index}"
                delta_key = f"mharp_torso_height_delta_location_{axis_index}"
                base_value = obj.get(base_key)
                if base_value is not None:
                    obj.location[axis_index] = float(base_value)
                try:
                    obj.driver_remove("location", axis_index)
                    touched = True
                except (TypeError, RuntimeError):
                    pass
                if base_key in obj:
                    del obj[base_key]
                if delta_key in obj:
                    del obj[delta_key]
        if touched:
            obj.update_tag()
            cleared.append(obj.name)
    return cleared


def build_shape_key(mesh_obj, armature, dashboard, item):
    ensure_basis_shape_key(mesh_obj)
    shape_name = f"MH_{safe_name(item['prop'])}"
    old = mesh_obj.data.shape_keys.key_blocks.get(shape_name)
    if old:
        mesh_obj.shape_key_remove(old)
    shape = mesh_obj.shape_key_add(name=shape_name, from_mix=False)
    shape.slider_min = -0.8
    shape.slider_max = 1.6

    basis = mesh_obj.data.shape_keys.key_blocks["Basis"]
    group_names = expanded_vertex_group_names(mesh_obj, item["bones"])
    follow_group_names = follow_vertex_group_names(mesh_obj, armature, item)
    group_lookup = vertex_group_index_lookup(mesh_obj, group_names)
    group_name_set = set(group_lookup.values())
    follow_group_lookup = vertex_group_index_lookup(mesh_obj, follow_group_names)
    follow_group_name_set = set(follow_group_lookup.values())
    all_group_lookup = {group.index: group.name for group in mesh_obj.vertex_groups}
    axis_cache = {}
    axis_arm = average_bone_axis(armature, item["axis_bones"])
    axis_world = (armature.matrix_world.to_3x3() @ axis_arm).normalized()
    axis_local = (mesh_obj.matrix_world.inverted().to_3x3() @ axis_world).normalized()
    center_world = average_bone_center_world(armature, item["axis_bones"])
    center_local = mesh_obj.matrix_world.inverted() @ center_world
    torso_low_z, torso_high_z, torso_height = torso_height_data(mesh_obj, armature)
    changed = 0

    for vert in mesh_obj.data.vertices:
        group_name, weight = best_weighted_group_for_vertex(vert, group_lookup)
        follow_group_name, follow_weight = best_weighted_group_for_vertex(vert, follow_group_lookup)
        primary_group_name, _primary_weight = best_weighted_group_for_vertex(vert, all_group_lookup)
        if item["kind"] == "width" and item["prop"] in {"胯部粗细", "腰部粗细", "胸部粗细"}:
            if not is_torso_width_vertex_group(primary_group_name):
                shape.data[vert.index].co = basis.data[vert.index].co
                continue
            weight = 1.0
            group_name = primary_group_name or (item["axis_bones"][0] if item.get("axis_bones") else group_name)
        if weight <= 0.0001 and follow_weight <= 0.0001 and item["kind"] != "vertical":
            shape.data[vert.index].co = basis.data[vert.index].co
            continue
        bone_name = group_name
        if group_name and group_name not in armature.data.bones:
            base, side = side_base_name(group_name)
            if side and f"{base}_{side}" in armature.data.bones:
                bone_name = f"{base}_{side}"
            elif base in armature.data.bones:
                bone_name = base
        local_axis = axis_local
        local_center = center_local
        bone = armature.data.bones.get(bone_name) if bone_name else None
        if bone:
            bone_axis_world = armature.matrix_world.to_3x3() @ (bone.tail_local - bone.head_local)
            if bone_axis_world.length > 1e-8:
                local_axis = (mesh_obj.matrix_world.inverted().to_3x3() @ bone_axis_world).normalized()
            local_center = mesh_obj.matrix_world.inverted() @ (armature.matrix_world @ ((bone.head_local + bone.tail_local) * 0.5))
        co = basis.data[vert.index].co.copy()
        rel = co - local_center

        if item["kind"] == "length":
            primary_role = length_primary_role(item["prop"], primary_group_name)
            if primary_role is None and primary_group_name in group_name_set:
                primary_role = "segment"
            elif primary_role is None and primary_group_name in follow_group_name_set:
                primary_role = "follow"
            if primary_role is None:
                shape.data[vert.index].co = basis.data[vert.index].co
                continue
            primary_is_follow = primary_role == "follow"
            delta = length_delta_for_vertex(
                mesh_obj,
                armature,
                dashboard,
                item,
                co,
                group_name,
                follow_group_name,
                weight,
                follow_weight,
                primary_is_follow,
                axis_cache,
            )
        elif item["kind"] == "vertical":
            torso_group = follow_group_name or group_name
            torso_weight = max(weight, follow_weight, 1.0 if torso_group else 0.0)
            factor = torso_height_factor(co, primary_group_name or torso_group, torso_weight, torso_low_z, torso_high_z, dashboard)
            if factor <= 0.0001:
                shape.data[vert.index].co = basis.data[vert.index].co
                continue
            delta = Vector((0.0, 0.0, torso_height * factor))
        else:
            if item["prop"] in {"胯部粗细", "腰部粗细", "胸部粗细"}:
                normal_local = Vector((vert.normal.x, vert.normal.y, vert.normal.z))
                delta, spatial_weight = torso_width_delta(mesh_obj, armature, dashboard, item, co, normal_local, primary_group_name)
                if spatial_weight <= 0.0001:
                    shape.data[vert.index].co = basis.data[vert.index].co
                    continue
                shape.data[vert.index].co = co + delta
                changed += 1
                continue
            axis_bone = axis_bone_for_group(armature, item, group_name)
            if item["prop"] in {"上臂粗细", "小臂粗细", "大腿粗细", "小腿粗细"}:
                if width_primary_role(item["prop"], primary_group_name) is None:
                    shape.data[vert.index].co = basis.data[vert.index].co
                    continue
                axis_bone = axis_bone_for_length_group(armature, item, group_name, primary_group_name)
            if axis_bone:
                local_center, local_axis, _bone_length = control_axis_data(mesh_obj, armature, axis_bone, axis_cache)
                rel = co - local_center
            projection = rel.dot(local_axis)
            perpendicular = rel - local_axis * projection
            if perpendicular.length < 1e-6:
                radial = Vector((vert.normal.x, vert.normal.y, vert.normal.z))
            else:
                radial = perpendicular.normalized()
            direction = radial
            if item["prop"] in {"上臂粗细", "小臂粗细"}:
                normal_mix = profile_param(dashboard, "上肢.粗细.法向混合")
                normal = Vector((vert.normal.x, vert.normal.y, vert.normal.z))
                normal = normal - local_axis * normal.dot(local_axis)
                if normal.length > 1e-6:
                    normal.normalize()
                else:
                    normal = radial
                direction = normalized_direction_blend(radial, normal, normal_mix)
            radius = max(perpendicular.length, 0.01)
            endpoint_fade = 1.0
            if item["prop"] in {"上臂粗细", "小臂粗细", "大腿粗细", "小腿粗细"} and axis_bone:
                side = vertex_group_side(group_name or "") or vertex_group_side(primary_group_name or "")
                head, fade_axis, bone_length = width_chain_axis_data(mesh_obj, armature, item, axis_bone, side, axis_cache)
                if bone_length > 1e-8:
                    t = clamp01((co - head).dot(fade_axis) / bone_length)
                    family = prop_limb_family(item["prop"])
                    endpoint = profile_param(dashboard, "四肢.粗细.骨末端衰减")
                    curve = profile_param(dashboard, f"{family}.粗细.骨末端衰减")
                    endpoint_fade = falloff_curve01(t, endpoint, curve)
            directional_bias = 1.0
            if item["prop"] == "胸部粗细":
                directional_bias = 1.15 if abs(direction.y) >= abs(direction.x) else 0.45
            elif item["prop"] == "腰部粗细":
                directional_bias = 1.2 if abs(direction.x) >= abs(direction.y) else 0.75
            delta = direction * radius * weight * endpoint_fade * directional_bias

        shape.data[vert.index].co = co + delta
        changed += 1

    add_shape_key_driver(mesh_obj, shape_name, dashboard, item)
    mesh_obj.data.update()
    if mesh_obj.data.shape_keys:
        mesh_obj.data.shape_keys.update_tag()
    return changed


def control_visual_delta_for_item(mesh_obj, armature, dashboard, item, body_co, bone_name, axis_cache):
    if item["kind"] == "length":
        role = length_primary_role(item["prop"], bone_name)
        if role is None:
            return Vector((0.0, 0.0, 0.0))
        return length_delta_for_vertex(
            mesh_obj,
            armature,
            dashboard,
            item,
            body_co,
            bone_name,
            bone_name,
            1.0,
            1.0,
            role == "follow",
            axis_cache,
        )
    if item["kind"] == "vertical":
        low_z, high_z, torso_height = torso_height_data(mesh_obj, armature)
        factor = torso_height_factor(body_co, bone_name, 1.0, low_z, high_z, dashboard)
        if factor <= 0.0001:
            return Vector((0.0, 0.0, 0.0))
        return Vector((0.0, 0.0, torso_height * factor))
    return Vector((0.0, 0.0, 0.0))


def rebuild_control_visual_shape_keys(mesh_obj, armature, dashboard):
    if not mesh_obj or not armature or not dashboard:
        return {"controls": 0, "shape_keys": 0}
    controls = [
        obj
        for obj in control_objects()
        if obj.type == "MESH" and obj.get("mharp_target_bone")
    ]
    if not controls:
        return {"controls": 0, "shape_keys": 0}

    body_world_to_local = mesh_obj.matrix_world.inverted()
    body_local_to_world_3x3 = mesh_obj.matrix_world.to_3x3()
    synced_controls = 0
    synced_shape_keys = 0
    items = [item for item in PROPORTION_DEFS if item["kind"] in {"length", "vertical"}]

    for control in controls:
        bone_name = str(control.get("mharp_target_bone") or "")
        if not bone_name:
            continue
        ensure_basis_shape_key(control)
        key_blocks = control.data.shape_keys.key_blocks
        for old_key in list(key_blocks)[1:]:
            if old_key.name.startswith(CONTROL_SYNC_SHAPE_PREFIX):
                control.shape_key_remove(old_key)
        basis = control.data.shape_keys.key_blocks["Basis"]
        control_world_to_local_3x3 = control.matrix_world.inverted().to_3x3()
        control_local_to_world = control.matrix_world
        control_shape_count = 0

        for item in items:
            shape_name = CONTROL_SYNC_SHAPE_PREFIX + safe_name(item["prop"])
            shape = control.shape_key_add(name=shape_name, from_mix=False)
            axis_cache = {}
            changed = 0
            for index, basis_vert in enumerate(basis.data):
                world_co = control_local_to_world @ basis_vert.co
                body_co = body_world_to_local @ world_co
                delta_body = control_visual_delta_for_item(mesh_obj, armature, dashboard, item, body_co, bone_name, axis_cache)
                if delta_body.length <= 1e-8:
                    shape.data[index].co = basis_vert.co
                    continue
                delta_world = body_local_to_world_3x3 @ delta_body
                shape.data[index].co = basis_vert.co + (control_world_to_local_3x3 @ delta_world)
                changed += 1
            if changed:
                add_control_visual_shape_driver(control, shape_name, dashboard, item)
                control_shape_count += 1
                synced_shape_keys += 1
            else:
                control.shape_key_remove(shape)

        if control_shape_count:
            synced_controls += 1
            control.data.update()

    return {"controls": synced_controls, "shape_keys": synced_shape_keys}


def sync_control_rig_proportion_follow(mesh_obj, armature, dashboard):
    visual_sync = rebuild_control_visual_shape_keys(mesh_obj, armature, dashboard)
    torso_item = torso_height_item_def()
    follow_controls = []
    if torso_item:
        follow_controls = add_torso_height_control_follow_drivers(mesh_obj, armature, dashboard, torso_item)
    visual_sync["follow_controls"] = follow_controls
    return visual_sync


def torso_width_items():
    return [item for item in PROPORTION_DEFS if item["prop"] in {"胸部粗细", "腰部粗细", "胯部粗细"}]


def torso_guide_defaults(mesh_obj, armature, dashboard):
    if not mesh_obj or not armature:
        return []
    _low_z, _high_z, torso_height = torso_height_data(mesh_obj, armature)
    plane_x = torso_symmetry_plane_x_local(mesh_obj, armature)
    smooth = profile_param(dashboard, "躯干.粗细.边界平滑") if dashboard else PROPORTION_PROFILE_PARAMS["躯干.粗细.边界平滑"]["default"]
    defaults = []
    for item in torso_width_items():
        center = average_axis_center_local(mesh_obj, armature, item["axis_bones"])
        unit = max(float(torso_height), 1.0)
        specs = torso_width_guide_specs(item["prop"], unit)
        local_centers = {}
        for spec in specs:
            local = center + Vector(spec["offset"])
            if spec.get("side") == "C":
                local.x = plane_x
            local_centers[spec["id"]] = local
        for spec in specs:
            local_center = local_centers[spec["id"]]
            if spec.get("mirror_of") and spec["mirror_of"] in local_centers:
                local_center = mirror_local_x(local_centers[spec["mirror_of"]], plane_x)
            defaults.append(
                {
                    "prop": item["prop"],
                    "spec": spec,
                    "local_center": local_center,
                    "world_center": mesh_obj.matrix_world @ local_center,
                    "soft": 1.0 + clamp01(smooth / 1.6) * 0.55,
                    "plane_x": plane_x,
                    "plane_world_x": (mesh_obj.matrix_world @ Vector((plane_x, 0.0, 0.0))).x,
                }
            )
    return defaults


def remove_location_drivers(obj):
    animation = obj.animation_data
    if not animation:
        return
    for fcurve in list(animation.drivers):
        if fcurve.data_path == "location":
            try:
                obj.driver_remove("location", fcurve.array_index)
            except TypeError:
                pass


def add_world_location_driver(obj, index, source, expression):
    fcurve = obj.driver_add("location", index)
    driver = fcurve.driver
    driver.type = "SCRIPTED"
    driver.expression = expression
    variable = driver.variables.new()
    variable.name = "src"
    variable.type = "TRANSFORMS"
    target = variable.targets[0]
    target.id = source
    target.transform_type = ("LOC_X", "LOC_Y", "LOC_Z")[index]
    target.transform_space = "WORLD_SPACE"


def apply_torso_guide_constraints(obj, spec, data):
    remove_location_drivers(obj)
    obj["mharp_torso_guide_side"] = spec.get("side", "")
    obj["mharp_torso_guide_mirror_of"] = spec.get("mirror_of", "")
    obj["mharp_torso_guide_is_ghost"] = bool(spec.get("mirror_of"))
    obj["mharp_torso_guide_is_center_locked"] = spec.get("side") == "C"
    if spec.get("mirror_of"):
        source = bpy.data.objects.get(torso_guide_object_name(spec["mirror_of"]))
        if source:
            plane_x_world = data["plane_world_x"]
            add_world_location_driver(obj, 0, source, f"{2.0 * plane_x_world:.9f}-src")
            add_world_location_driver(obj, 1, source, "src")
            add_world_location_driver(obj, 2, source, "src")
        obj.hide_select = True
        obj.lock_location = (True, True, True)
        obj.lock_rotation = (True, True, True)
        obj.lock_scale = (True, True, True)
        obj.display_type = "WIRE"
    elif spec.get("side") == "C":
        plane_x_world = data["world_center"].x
        fcurve = obj.driver_add("location", 0)
        fcurve.driver.type = "SCRIPTED"
        fcurve.driver.expression = f"{plane_x_world:.9f}"
        obj.hide_select = False
        obj.lock_location = (True, False, False)
        obj.lock_rotation = (True, True, True)
        obj.lock_scale = (True, True, True)
        obj.display_type = "TEXTURED"
    else:
        obj.hide_select = False
        obj.lock_location = (False, False, False)
        obj.lock_rotation = (True, True, True)
        obj.lock_scale = (True, True, True)
        obj.display_type = "TEXTURED"


def create_or_update_torso_guide_label(handle, spec, collection, language):
    name = torso_guide_label_object_name(spec["id"])
    label = bpy.data.objects.get(name)
    if label is None or label.type != "FONT":
        curve = bpy.data.curves.new(f"{name}_Curve", "FONT")
        curve.align_x = "CENTER"
        curve.align_y = "CENTER"
        curve.size = 0.055
        label = bpy.data.objects.new(name, curve)
        collection.objects.link(label)
    elif label.name not in collection.objects:
        collection.objects.link(label)
    label.data.body = torso_guide_label_text(spec["id"], language)
    label.data.align_x = "CENTER"
    label.data.align_y = "CENTER"
    label.data.size = 0.055
    label.parent = handle
    label.location = (0.0, 0.0, 0.105)
    label.rotation_euler = (math.radians(70.0), 0.0, 0.0)
    label.show_in_front = True
    label.hide_render = True
    label.hide_select = True
    label["mharp_torso_guide_label_for"] = spec["id"]
    material = ensure_material("MH_TorsoGuide_Text", (1.0, 1.0, 1.0, 1.0))
    if not label.data.materials:
        label.data.materials.append(material)
    return label


def torso_guide_label_objects():
    return [obj for obj in bpy.data.objects if obj.name.startswith(TORSO_GUIDE_LABEL_PREFIX)]


def apply_torso_guide_language(language):
    language = language if language in UI_TEXT else DEFAULT_INTERFACE_LANGUAGE
    labels = 0
    for obj in torso_guide_objects():
        guide_id = str(obj.get("mharp_torso_guide_id") or "")
        if not guide_id:
            continue
        obj["mharp_torso_guide_label"] = torso_guide_label_text(guide_id, language)
        label = bpy.data.objects.get(torso_guide_label_object_name(guide_id))
        if label and label.type == "FONT":
            label.data.body = torso_guide_label_text(guide_id, language)
            labels += 1
    return {"language": language, "labels": labels}


def create_or_update_torso_guides(mesh_obj, armature, dashboard, reset=False):
    collection = ensure_collection(TORSO_GUIDE_COLLECTION)
    collection.hide_render = True
    settings = getattr(bpy.context.scene, "mharp_settings", None)
    language = ui_language(settings) if settings else DEFAULT_INTERFACE_LANGUAGE
    created = 0
    updated = 0
    labels = 0
    for data in torso_guide_defaults(mesh_obj, armature, dashboard):
        spec = data["spec"]
        name = torso_guide_object_name(spec["id"])
        obj = bpy.data.objects.get(name)
        is_new = obj is None
        if obj is None:
            mesh = create_guide_mesh(f"{name}_Mesh")
            material = ensure_material(f"MH_TorsoGuide_{safe_name(data['prop'])}", spec.get("color", (0.9, 0.55, 0.2, 1.0)))
            mesh.materials.append(material)
            obj = bpy.data.objects.new(name, mesh)
            collection.objects.link(obj)
            created += 1
        else:
            if obj.name not in collection.objects:
                collection.objects.link(obj)
            updated += 1
            if reset:
                obj.location = data["world_center"]
        if is_new:
            obj.location = data["world_center"]
        elif reset:
            obj.location = data["world_center"]
        obj.show_in_front = True
        obj.hide_render = True
        obj["mharp_torso_guide_id"] = spec["id"]
        obj["mharp_torso_guide_label"] = torso_guide_label_text(spec["id"], language)
        obj["mharp_torso_guide_prop"] = data["prop"]
        obj["mharp_torso_guide_radii"] = tuple(float(v * data["soft"]) for v in spec["radii"])
        obj["mharp_torso_guide_direction"] = tuple(float(v) for v in spec["direction"])
        obj["mharp_torso_guide_strength"] = float(spec["strength"])
        obj["mharp_torso_guide_amplitude"] = float(spec["amplitude"])
        apply_torso_guide_constraints(obj, spec, data)
        create_or_update_torso_guide_label(obj, spec, collection, language)
        labels += 1
        obj.update_tag()
    reveal_collection_and_ancestors(collection)
    bpy.context.view_layer.update()
    return {"created": created, "updated": updated, "total": len(torso_guide_defaults(mesh_obj, armature, dashboard)), "labels": labels}


def torso_guide_objects():
    return [obj for obj in bpy.data.objects if obj.name.startswith(TORSO_GUIDE_PREFIX)]


def apply_torso_guide_visibility(mode):
    mode = mode if mode in {"HIDE", "SHOW"} else "SHOW"
    collection = bpy.data.collections.get(TORSO_GUIDE_COLLECTION)
    if collection:
        collection.hide_viewport = False
        collection.hide_render = True
        if mode == "SHOW":
            reveal_collection_and_ancestors(collection)
    hidden = mode == "HIDE"
    objects = torso_guide_objects()
    for obj in objects:
        obj.hide_viewport = False
        obj.hide_render = True
        obj.hide_set(hidden)
    for label in torso_guide_label_objects():
        label.hide_viewport = False
        label.hide_render = True
        label.hide_set(hidden)
    bpy.context.view_layer.update()
    return {"mode": mode, "guides": len(objects), "labels": len(torso_guide_label_objects())}


def unique_bpy_name(base, data_blocks):
    name = base
    index = 1
    while name in data_blocks:
        name = f"{base}.{index:03d}"
        index += 1
    return name


def dashboard_proportion_snapshot(dashboard):
    if not dashboard:
        return {}
    snapshot = {}
    for item in PROPORTION_DEFS:
        prop = item["prop"]
        if prop in dashboard:
            snapshot[prop] = float(dashboard.get(prop, 1.0))
    for prop in PROPORTION_PROFILE_PARAMS:
        if prop in dashboard:
            snapshot[prop] = float(dashboard.get(prop))
    return snapshot


def current_shape_value(dashboard, item):
    if not dashboard:
        return 0.0
    ratio = float(dashboard.get(item["prop"], 1.0))
    return (ratio - 1.0) * float(item.get("driver_strength", 1.0))


def point_proportion_delta_body_local(mesh_obj, armature, dashboard, bone_name, body_co, axis_cache=None):
    total = Vector((0.0, 0.0, 0.0))
    if not dashboard:
        return total
    axis_cache = axis_cache if axis_cache is not None else {}
    for item in PROPORTION_DEFS:
        if item["kind"] not in {"length", "vertical"}:
            continue
        value = current_shape_value(dashboard, item)
        if abs(value) <= 1e-8:
            continue
        if item["kind"] == "vertical" and (
            bone_name.startswith("clavicle") or is_torso_height_upper_follow_group(bone_name)
        ):
            _low_z, _high_z, torso_height = torso_height_data(mesh_obj, armature)
            delta = Vector((0.0, 0.0, torso_height))
        else:
            delta = control_visual_delta_for_item(mesh_obj, armature, dashboard, item, body_co, bone_name, axis_cache)
        if delta.length > 1e-8:
            total += delta * value
    return total


def armature_local_delta_from_body_delta(mesh_obj, armature, delta_body):
    delta_world = mesh_obj.matrix_world.to_3x3() @ delta_body
    return armature.matrix_world.inverted().to_3x3() @ delta_world


def adjusted_bone_endpoint_local(mesh_obj, armature, dashboard, bone_name, endpoint_local, axis_cache=None):
    body_co = mesh_obj.matrix_world.inverted() @ (armature.matrix_world @ endpoint_local)
    delta_body = point_proportion_delta_body_local(mesh_obj, armature, dashboard, bone_name, body_co, axis_cache)
    return endpoint_local + armature_local_delta_from_body_delta(mesh_obj, armature, delta_body)


def clear_pose_constraints_and_animation(armature_obj):
    armature_obj.animation_data_clear()
    for constraint in list(armature_obj.constraints):
        armature_obj.constraints.remove(constraint)
    if armature_obj.data:
        armature_obj.data.animation_data_clear()
    if armature_obj.pose:
        for pose_bone in armature_obj.pose.bones:
            pose_bone.matrix_basis.identity()
            for constraint in list(pose_bone.constraints):
                pose_bone.constraints.remove(constraint)


def duplicate_adjusted_rest_armature(mesh_obj, armature, dashboard, collection, tag):
    new_data = armature.data.copy()
    new_data.name = unique_bpy_name(f"MH_Advanced_{safe_name(armature.data.name)}_{tag}", bpy.data.armatures)
    new_armature = armature.copy()
    new_armature.data = new_data
    new_armature.name = unique_bpy_name(f"MH_Advanced_{safe_name(armature.name)}_{tag}", bpy.data.objects)
    collection.objects.link(new_armature)
    new_armature.matrix_world = armature.matrix_world.copy()
    new_armature.show_in_front = True
    new_armature.hide_viewport = False
    new_armature.hide_render = False
    new_armature.hide_set(False)
    reveal_collection_and_ancestors(collection)
    clear_pose_constraints_and_animation(new_armature)
    original_points = {
        bone.name: (bone.head_local.copy(), bone.tail_local.copy())
        for bone in armature.data.bones
    }
    adjusted_points = {}
    axis_cache = {}
    for bone_name, (head, tail) in original_points.items():
        adjusted_points[bone_name] = (
            adjusted_bone_endpoint_local(mesh_obj, armature, dashboard, bone_name, head, axis_cache),
            adjusted_bone_endpoint_local(mesh_obj, armature, dashboard, bone_name, tail, axis_cache),
        )
    previous_active = bpy.context.view_layer.objects.active
    previous_mode = bpy.context.object.mode if bpy.context.object else "OBJECT"
    if previous_mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    new_armature.select_set(True)
    bpy.context.view_layer.objects.active = new_armature
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        for edit_bone in new_armature.data.edit_bones:
            head, tail = adjusted_points.get(edit_bone.name, (None, None))
            if head is None or tail is None:
                continue
            edit_bone.head = head
            edit_bone.tail = tail
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
        if previous_active and previous_active.name in bpy.context.view_layer.objects:
            bpy.context.view_layer.objects.active = previous_active
    new_armature["mharp_advanced_baked_rest_armature"] = True
    new_armature["mharp_baked_source_armature"] = armature.name
    new_armature["mharp_baked_at"] = tag
    new_armature["mharp_baked_dashboard_json"] = json.dumps(dashboard_proportion_snapshot(dashboard), ensure_ascii=False)
    return new_armature


def copy_vertex_groups(source_obj, target_obj):
    while target_obj.vertex_groups:
        target_obj.vertex_groups.remove(target_obj.vertex_groups[0])
    for group in source_obj.vertex_groups:
        target_obj.vertex_groups.new(name=group.name)
    if len(source_obj.data.vertices) != len(target_obj.data.vertices):
        return {"copied": 0, "skipped": True}
    copied = 0
    for vertex in source_obj.data.vertices:
        for assignment in vertex.groups:
            source_group = source_obj.vertex_groups[assignment.group]
            target_group = target_obj.vertex_groups.get(source_group.name)
            if target_group:
                target_group.add([vertex.index], assignment.weight, "REPLACE")
                copied += 1
    return {"copied": copied, "skipped": False}


def create_static_baked_mesh_copy(source_obj, collection, tag, dashboard):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = source_obj.evaluated_get(depsgraph)
    mesh_name = unique_bpy_name(f"MH_Baked_{safe_name(source_obj.data.name)}_{tag}", bpy.data.meshes)
    new_mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph, preserve_all_data_layers=True)
    new_mesh.name = mesh_name
    if new_mesh.shape_keys:
        bpy.data.shape_keys.remove(new_mesh.shape_keys)
    if len(new_mesh.materials) == 0:
        for slot in source_obj.material_slots:
            if slot.material:
                new_mesh.materials.append(slot.material)
    obj_name = unique_bpy_name(f"MH_Baked_{safe_name(source_obj.name)}_{tag}", bpy.data.objects)
    new_obj = bpy.data.objects.new(obj_name, new_mesh)
    collection.objects.link(new_obj)
    new_obj.matrix_world = source_obj.matrix_world.copy()
    new_obj.display_type = source_obj.display_type
    new_obj.show_in_front = False
    new_obj.hide_viewport = False
    new_obj.hide_render = False
    new_obj.animation_data_clear()
    new_mesh.animation_data_clear()
    new_obj["mharp_baked_static_copy"] = True
    new_obj["mharp_baked_source_object"] = source_obj.name
    new_obj["mharp_baked_at"] = tag
    new_obj["mharp_baked_dashboard_json"] = json.dumps(dashboard_proportion_snapshot(dashboard), ensure_ascii=False)
    return new_obj


def create_advanced_baked_mesh_copy(source_obj, collection, tag, dashboard, armature_obj=None):
    new_obj = create_static_baked_mesh_copy(source_obj, collection, tag, dashboard)
    new_obj.name = unique_bpy_name(f"MH_Advanced_{safe_name(source_obj.name)}_{tag}", bpy.data.objects)
    new_obj.data.name = unique_bpy_name(f"MH_Advanced_{safe_name(source_obj.data.name)}_{tag}", bpy.data.meshes)
    group_copy = copy_vertex_groups(source_obj, new_obj)
    if armature_obj and source_obj.name.startswith("MH_Body"):
        modifier = new_obj.modifiers.new("MH_Advanced_Rest_Armature", "ARMATURE")
        modifier.object = armature_obj
        modifier.use_vertex_groups = True
        preserve_parent(new_obj, armature_obj)
    new_obj["mharp_advanced_baked_mesh"] = True
    new_obj["mharp_vertex_group_copy_json"] = json.dumps(group_copy, ensure_ascii=False)
    return new_obj


def ensure_object_mode():
    try:
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass


def cloth_binding_targets(context, source_body):
    targets = []
    for obj in context.selected_objects:
        if obj.type != "MESH" or obj == source_body:
            continue
        if obj.name.startswith(("MH_Body", "MH_Face", CONTROL_PREFIX, TORSO_GUIDE_PREFIX, TORSO_GUIDE_LABEL_PREFIX)):
            continue
        if obj.get("mharp_is_control_rig") or obj.get("mharp_baked_static_copy") or obj.get("mharp_advanced_baked_mesh"):
            continue
        targets.append(obj)
    return targets


def remove_source_named_vertex_groups(source_obj, target_obj):
    source_names = {group.name for group in source_obj.vertex_groups}
    removed = 0
    for group in list(target_obj.vertex_groups):
        if group.name in source_names:
            target_obj.vertex_groups.remove(group)
            removed += 1
    created = 0
    for group in source_obj.vertex_groups:
        if target_obj.vertex_groups.get(group.name) is None:
            target_obj.vertex_groups.new(name=group.name)
            created += 1
    return {"removed": removed, "created": created}


def set_modifier_enum(modifier, property_name, values):
    for value in values:
        try:
            setattr(modifier, property_name, value)
            return value
        except Exception:
            continue
    return None


def configure_weight_transfer_modifier(modifier, source_body):
    modifier.object = source_body
    modifier.use_vert_data = True
    modifier.use_edge_data = False
    modifier.use_loop_data = False
    modifier.use_poly_data = False
    modifier.data_types_verts = {"VGROUP_WEIGHTS"}
    set_modifier_enum(modifier, "vert_mapping", ("POLYINTERP_NEAREST", "POLY_NEAREST", "NEAREST"))
    set_modifier_enum(modifier, "layers_vgroup_select_src", ("ALL", "BONE_DEFORM"))
    set_modifier_enum(modifier, "layers_vgroup_select_dst", ("NAME", "INDEX"))
    set_modifier_enum(modifier, "mix_mode", ("REPLACE",))
    modifier.mix_factor = 1.0
    if hasattr(modifier, "use_object_transform"):
        modifier.use_object_transform = True
    if hasattr(modifier, "use_max_distance"):
        modifier.use_max_distance = False


def move_modifier_before_armatures(target_obj, modifier):
    try:
        modifier_index = target_obj.modifiers.find(modifier.name)
        armature_indexes = [
            index
            for index, item in enumerate(target_obj.modifiers)
            if item.type == "ARMATURE" and item.name != modifier.name
        ]
        if modifier_index >= 0 and armature_indexes and modifier_index > min(armature_indexes):
            target_obj.modifiers.move(modifier_index, min(armature_indexes))
            return True
    except Exception:
        pass
    return False


def apply_modifier_on_object(context, obj, modifier_name):
    selected = list(context.selected_objects)
    active = context.view_layer.objects.active
    ensure_object_mode()
    try:
        reveal_object_and_collections(obj)
        obj.hide_select = False
        obj.hide_viewport = False
        try:
            obj.hide_set(False)
        except Exception:
            pass
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        context.view_layer.objects.active = obj
        context.view_layer.update()
        result = bpy.ops.object.modifier_apply(modifier=modifier_name)
        return "FINISHED" in result
    except Exception:
        print(traceback.format_exc())
        return False
    finally:
        try:
            bpy.ops.object.select_all(action="DESELECT")
            for item in selected:
                if item.name in bpy.data.objects:
                    item.select_set(True)
            if active and active.name in bpy.data.objects:
                context.view_layer.objects.active = active
        except Exception:
            pass


def normalize_vertex_groups_on_object(context, obj):
    selected = list(context.selected_objects)
    active = context.view_layer.objects.active
    ensure_object_mode()
    try:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        context.view_layer.objects.active = obj
        result = bpy.ops.object.vertex_group_normalize_all(lock_active=False)
        return "FINISHED" in result
    except Exception:
        return False
    finally:
        try:
            bpy.ops.object.select_all(action="DESELECT")
            for item in selected:
                if item.name in bpy.data.objects:
                    item.select_set(True)
            if active and active.name in bpy.data.objects:
                context.view_layer.objects.active = active
        except Exception:
            pass


def body_deform_group_names(source_body):
    if not source_body or source_body.type != "MESH":
        return []
    return [group.name for group in source_body.vertex_groups]


def vertex_group_total_weight(obj, group_name):
    group = obj.vertex_groups.get(group_name) if obj and obj.type == "MESH" else None
    if group is None:
        return 0.0
    total = 0.0
    for vertex in obj.data.vertices:
        for assignment in vertex.groups:
            if assignment.group == group.index:
                total += float(assignment.weight)
                break
    return total


def has_nonzero_weights(obj, group_names, epsilon=1e-6):
    return any(vertex_group_total_weight(obj, name) > epsilon for name in group_names)


def evaluated_vertex_world_positions(obj):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    try:
        if len(evaluated_mesh.vertices) == len(obj.data.vertices):
            return [evaluated.matrix_world @ vertex.co for vertex in evaluated_mesh.vertices]
    finally:
        evaluated.to_mesh_clear()
    return [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]


def source_vertex_weight_map(source_body, vertex_index, group_names):
    weights = {}
    vertex = source_body.data.vertices[vertex_index]
    allowed = set(group_names)
    for assignment in vertex.groups:
        group = source_body.vertex_groups[assignment.group]
        if group.name in allowed and assignment.weight > 1e-6:
            weights[group.name] = float(assignment.weight)
    return weights


def blended_source_weights(source_body, nearest_items, group_names):
    if not nearest_items:
        return {}
    blended = {}
    total_factor = 0.0
    for _position, source_index, distance in nearest_items:
        factor = 1.0 / max(float(distance), 1e-5)
        total_factor += factor
        for group_name, weight in source_vertex_weight_map(source_body, source_index, group_names).items():
            blended[group_name] = blended.get(group_name, 0.0) + weight * factor
    if total_factor <= 1e-8:
        return {}
    total_weight = 0.0
    for group_name in list(blended.keys()):
        value = blended[group_name] / total_factor
        if value <= 1e-6:
            del blended[group_name]
            continue
        blended[group_name] = value
        total_weight += value
    if total_weight <= 1e-8:
        return {}
    return {group_name: weight / total_weight for group_name, weight in blended.items()}


def clear_target_group_weights(target_obj, group_names):
    indices = [vertex.index for vertex in target_obj.data.vertices]
    if not indices:
        return
    for name in group_names:
        group = target_obj.vertex_groups.get(name)
        if group is None:
            continue
        try:
            group.remove(indices)
        except Exception:
            pass


def transfer_body_weights_to_cloth(source_body, target_obj, samples_per_vertex=4):
    group_names = body_deform_group_names(source_body)
    if not group_names:
        return {"assigned_vertices": 0, "created_groups": 0, "group_count": 0, "samples_per_vertex": 0}
    created = 0
    for name in group_names:
        if target_obj.vertex_groups.get(name) is None:
            target_obj.vertex_groups.new(name=name)
            created += 1

    source_positions = evaluated_vertex_world_positions(source_body)
    target_positions = evaluated_vertex_world_positions(target_obj)
    if not source_positions or not target_positions:
        return {"assigned_vertices": 0, "created_groups": created, "group_count": len(group_names), "samples_per_vertex": 0}

    tree = KDTree(len(source_positions))
    for index, position in enumerate(source_positions):
        tree.insert(position, index)
    tree.balance()

    clear_target_group_weights(target_obj, group_names)
    assigned_vertices = 0
    sample_count = max(1, min(int(samples_per_vertex or 1), len(source_positions)))
    for vertex_index, position in enumerate(target_positions):
        weights = blended_source_weights(source_body, tree.find_n(position, sample_count), group_names)
        if not weights:
            continue
        assigned_vertices += 1
        for group_name, weight in weights.items():
            target_obj.vertex_groups[group_name].add([vertex_index], weight, "REPLACE")
    target_obj.data.update()
    target_obj["mharp_cloth_weights_baked_from_body"] = True
    target_obj["mharp_cloth_weights_baked_at"] = timestamp()
    return {
        "assigned_vertices": assigned_vertices,
        "created_groups": created,
        "group_count": len(group_names),
        "samples_per_vertex": sample_count,
    }


def modifier_targets_object(modifier, target_obj):
    for attribute in ("object", "target"):
        if hasattr(modifier, attribute) and getattr(modifier, attribute) == target_obj:
            return True
    return False


def live_weight_mapping_modifiers(target_obj, source_body):
    modifiers = []
    for modifier in target_obj.modifiers:
        if modifier.type != "DATA_TRANSFER":
            continue
        if modifier.name.startswith("MH_Cloth_Weight_Projection") or modifier_targets_object(modifier, source_body):
            modifiers.append(modifier)
    return modifiers


def remove_live_weight_mapping_modifiers(target_obj, source_body):
    removed = []
    for modifier in list(live_weight_mapping_modifiers(target_obj, source_body)):
        removed.append(modifier.name)
        target_obj.modifiers.remove(modifier)
    return removed


def bake_cloth_weights_for_paint(context, source_body, target_obj, bone_name):
    if not source_body or source_body.type != "MESH":
        return {"baked": False, "reason": "missing_source_body"}
    group_names = body_deform_group_names(source_body)
    if not group_names:
        return {"baked": False, "reason": "source_body_has_no_groups"}

    live_modifiers = [modifier.name for modifier in live_weight_mapping_modifiers(target_obj, source_body)]
    applied_modifiers = []
    for modifier_name in list(live_modifiers):
        if target_obj.modifiers.get(modifier_name) and apply_modifier_on_object(context, target_obj, modifier_name):
            applied_modifiers.append(modifier_name)

    needs_manual_transfer = (
        not target_obj.get("mharp_cloth_weights_baked_from_body")
        or not has_nonzero_weights(target_obj, group_names)
    )
    manual_transfer = {"assigned_vertices": 0, "created_groups": 0, "group_count": len(group_names)}
    if needs_manual_transfer:
        manual_transfer = transfer_body_weights_to_cloth(source_body, target_obj)

    removed_modifiers = remove_live_weight_mapping_modifiers(target_obj, source_body)
    normalized = normalize_vertex_groups_on_object(context, target_obj)
    active_total = vertex_group_total_weight(target_obj, bone_name)
    return {
        "baked": bool(needs_manual_transfer or applied_modifiers or removed_modifiers),
        "manual_transfer": manual_transfer,
        "applied_modifiers": applied_modifiers,
        "removed_modifiers": removed_modifiers,
        "normalized": normalized,
        "active_group_weight": active_total,
    }


def ensure_cloth_armature_modifier(target_obj, armature_obj):
    removed = 0
    modifier = None
    for old_modifier in list(target_obj.modifiers):
        if old_modifier.type != "ARMATURE":
            continue
        if old_modifier.object == armature_obj and modifier is None:
            modifier = old_modifier
            modifier.name = "MH_Cloth_Armature"
            continue
        target_obj.modifiers.remove(old_modifier)
        removed += 1
    if modifier is None:
        modifier = target_obj.modifiers.new("MH_Cloth_Armature", "ARMATURE")
    modifier.object = armature_obj
    modifier.use_vertex_groups = True
    return {"modifier": modifier, "removed": removed}


def body_driver_armature(source_body, settings):
    for modifier in source_body.modifiers:
        if modifier.type == "ARMATURE" and modifier.object and modifier.object.type == "ARMATURE":
            return modifier.object
    return get_armature(getattr(settings, "armature_name", "MH_Body_Root"))


def detach_stale_cloth_parent(target_obj, armature_obj):
    if target_obj.parent != armature_obj:
        return False
    if not target_obj.get("mharp_cloth_bound_to_body"):
        return False
    detach_keep_world(target_obj)
    return True


def bind_cloth_to_body(context, source_body, armature_obj, target_obj):
    detached_parent = detach_stale_cloth_parent(target_obj, armature_obj)
    group_result = remove_source_named_vertex_groups(source_body, target_obj)
    removed_mapping_modifiers = []
    removed_mapping_modifiers.extend(remove_live_weight_mapping_modifiers(target_obj, source_body))
    direct_transfer = transfer_body_weights_to_cloth(source_body, target_obj)
    removed_mapping_modifiers.extend(remove_live_weight_mapping_modifiers(target_obj, source_body))
    normalized = normalize_vertex_groups_on_object(context, target_obj)
    armature_result = ensure_cloth_armature_modifier(target_obj, armature_obj)
    armature_modifier = armature_result["modifier"]
    target_obj["mharp_cloth_bound_to_body"] = True
    target_obj["mharp_cloth_source_body"] = source_body.name
    target_obj["mharp_cloth_armature"] = armature_obj.name
    target_obj["mharp_cloth_weight_transfer_applied"] = False
    target_obj["mharp_cloth_direct_weights_applied"] = bool(direct_transfer["assigned_vertices"])
    target_obj["mharp_cloth_parent_policy"] = "modifier_only"
    return {
        "object": target_obj.name,
        "removed_groups": group_result["removed"],
        "created_groups": group_result["created"],
        "transfer_applied": False,
        "direct_weight_transfer": direct_transfer,
        "manual_transfer": direct_transfer,
        "removed_mapping_modifiers": removed_mapping_modifiers,
        "normalized": normalized,
        "armature_modifier": armature_modifier.name,
        "removed_armature_modifiers": armature_result["removed"],
        "detached_parent": detached_parent,
    }


def bind_selected_clothes_to_body(context, settings):
    source_body = find_body_mesh(settings)
    if not source_body or source_body.type != "MESH":
        raise RuntimeError("找不到可用于投射权重的身体网格")
    if not source_body.vertex_groups:
        raise RuntimeError(f"身体网格没有可投射的顶点组: {source_body.name}")
    armature = body_driver_armature(source_body, settings)
    if not armature:
        raise RuntimeError("找不到身体骨架")
    targets = cloth_binding_targets(context, source_body)
    if not targets:
        raise RuntimeError("请先选中要绑定的衣服/装备网格")
    results = [bind_cloth_to_body(context, source_body, armature, target) for target in targets]
    return {
        "source_body": source_body.name,
        "armature": armature.name,
        "targets": results,
        "count": len(results),
        "applied_count": sum(1 for item in results if item["direct_weight_transfer"]["assigned_vertices"] > 0),
        "direct_weight_vertices": sum(item["direct_weight_transfer"]["assigned_vertices"] for item in results),
        "detached_parent_count": sum(1 for item in results if item["detached_parent"]),
        "removed_armature_modifier_count": sum(item["removed_armature_modifiers"] for item in results),
    }


def control_target_bone_name(obj):
    if not obj:
        return ""
    return str(obj.get("mharp_target_bone") or "")


def selected_control_for_weight_paint(context):
    active = context.view_layer.objects.active
    if control_target_bone_name(active):
        return active
    controls = [obj for obj in context.selected_objects if control_target_bone_name(obj)]
    if len(controls) == 1:
        return controls[0]
    if not controls:
        raise RuntimeError("请同时选中衣服网格和一个ControlRig手柄")
    raise RuntimeError("请只选中一个ControlRig手柄作为要修的骨骼")


def is_cloth_weight_paint_mesh(obj, source_body=None):
    if not obj or obj.type != "MESH" or obj == source_body:
        return False
    if obj.name.startswith(("MH_Body", "MH_Face", CONTROL_PREFIX, TORSO_GUIDE_PREFIX, TORSO_GUIDE_LABEL_PREFIX)):
        return False
    if obj.get("mharp_is_control_rig") or obj.get("mharp_baked_static_copy") or obj.get("mharp_advanced_baked_mesh"):
        return False
    return True


def selected_cloth_for_weight_paint(context, source_body):
    active = context.view_layer.objects.active
    if is_cloth_weight_paint_mesh(active, source_body):
        return active
    meshes = [obj for obj in context.selected_objects if is_cloth_weight_paint_mesh(obj, source_body)]
    if len(meshes) == 1:
        return meshes[0]
    if not meshes:
        raise RuntimeError("请同时选中要修的衣服网格")
    raise RuntimeError("请只选中一个要进入权重绘制的衣服网格")


def enter_cloth_weight_paint_from_control(context, settings):
    source_body = find_body_mesh(settings)
    control = selected_control_for_weight_paint(context)
    bone_name = control_target_bone_name(control)
    if not bone_name:
        raise RuntimeError("选中的ControlRig手柄没有对应骨骼")
    target = selected_cloth_for_weight_paint(context, source_body)
    bake_result = bake_cloth_weights_for_paint(context, source_body, target, bone_name)
    group = target.vertex_groups.get(bone_name)
    if group is None:
        group = target.vertex_groups.new(name=bone_name)
    target.vertex_groups.active_index = group.index

    armature = body_driver_armature(source_body, settings) if source_body and source_body.type == "MESH" else None
    if armature:
        ensure_cloth_armature_modifier(target, armature)

    ensure_object_mode()
    reveal_object_and_collections(target)
    reveal_object_and_collections(control)
    target.hide_select = False
    control.hide_select = False
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    control.select_set(True)
    context.view_layer.objects.active = target
    context.view_layer.update()
    if context.view_layer.objects.active != target:
        raise RuntimeError(f"无法把衣服设为活动对象: {target.name}")
    mode_result = bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
    if "FINISHED" not in mode_result:
        raise RuntimeError(f"Blender没有进入Weight Paint: {mode_result}")
    target["mharp_weight_paint_bone"] = bone_name
    target["mharp_weight_paint_control"] = control.name
    return {
        "object": target.name,
        "control": control.name,
        "bone": bone_name,
        "group": group.name,
        "armature": armature.name if armature else "",
        "bake": bake_result,
    }


def object_in_active_view_layer(context, obj):
    return any(item == obj for item in context.view_layer.objects)


def activate_object_for_mode(context, obj):
    reveal_object_and_collections(obj)
    obj.hide_select = False
    obj.hide_viewport = False
    obj.hide_render = False
    try:
        obj.hide_set(False)
    except Exception:
        pass
    if obj.type == "ARMATURE":
        try:
            for bone in obj.data.bones:
                bone.hide = False
                bone.hide_select = False
        except Exception:
            pass
    context.view_layer.update()
    if not object_in_active_view_layer(context, obj):
        raise RuntimeError(f"当前View Layer里找不到可激活对象: {obj.name}")
    try:
        if context.view_layer.objects.active and bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    context.view_layer.objects.active = obj
    context.view_layer.update()
    if context.view_layer.objects.active != obj:
        raise RuntimeError(f"无法把对象设为活动对象: {obj.name}")
    return obj


def control_map_for_armature(armature):
    controls = {}
    if not armature or not armature.pose:
        return controls
    for control in control_objects():
        bone_name = str(control.get("mharp_target_bone") or "")
        if bone_name and bone_name in armature.pose.bones:
            controls[bone_name] = control
    return controls


def capture_pose_bone_matrices(armature):
    bpy.context.view_layer.update()
    return {pose_bone.name: pose_bone.matrix.copy() for pose_bone in armature.pose.bones}


def pose_bone_depth(pose_bone):
    depth = 0
    bone = pose_bone.bone
    while bone.parent:
        depth += 1
        bone = bone.parent
    return depth


def set_pose_bone_matrices(armature, matrices):
    for pose_bone in sorted(armature.pose.bones, key=pose_bone_depth):
        matrix = matrices.get(pose_bone.name)
        if matrix is not None:
            pose_bone.matrix = matrix
    bpy.context.view_layer.update()


def armature_driven_meshes(armature, source_body=None):
    meshes = []
    seen = set()
    if source_body and source_body.type == "MESH":
        meshes.append(source_body)
        seen.add(source_body.name)
    for obj in bpy.data.objects:
        if obj.type != "MESH" or obj.name in seen:
            continue
        for modifier in obj.modifiers:
            if modifier.type == "ARMATURE" and modifier.object == armature and modifier.show_viewport:
                meshes.append(obj)
                seen.add(obj.name)
                break
    return meshes


def capture_evaluated_mesh_coordinates(mesh_obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = mesh_obj.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    try:
        if len(evaluated_mesh.vertices) != len(mesh_obj.data.vertices):
            return None
        to_original_local = mesh_obj.matrix_world.inverted() @ evaluated.matrix_world
        return [to_original_local @ vertex.co for vertex in evaluated_mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def capture_visual_mesh_states(meshes):
    states = {}
    bpy.context.view_layer.update()
    for mesh_obj in meshes:
        coords = capture_evaluated_mesh_coordinates(mesh_obj)
        if coords is not None:
            states[mesh_obj.name] = coords
    return states


def write_mesh_coordinates(mesh_obj, coords):
    if len(coords) != len(mesh_obj.data.vertices):
        return False
    shape_keys = mesh_obj.data.shape_keys
    if shape_keys and shape_keys.key_blocks:
        for key_block in shape_keys.key_blocks:
            if len(key_block.data) != len(coords):
                return False
            for point, coord in zip(key_block.data, coords):
                point.co = coord
    else:
        for vertex, coord in zip(mesh_obj.data.vertices, coords):
            vertex.co = coord
    mesh_obj.data.update()
    return True


def restore_visual_mesh_states(states):
    restored = 0
    skipped = []
    for name, coords in states.items():
        mesh_obj = bpy.data.objects.get(name)
        if mesh_obj and mesh_obj.type == "MESH" and write_mesh_coordinates(mesh_obj, coords):
            restored += 1
        else:
            skipped.append(name)
    bpy.context.view_layer.update()
    return restored, skipped


def apply_current_body_pose_as_rest(context, settings):
    source_body = find_body_mesh(settings)
    armature = body_driver_armature(source_body, settings) if source_body else get_armature(getattr(settings, "armature_name", "MH_Body_Root"))
    if not armature or armature.type != "ARMATURE":
        raise RuntimeError("找不到可应用Rest Pose的身体骨架")

    selected = list(context.selected_objects)
    active = context.view_layer.objects.active
    previous_mode = context.object.mode if context.object else "OBJECT"
    if getattr(settings, "make_backup", False):
        make_backup_if_saved()
    context.view_layer.update()
    try:
        activate_object_for_mode(context, armature)
        bpy.ops.object.mode_set(mode="POSE")
        controls = control_map_for_armature(armature)
        driven_meshes = armature_driven_meshes(armature, source_body)
        visual_mesh_states = capture_visual_mesh_states(driven_meshes)
        current_pose_matrices = capture_pose_bone_matrices(armature)
        removed_constraints = clear_control_constraints(armature)
        set_pose_bone_matrices(armature, current_pose_matrices)
        result = bpy.ops.pose.armature_apply(selected=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        if "FINISHED" not in result:
            raise RuntimeError(f"Blender没有完成Apply Pose as Rest: {result}")
        baked_mesh_count, skipped_meshes = restore_visual_mesh_states(visual_mesh_states)
        restored_constraints = add_control_constraints(armature, controls) if controls else 0
        context.view_layer.update()
        armature["mharp_pose_applied_as_rest_at"] = timestamp()
        if source_body:
            source_body["mharp_pose_applied_as_rest_armature"] = armature.name
        result = {
            "armature": armature.name,
            "body": source_body.name if source_body else "",
            "timestamp": armature["mharp_pose_applied_as_rest_at"],
            "baked_control_constraints": removed_constraints,
            "restored_control_constraints": restored_constraints,
            "control_count": len(controls),
            "baked_mesh_count": baked_mesh_count,
            "skipped_meshes": skipped_meshes,
        }
        context.scene["mharp_pose_applied_as_rest"] = result
        if getattr(settings, "hide_source_armature", False):
            hide_deform_rigs(armature, getattr(settings, "hide_non_lod0", True))
        return result
    finally:
        try:
            if context.view_layer.objects.active and bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action="DESELECT")
            for obj in selected:
                if obj.name in bpy.data.objects:
                    obj.select_set(True)
            if active and active.name in bpy.data.objects:
                context.view_layer.objects.active = active
        except Exception:
            pass


def proportion_shape_keys_missing(mesh_obj):
    if not mesh_obj or mesh_obj.type != "MESH" or mesh_obj.data.shape_keys is None:
        return True
    key_blocks = mesh_obj.data.shape_keys.key_blocks
    return any(f"MH_{safe_name(item['prop'])}" not in key_blocks for item in PROPORTION_DEFS)


def ensure_proportion_applied_and_rig_synced(settings):
    armature = get_armature(getattr(settings, "armature_name", "MH_Body_Root"))
    mesh_obj = find_body_mesh(settings)
    if getattr(settings, "proportion_lod0_only", False) and mesh_obj and not mesh_obj.name.startswith("MH_Body_LOD0"):
        lod0_mesh = bpy.data.objects.get("MH_Body_LOD0")
        if lod0_mesh and lod0_mesh.type == "MESH":
            mesh_obj = lod0_mesh
    if not armature or not mesh_obj or mesh_obj.type != "MESH":
        return {"rebuilt": False, "synced": False, "reason": "missing_body_or_armature"}
    dashboard = create_dashboard()
    dirty_params, _snapshot_missing = dirty_profile_params(dashboard)
    needs_rebuild = bool(dirty_params) or proportion_shape_keys_missing(mesh_obj)
    total_changed = 0
    added_face_drivers = []
    cleared_face_drivers = []
    if needs_rebuild:
        cleared_face_drivers = clear_torso_height_object_drivers()
        for item in PROPORTION_DEFS:
            total_changed += build_shape_key(mesh_obj, armature, dashboard, item)
            if item["kind"] == "vertical":
                added_face_drivers = add_torso_height_object_drivers(mesh_obj, armature, dashboard, item)
        record_profile_build_snapshot(dashboard)
    visual_sync = {"controls": 0, "shape_keys": 0, "follow_controls": []}
    if needs_rebuild or (bool(control_objects()) and not has_control_visual_sync_shape_keys()):
        visual_sync = sync_control_rig_proportion_follow(mesh_obj, armature, dashboard)
    bpy.context.scene["mharp_auto_apply_before_bake"] = {
        "rebuilt": needs_rebuild,
        "dirty_params": dirty_params,
        "changed_vertices": total_changed,
        "cleared_face_drivers": cleared_face_drivers,
        "added_face_drivers": added_face_drivers,
        "visual_sync": visual_sync,
    }
    return {
        "rebuilt": needs_rebuild,
        "synced": bool(visual_sync.get("controls") or visual_sync.get("shape_keys") or visual_sync.get("follow_controls")),
        "changed_vertices": total_changed,
        "dirty_params": dirty_params,
        "visual_sync": visual_sync,
    }


def bake_current_proportion_static_copy(settings):
    ensure_proportion_applied_and_rig_synced(settings)
    body = find_body_mesh(settings)
    face = find_face_lod0_mesh()
    targets = []
    if body and body.type == "MESH":
        targets.append(body)
    if face and face.type == "MESH" and face not in targets:
        targets.append(face)
    if not targets:
        raise RuntimeError("找不到可固化的 Body/Face LOD0 网格")
    dashboard = bpy.data.objects.get(DASHBOARD_NAME)
    collection = ensure_collection(BAKED_PROPORTION_COLLECTION)
    collection.hide_viewport = False
    collection.hide_render = False
    tag = timestamp()
    baked = [create_static_baked_mesh_copy(obj, collection, tag, dashboard) for obj in targets]
    reveal_collection_and_ancestors(collection)
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in baked:
        obj.select_set(True)
        obj.hide_set(False)
    bpy.context.view_layer.objects.active = baked[0]
    bpy.context.view_layer.update()
    return {
        "tag": tag,
        "objects": [obj.name for obj in baked],
        "sources": [obj.get("mharp_baked_source_object", "") for obj in baked],
        "vertices": sum(len(obj.data.vertices) for obj in baked),
        "shape_key_counts": {
            obj.name: (len(obj.data.shape_keys.key_blocks) if obj.data.shape_keys else 0)
            for obj in baked
        },
        "collection": collection.name,
    }


def bake_current_proportion_advanced_copy(settings):
    ensure_proportion_applied_and_rig_synced(settings)
    body = find_body_mesh(settings)
    face = find_face_lod0_mesh()
    armature = get_armature(getattr(settings, "armature_name", "MH_Body_Root"))
    if not body or body.type != "MESH":
        raise RuntimeError("找不到可固化的 Body LOD0 网格")
    if not armature or armature.type != "ARMATURE":
        raise RuntimeError("找不到可固化的身体骨架")
    dashboard = bpy.data.objects.get(DASHBOARD_NAME)
    if not dashboard:
        raise RuntimeError("需要先生成体型调节器")
    collection = ensure_collection(ADVANCED_BAKED_COLLECTION)
    collection.hide_viewport = False
    collection.hide_render = False
    tag = timestamp()
    new_armature = duplicate_adjusted_rest_armature(body, armature, dashboard, collection, tag)
    baked_body = create_advanced_baked_mesh_copy(body, collection, tag, dashboard, new_armature)
    baked = [baked_body]
    if face and face.type == "MESH":
        baked.append(create_advanced_baked_mesh_copy(face, collection, tag, dashboard, None))
    reveal_collection_and_ancestors(collection)
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    new_armature.select_set(True)
    baked_body.select_set(True)
    bpy.context.view_layer.objects.active = new_armature
    bpy.context.view_layer.update()
    moved_bones = 0
    max_bone_delta = 0.0
    for bone in armature.data.bones:
        new_bone = new_armature.data.bones.get(bone.name)
        if not new_bone:
            continue
        delta = max((new_bone.head_local - bone.head_local).length, (new_bone.tail_local - bone.tail_local).length)
        if delta > 1e-7:
            moved_bones += 1
            max_bone_delta = max(max_bone_delta, delta)
    return {
        "tag": tag,
        "armature": new_armature.name,
        "objects": [obj.name for obj in baked],
        "sources": [obj.get("mharp_baked_source_object", "") for obj in baked],
        "vertices": sum(len(obj.data.vertices) for obj in baked),
        "body_vertex_groups": len(baked_body.vertex_groups),
        "body_modifiers": [modifier.type for modifier in baked_body.modifiers],
        "moved_bones": moved_bones,
        "max_bone_delta": max_bone_delta,
        "collection": collection.name,
    }


def apply_control_rig_thickness(settings, armature):
    if not armature:
        return {"controls": 0, "shape_keys": 0}
    thickness = control_thickness_scale(getattr(settings, "control_rig_thickness", "LARGE"))
    handle_display_scale = average_matrix_scale(armature.matrix_world)
    controls = [obj for obj in control_objects() if obj.type == "MESH" and obj.get("mharp_target_bone")]
    updated = 0
    for obj in controls:
        bone_name = str(obj.get("mharp_target_bone") or "")
        bone = armature.data.bones.get(bone_name)
        if not bone:
            continue
        target_direction, _child_name, target_length = direction_to_primary_child(bone)
        direction_local = local_direction_for_shape(bone, target_direction)
        old_mesh = obj.data
        materials = [slot.material for slot in obj.material_slots]
        new_mesh = create_handle_mesh(
            f"{CONTROL_PREFIX}{safe_name(bone.name)}_Mesh",
            bone.name,
            direction_local,
            (target_length or bone.length) * handle_display_scale,
            thickness,
        )
        new_mesh["mharp_is_control_mesh"] = True
        for material in materials:
            if material:
                new_mesh.materials.append(material)
        obj.data = new_mesh
        if old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)
        updated += 1

    dashboard = bpy.data.objects.get(DASHBOARD_NAME)
    body_mesh = find_body_mesh(settings)
    visual_sync = {"controls": 0, "shape_keys": 0}
    if dashboard and body_mesh:
        visual_sync = sync_control_rig_proportion_follow(body_mesh, armature, dashboard)
    apply_control_rig_language(ui_language(settings))
    apply_control_rig_display_mode(getattr(settings, "control_rig_display_mode", "SHOW"))
    return {"controls": updated, "shape_keys": visual_sync["shape_keys"], "sync_controls": visual_sync["controls"]}


class MHARP_Settings(PropertyGroup):
    interface_language: EnumProperty(
        name="界面语言",
        items=[
            ("ZH", "中文", "使用中文界面标签"),
            ("EN", "English", "Use English interface labels"),
        ],
        default=DEFAULT_INTERFACE_LANGUAGE,
        update=interface_language_updated,
    )
    use_builtin_metahuman: BoolProperty(
        name="无外部路径时使用内置MetaHuman",
        default=True,
        description="DCCExport目录为空或不存在时，自动使用插件内置的默认MetaHuman资源包。",
    )
    dcc_export_root: StringProperty(
        name="DCCExport目录",
        subtype="DIR_PATH",
        default="",
    )
    character_name: StringProperty(name="角色名", default="")
    armature_name: StringProperty(name="身体骨架", default="MH_Body_Root")
    body_mesh_name: StringProperty(name="身体网格", default="MH_Body_LOD0")
    import_scale: FloatProperty(
        name="导入缩放",
        default=1.0,
        min=0.0001,
        max=10.0,
        soft_min=0.001,
        soft_max=1.0,
        precision=4,
        description="当前DCCExport的FBX直接用1.0导入会得到约1.4m的米制尺寸；不要靠缩放根骨架补救单位。",
    )
    hide_non_lod0: BoolProperty(name="用小眼睛隐藏低LOD", default=True)
    hide_source_armature: BoolProperty(name="隐藏原骨架，只看手柄", default=True)
    proportion_lod0_only: BoolProperty(name="只处理LOD0体型", default=True)
    run_proportion_shapes_in_full_pipeline: BoolProperty(name="一键流程生成体型调节器", default=False)
    control_rig_thickness: EnumProperty(
        name="ControlRig粗细",
        items=[
            ("THIN", "细", "更细的手柄，适合看模型轮廓。"),
            ("MEDIUM", "中", "中等粗细，介于清晰和遮挡之间。"),
            ("LARGE", "粗", "当前默认最大粗细，最容易点击。"),
        ],
        default="LARGE",
    )
    control_rig_display_mode: EnumProperty(
        name="ControlRig显示",
        items=[
            ("HIDE", "隐藏", "用小眼睛隐藏 ControlRig 可见手柄。"),
            ("TRANSPARENT", "半透明", "显示 ControlRig，但用半透明材质降低遮挡。"),
            ("SHOW", "显示", "显示 ControlRig，使用正常不透明材质。"),
        ],
        default="SHOW",
    )
    lod_display_mode: EnumProperty(
        name="低LOD显示",
        items=[
            ("HIDE", "隐藏", "用小眼睛隐藏 LOD0 以外的 MetaHuman 网格。"),
            ("TRANSPARENT", "半透明", "显示 LOD0 以外网格，但用半透明材质。"),
            ("SHOW", "显示", "显示所有 MetaHuman LOD 网格并恢复原材质。"),
        ],
        default="HIDE",
    )
    make_backup: BoolProperty(name="操作前备份当前blend", default=True)
    status: StringProperty(name="状态", default="未扫描")


class MHARP_OT_toggle_ui_language(Operator):
    bl_idname = "mharp.toggle_ui_language"
    bl_label = "切换界面语言"
    bl_description = "在中文和英文界面标签之间一键切换；插件默认中文。"

    def execute(self, context):
        settings = context.scene.mharp_settings
        settings.interface_language = "EN" if ui_language(settings) == "ZH" else "ZH"
        result = apply_scene_language_artifacts(settings)
        if settings.interface_language == "ZH":
            settings.status = f"界面语言已切换为中文：Rig重命名 {result['control_rig'].get('renamed', 0)} 个，引导标签 {result['guides'].get('labels', 0)} 个"
        else:
            settings.status = f"Interface language switched to English: renamed {result['control_rig'].get('renamed', 0)} rig controls, {result['guides'].get('labels', 0)} guide labels"
        return {"FINISHED"}


class MHARP_OT_use_builtin_metahuman(Operator):
    bl_idname = "mharp.use_builtin_metahuman"
    bl_label = "使用内置MetaHuman"
    bl_description = "把DCCExport目录切换到插件内置的默认MetaHuman资源包。"

    def execute(self, context):
        settings = context.scene.mharp_settings
        builtin = bundled_metahuman_dcc_export()
        settings.use_builtin_metahuman = True
        settings.dcc_export_root = str(builtin)
        if not builtin.exists():
            settings.status = f"内置MetaHuman资源未安装: {builtin}"
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}
        try:
            source = resolve_metahuman_source(settings)
            settings.character_name = source["character"]
            settings.status = f"已切换到内置MetaHuman: {source['character']}"
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"内置MetaHuman扫描失败: {exc}"
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}


class MHARP_OT_scan(Operator):
    bl_idname = "mharp.scan_files"
    bl_label = "扫描MetaHuman文件"
    bl_description = "从固定DCCExport入口检查角色目录、Maps、Manifest、Face/Body FBX"

    def execute(self, context):
        settings = context.scene.mharp_settings
        try:
            source = resolve_metahuman_source(settings)
            settings.character_name = source["character"]
            paths = {
                "角色目录": source["character_dir"],
                "Face FBX": source["face_fbx"],
                "Body FBX": source["body_fbx"],
                "Maps": source["maps"],
                "Manifest": source["manifest"],
            }
            missing = [name for name, path in paths.items() if not path or not path.exists()]
            settings.status = (
                f"OK: {source['character']} @ {source['dcc_export']}"
                if not missing
                else "缺失: " + ", ".join(missing)
            )
            self.report({"INFO" if not missing else "WARNING"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"扫描失败: {exc}"
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}


class MHARP_OT_import_metahuman(Operator):
    bl_idname = "mharp.import_metahuman"
    bl_label = "导入MetaHuman并接贴图"
    bl_description = "从DCCExport反推Face/Body FBX，保留LOD，按Maps接皮肤、眼睛、牙齿、睫毛材质"

    def execute(self, context):
        settings = context.scene.mharp_settings
        try:
            source = resolve_metahuman_source(settings)
        except Exception as exc:
            self.report({"ERROR"}, f"源文件解析失败: {exc}")
            return {"CANCELLED"}
        face_fbx = source["face_fbx"]
        body_fbx = source["body_fbx"]
        map_dir = source["maps"]
        if not face_fbx or not body_fbx or not map_dir.exists():
            self.report({"ERROR"}, "Face/Body FBX 或 Maps 缺失，请先扫描DCCExport目录")
            return {"CANCELLED"}
        settings.character_name = source["character"]

        try:
            if settings.make_backup:
                make_backup_if_saved()
            root_col = ensure_collection("MetaHuman_Blender")
            face_col = ensure_collection("MetaHuman_Blender_Face", root_col)
            body_col = ensure_collection("MetaHuman_Blender_Body", root_col)
            rig_col = ensure_collection("MetaHuman_Blender_Rig", root_col)

            materials = make_materials(map_dir)
            face_objects = import_fbx(face_fbx, settings.import_scale)
            body_objects = import_fbx(body_fbx, settings.import_scale)

            face_arm = next((obj for obj in face_objects if obj.type == "ARMATURE"), None)
            body_arm = next((obj for obj in body_objects if obj.type == "ARMATURE"), None)
            if not face_arm or not body_arm:
                raise RuntimeError("FBX 没有导入完整 Face/Body armature")

            face_arm.name = "MH_Face_Root"
            face_arm.data.name = "MH_Face_Root_Armature"
            body_arm.name = settings.armature_name or "MH_Body_Root"
            body_arm.data.name = f"{body_arm.name}_Armature"
            settings.armature_name = body_arm.name
            face_arm.show_in_front = True
            body_arm.show_in_front = True
            move_to_collection(face_arm, rig_col)
            move_to_collection(body_arm, rig_col)

            face_meshes = set_lods([obj for obj in face_objects if obj.type == "MESH"], "MH_Face", settings.hide_non_lod0)
            body_meshes = set_lods([obj for obj in body_objects if obj.type == "MESH"], "MH_Body", settings.hide_non_lod0)
            if body_meshes:
                settings.body_mesh_name = body_meshes[0].name
            for obj in face_meshes:
                preserve_parent(obj, face_arm)
                move_to_collection(obj, face_col)
            for obj in body_meshes:
                preserve_parent(obj, body_arm)
                move_to_collection(obj, body_col)
            enforce_metahuman_lod_visibility(settings.hide_non_lod0)
            apply_lod_display_mode(settings.lod_display_mode)

            preserve_parent(face_arm, body_arm)
            removed_empty_count = remove_empties_keep_children(face_objects + body_objects)
            unit_report = normalize_metahuman_unit_scale(body_arm, body_meshes)
            body_pose_bones = {bone.name for bone in body_arm.pose.bones}
            constraint_count = 0
            for pose_bone in face_arm.pose.bones:
                if pose_bone.name.startswith("FACIAL_") or pose_bone.name not in body_pose_bones:
                    continue
                constraint = pose_bone.constraints.new(type="COPY_TRANSFORMS")
                constraint.name = "MH_Copy_Body"
                constraint.target = body_arm
                constraint.subtarget = pose_bone.name
                constraint.target_space = "POSE"
                constraint.owner_space = "POSE"
                constraint_count += 1

            assign_metahuman_materials(face_meshes + body_meshes, materials)

            context.scene["mharp_imported"] = True
            context.scene["mharp_dcc_export"] = str(source["dcc_export"])
            context.scene["mharp_character_dir"] = str(source["character_dir"])
            context.scene["mharp_import_scale"] = float(settings.import_scale)
            context.scene["mharp_unit_normalization_scale"] = float(unit_report["scale_factor"])
            context.scene["mharp_body_height_before_unit_normalization"] = float(unit_report["height_before"])
            context.scene["mharp_body_height_after_unit_normalization"] = float(unit_report["height_after"])
            context.scene["mharp_unit_warning"] = unit_report["warning"]
            context.scene["mharp_removed_fbx_empty_count"] = removed_empty_count
            context.scene["mharp_face_body_copy_constraints"] = constraint_count
            unit_warning = f"，{unit_report['warning']}" if unit_report["warning"] else ""
            settings.status = (
                f"已导入：Face {len(face_meshes)} 个LOD，Body {len(body_meshes)} 个LOD，"
                f"FBX缩放 {settings.import_scale:g}，单位归一化 {unit_report['scale_factor']:g}，"
                f"身高 {unit_report['height_after']:.3f}{unit_warning}"
            )
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"导入失败: {exc!r}"
            print(traceback.format_exc())
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}


class MHARP_OT_repair_texture_index(Operator):
    bl_idname = "mharp.repair_texture_index"
    bl_label = "修复MetaHuman贴图索引"
    bl_description = "只重连当前Blend里的Image/材质贴图引用；不会保存Blend，也不会复制、改名、生成或删除贴图文件。"

    def execute(self, context):
        settings = context.scene.mharp_settings
        try:
            result = repair_metahuman_texture_index(settings, context)
            if ui_language(settings) == "EN":
                settings.status = (
                    f"Texture index repaired: {result['found_expected']}/{result['expected_total']} expected maps, "
                    f"{result['relinked_images']} image paths, {result['changed_slots']} material slots."
                )
                if result["missing"]:
                    settings.status += f" Missing {len(result['missing'])} expected maps."
            else:
                settings.status = (
                    f"贴图索引已修复：预期贴图 {result['found_expected']}/{result['expected_total']}，"
                    f"Image路径 {result['relinked_images']} 个，材质槽 {result['changed_slots']} 个。"
                )
                if result["missing"]:
                    settings.status += f" 仍缺少 {len(result['missing'])} 个预期贴图。"
            self.report({"WARNING" if result["missing"] else "INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"贴图索引修复失败: {exc}"
            print(traceback.format_exc())
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}


class MHARP_OT_bind_selected_clothes(Operator):
    bl_idname = "mharp.bind_selected_clothes"
    bl_label = "绑定选中衣服到身体"
    bl_description = "把当前选中的衣服/装备网格绑定到MetaHuman身体骨架：从身体LOD0投射顶点组权重，并添加Armature修改器。"

    def execute(self, context):
        settings = context.scene.mharp_settings
        try:
            result = bind_selected_clothes_to_body(context, settings)
            if ui_language(settings) == "EN":
                settings.status = (
                    f"Bound {result['count']} selected mesh(es) to {result['armature']}: "
                    f"weights applied {result['applied_count']}, old armatures removed {result['removed_armature_modifier_count']}, "
                    f"old parents detached {result['detached_parent_count']}."
                )
            else:
                settings.status = (
                    f"已绑定 {result['count']} 个选中网格到 {result['armature']}："
                    f"权重投射 {result['applied_count']} 个，移除旧Armature {result['removed_armature_modifier_count']} 个，"
                    f"解除旧父级 {result['detached_parent_count']} 个。"
                )
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"衣服绑定失败: {exc}"
            print(traceback.format_exc())
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}


class MHARP_OT_paint_cloth_weights_from_control(Operator):
    bl_idname = "mharp.paint_cloth_weights_from_control"
    bl_label = "用ControlRig刷衣服权重"
    bl_description = "选中一个衣服网格和一个ControlRig手柄后，自动进入衣服的Weight Paint，并把手柄对应骨骼设为当前顶点组。"

    def execute(self, context):
        settings = context.scene.mharp_settings
        try:
            result = enter_cloth_weight_paint_from_control(context, settings)
            bake = result.get("bake", {})
            if ui_language(settings) == "EN":
                settings.status = (
                    f"Weight Paint ready on {result['object']}: active group {result['group']} "
                    f"from {result['control']}; baked {bake.get('manual_transfer', {}).get('assigned_vertices', 0)} vertices."
                )
            else:
                settings.status = (
                    f"已进入 {result['object']} 的权重绘制：当前顶点组 {result['group']}，"
                    f"来自 {result['control']}；固化权重顶点 {bake.get('manual_transfer', {}).get('assigned_vertices', 0)} 个。"
                )
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"进入衣服权重绘制失败: {exc}"
            print(traceback.format_exc())
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}


class MHARP_OT_apply_pose_as_rest(Operator):
    bl_idname = "mharp.apply_pose_as_rest"
    bl_label = "应用当前姿势为Rest Pose"
    bl_description = "把身体骨架当前姿势应用为新的Rest Pose；会修改当前角色骨架，建议保持“操作前备份当前blend”开启。"

    def execute(self, context):
        settings = context.scene.mharp_settings
        try:
            result = apply_current_body_pose_as_rest(context, settings)
            if ui_language(settings) == "EN":
                settings.status = f"Applied current pose as rest pose: {result['armature']}"
            else:
                settings.status = f"已应用当前姿势为Rest Pose：{result['armature']}"
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"应用当前姿势为Rest Pose失败: {exc}"
            print(traceback.format_exc())
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}


class MHARP_OT_build_control_rig(Operator):
    bl_idname = "mharp.build_control_rig"
    bl_label = "生成专用ControlRig"
    bl_description = "为身体骨架每根骨骼生成 mesh 手柄，并用 Copy Location/Rotation 约束驱动原骨架"

    def execute(self, context):
        settings = context.scene.mharp_settings
        armature = get_armature(settings.armature_name)
        if not armature:
            self.report({"ERROR"}, "找不到身体骨架")
            return {"CANCELLED"}
        try:
            if settings.make_backup:
                make_backup_if_saved()
            remove_existing_control_rig()
            collection = ensure_collection(CONTROL_COLLECTION)
            collection.hide_render = True
            visible_mat = ensure_material("MH_Control_Visible_Handle", (0.12, 0.72, 1.0, 1.0))
            hidden_mat = ensure_material("MH_Control_Hidden_Helper", (0.22, 0.22, 0.22, 0.18))
            global_mat = ensure_material("MH_Control_Global", (1.0, 0.78, 0.12, 1.0))
            controls = {}
            rest_matrices = {}
            visible_count = 0
            hidden_count = 0
            handle_display_scale = average_matrix_scale(armature.matrix_world)

            for bone in armature.data.bones:
                rest = bone_rest_matrix(armature, bone)
                target_direction, _child_name, target_length = direction_to_primary_child(bone)
                direction_local = local_direction_for_shape(bone, target_direction)
                mesh = create_handle_mesh(
                    f"{CONTROL_PREFIX}{safe_name(bone.name)}_Mesh",
                    bone.name,
                    direction_local,
                    (target_length or bone.length) * handle_display_scale,
                    control_thickness_scale(settings.control_rig_thickness),
                )
                obj = bpy.data.objects.new(f"{CONTROL_PREFIX}{safe_name(bone.name)}", mesh)
                obj.matrix_world = rest
                obj.show_in_front = True
                obj.hide_render = True
                obj.display_type = "TEXTURED"
                tag_control_object(obj, bone.name)
                visible = is_primary_bone(bone.name)
                obj.hide_viewport = not visible
                obj.hide_select = not visible
                mesh.materials.append(visible_mat if visible else hidden_mat)
                collection.objects.link(obj)
                controls[bone.name] = obj
                rest_matrices[bone.name] = rest
                visible_count += int(visible)
                hidden_count += int(not visible)

            global_control, global_rest = create_global_control(armature, collection, global_mat)
            apply_control_rig_language(ui_language(settings))

            for bone in armature.data.bones:
                obj = controls[bone.name]
                parent_bone = bone.parent
                parent_obj = controls.get(parent_bone.name) if parent_bone else global_control
                parent_rest = rest_matrices.get(parent_bone.name) if parent_bone else global_rest
                obj.parent = parent_obj
                obj.matrix_parent_inverse = Matrix.Identity(4)
                obj.matrix_basis = parent_rest.inverted() @ rest_matrices[bone.name]

            clear_control_constraints(armature)
            constraint_count = add_control_constraints(armature, controls)
            visual_sync = {"controls": 0, "shape_keys": 0}
            dashboard = bpy.data.objects.get(DASHBOARD_NAME)
            body_mesh = find_body_mesh(settings)
            if dashboard and body_mesh:
                visual_sync = sync_control_rig_proportion_follow(body_mesh, armature, dashboard)
            if settings.hide_source_armature:
                hide_deform_rigs(armature, settings.hide_non_lod0)
            enforce_metahuman_lod_visibility(settings.hide_non_lod0)
            apply_lod_display_mode(settings.lod_display_mode)
            apply_control_rig_display_mode(settings.control_rig_display_mode)

            bpy.ops.object.select_all(action="DESELECT")
            if settings.control_rig_display_mode != "HIDE":
                global_control.select_set(True)
                context.view_layer.objects.active = global_control
            context.scene["mharp_control_rig"] = True
            context.scene["mharp_control_visual_sync"] = visual_sync
            sync_suffix = f"，同步{visual_sync['controls']}个手柄外观" if visual_sync["controls"] else ""
            settings.status = f"ControlRig完成：可见{visible_count + 1}，隐藏{hidden_count}，约束{constraint_count}{sync_suffix}"
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"ControlRig失败: {exc!r}"
            print(traceback.format_exc())
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}


class MHARP_OT_mirror_left_to_right(Operator):
    bl_idname = "mharp.mirror_left_to_right"
    bl_label = "左侧手柄镜像到右侧"
    bl_description = "只镜像左侧 ControlRig 手柄对象的姿态状态到右侧；不修改顶点、mesh 数据或形态键"

    def execute(self, context):
        settings = context.scene.mharp_settings
        armature = get_armature(settings.armature_name)
        pairs = mirror_control_states("_l", "_r", armature)
        settings.status = f"已左到右镜像 {pairs} 对ControlRig手柄"
        self.report({"INFO"}, settings.status)
        return {"FINISHED"}


class MHARP_OT_mirror_right_to_left(Operator):
    bl_idname = "mharp.mirror_right_to_left"
    bl_label = "右侧手柄镜像到左侧"
    bl_description = "只镜像右侧 ControlRig 手柄对象的姿态状态到左侧；不修改顶点、mesh 数据或形态键"

    def execute(self, context):
        settings = context.scene.mharp_settings
        armature = get_armature(settings.armature_name)
        pairs = mirror_control_states("_r", "_l", armature)
        settings.status = f"已右到左镜像 {pairs} 对ControlRig手柄"
        self.report({"INFO"}, settings.status)
        return {"FINISHED"}


class MHARP_OT_sync_control_rig_visuals(Operator):
    bl_idname = "mharp.sync_control_rig_visuals"
    bl_label = "刷新Rig外观"
    bl_description = "只刷新 ControlRig 手柄显示和跟随驱动，让它跟上当前体型；不修改体型参数、不固化网格"

    def execute(self, context):
        settings = context.scene.mharp_settings
        armature = get_armature(settings.armature_name)
        mesh_obj = find_body_mesh(settings)
        dashboard = bpy.data.objects.get(DASHBOARD_NAME)
        if not armature or not mesh_obj or not dashboard:
            self.report({"ERROR"}, "需要先有身体骨架、身体网格和体型调节器")
            return {"CANCELLED"}
        try:
            visual_sync = sync_control_rig_proportion_follow(mesh_obj, armature, dashboard)
            context.scene["mharp_control_visual_sync"] = visual_sync
            settings.status = (
                f"ControlRig体型外观同步完成：{visual_sync['controls']} 个手柄，"
                f"{visual_sync['shape_keys']} 个同步形态键，{len(visual_sync.get('follow_controls', []))} 个跟随控制器"
            )
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"ControlRig体型外观同步失败: {exc!r}"
            print(traceback.format_exc())
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}


class MHARP_OT_bake_static_proportion_copy(Operator):
    bl_idname = "mharp.bake_static_proportion_copy"
    bl_label = "静态网格副本"
    bl_description = "生成当前体型的静态 Body/Face 网格副本；适合进编辑模式修网格，不保留骨架绑定，不修改原始可调角色"

    def execute(self, context):
        settings = context.scene.mharp_settings
        try:
            result = bake_current_proportion_static_copy(settings)
            context.scene["mharp_baked_static_copy"] = result
            settings.status = f"已固化静态副本：{len(result['objects'])} 个对象，{result['vertices']} 个顶点"
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"固化当前体型副本失败: {exc!r}"
            print(traceback.format_exc())
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}


class MHARP_OT_bake_advanced_proportion_copy(Operator):
    bl_idname = "mharp.bake_advanced_proportion_copy"
    bl_label = "新骨架副本"
    bl_description = "生成当前体型的新 Body/Face 和新身体骨架；Body 保留顶点组并绑定到按当前长度/躯干高度调整过 rest pose 的新骨架，不修改原始角色"

    def execute(self, context):
        settings = context.scene.mharp_settings
        try:
            result = bake_current_proportion_advanced_copy(settings)
            context.scene["mharp_advanced_baked_copy"] = result
            settings.status = (
                f"已固化新骨架副本：{result['armature']}，"
                f"{len(result['objects'])} 个网格，移动骨骼 {result['moved_bones']} 个"
            )
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"固化为新骨架副本失败: {exc!r}"
            print(traceback.format_exc())
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}


class MHARP_OT_apply_control_rig_thickness(Operator):
    bl_idname = "mharp.apply_control_rig_thickness"
    bl_label = "应用ControlRig粗细"
    bl_description = "按细/中/粗三档重建 ControlRig 手柄网格，并保留当前控制层级和体型外观同步"

    def execute(self, context):
        settings = context.scene.mharp_settings
        armature = get_armature(settings.armature_name)
        if not armature:
            self.report({"ERROR"}, "找不到身体骨架")
            return {"CANCELLED"}
        try:
            result = apply_control_rig_thickness(settings, armature)
            context.scene["mharp_control_thickness_apply"] = result
            settings.status = (
                f"ControlRig粗细已应用：{settings.control_rig_thickness}，"
                f"{result['controls']} 个手柄，{result['shape_keys']} 个同步形态键"
            )
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"ControlRig粗细应用失败: {exc!r}"
            print(traceback.format_exc())
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}


class MHARP_OT_create_torso_width_guides(Operator):
    bl_idname = "mharp.create_torso_width_guides"
    bl_label = "生成躯干粗细引导点"
    bl_description = "为胸部、腰腹、胯部粗细生成可摆放引导点；移动后点击应用并重建让体型形态键读取新位置"

    reset: BoolProperty(default=False)

    def execute(self, context):
        settings = context.scene.mharp_settings
        armature = get_armature(settings.armature_name)
        mesh_obj = find_body_mesh(settings)
        dashboard = bpy.data.objects.get(DASHBOARD_NAME) or create_dashboard()
        if not armature or not mesh_obj:
            settings.status = "需要先导入身体并生成/找到身体骨架"
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}
        result = create_or_update_torso_guides(mesh_obj, armature, dashboard, reset=self.reset)
        action = "重置" if self.reset else "生成/刷新"
        settings.status = f"已{action}躯干粗细引导点：{result['total']} 个"
        self.report({"INFO"}, settings.status)
        return {"FINISHED"}


class MHARP_OT_set_torso_guide_visibility(Operator):
    bl_idname = "mharp.set_torso_guide_visibility"
    bl_label = "设置躯干引导点显示"
    bl_description = "一键隐藏或显示躯干粗细引导点；只改变引导点对象可见性，不改变体型形态键"

    mode: StringProperty(default="SHOW")

    def execute(self, context):
        settings = context.scene.mharp_settings
        mode = self.mode if self.mode in {"HIDE", "SHOW"} else "SHOW"
        result = apply_torso_guide_visibility(mode)
        labels = {"HIDE": "隐藏", "SHOW": "显示"}
        settings.status = f"躯干粗细引导点已{labels[mode]}：{result['guides']} 个"
        self.report({"INFO"}, settings.status)
        return {"FINISHED"}


class MHARP_OT_set_control_rig_display(Operator):
    bl_idname = "mharp.set_control_rig_display"
    bl_label = "设置ControlRig显示"
    bl_description = "一键隐藏、半透明或显示 ControlRig 手柄"

    mode: StringProperty(default="SHOW")

    def execute(self, context):
        settings = context.scene.mharp_settings
        mode = self.mode if self.mode in {"HIDE", "TRANSPARENT", "SHOW"} else "SHOW"
        result = apply_control_rig_display_mode(mode)
        settings.control_rig_display_mode = mode
        context.scene["mharp_control_rig_display"] = result
        labels = {"HIDE": "隐藏", "TRANSPARENT": "半透明", "SHOW": "显示"}
        settings.status = f"ControlRig显示已切换为{labels[mode]}：{result['objects']} 个对象"
        self.report({"INFO"}, settings.status)
        return {"FINISHED"}


class MHARP_OT_set_lod_display(Operator):
    bl_idname = "mharp.set_lod_display"
    bl_label = "设置低LOD显示"
    bl_description = "一键隐藏、半透明或显示 LOD0 以外的 MetaHuman 网格"

    mode: StringProperty(default="HIDE")

    def execute(self, context):
        settings = context.scene.mharp_settings
        mode = self.mode if self.mode in {"HIDE", "TRANSPARENT", "SHOW"} else "HIDE"
        result = apply_lod_display_mode(mode)
        settings.lod_display_mode = mode
        settings.hide_non_lod0 = mode == "HIDE"
        context.scene["mharp_lod_display"] = result
        labels = {"HIDE": "隐藏", "TRANSPARENT": "半透明", "SHOW": "显示"}
        settings.status = f"低LOD显示已切换为{labels[mode]}：{result['objects']} 个对象"
        self.report({"INFO"}, settings.status)
        return {"FINISHED"}


class MHARP_OT_reset_proportion_group_defaults(Operator):
    bl_idname = "mharp.reset_proportion_group_defaults"
    bl_label = "恢复本组默认并应用"
    bl_description = "把当前体型参数分组恢复到插件默认值，并自动执行该分组需要的重建或ControlRig外观同步"

    group_name: StringProperty(default="")

    def execute(self, context):
        settings = context.scene.mharp_settings
        dashboard = bpy.data.objects.get(DASHBOARD_NAME)
        if not dashboard:
            self.report({"ERROR"}, "需要先生成体型调节器")
            return {"CANCELLED"}
        prop_names = proportion_group_props(self.group_name)
        if not prop_names:
            self.report({"ERROR"}, f"找不到参数分组: {self.group_name}")
            return {"CANCELLED"}

        reset_count = 0
        for prop_name in prop_names:
            default = proportion_param_default(prop_name)
            if default is None:
                continue
            dashboard[prop_name] = default
            reset_count += 1

        needs_rebuild = any(param_action_kind(prop_name) == "REBUILD" for prop_name in prop_names)
        needs_rig_sync = any(param_action_kind(prop_name) == "REALTIME_RIG" for prop_name in prop_names)
        applied = "实时生效"
        if needs_rebuild:
            result = bpy.ops.mharp.create_proportion_shapes()
            if "FINISHED" not in result:
                self.report({"ERROR"}, f"已恢复默认值，但应用并重建失败：{settings.status}")
                return {"CANCELLED"}
            applied = "已应用并重建"
        elif needs_rig_sync and control_objects():
            result = bpy.ops.mharp.sync_control_rig_visuals()
            if "FINISHED" not in result:
                self.report({"WARNING"}, f"已恢复默认值，但ControlRig外观同步失败：{settings.status}")
                return {"FINISHED"}
            applied = "已同步ControlRig外观"

        context.scene["mharp_last_reset_group_apply"] = {
            "group": self.group_name,
            "reset_count": reset_count,
            "needs_rebuild": needs_rebuild,
            "needs_rig_sync": needs_rig_sync,
            "applied": applied,
        }
        settings.status = f"已恢复“{self.group_name}”默认值：{reset_count} 个参数，{applied}"
        self.report({"INFO"}, settings.status)
        return {"FINISHED"}


class MHARP_OT_create_proportion_shapes(Operator):
    bl_idname = "mharp.create_proportion_shapes"
    bl_label = "应用体型并同步Rig"
    bl_description = "创建或重建身体形态键，应用骨末端/法向/权重/平滑等底层策略，并自动同步 ControlRig 外观；不改骨骼 rest、不改权重"

    def execute(self, context):
        settings = context.scene.mharp_settings
        armature = get_armature(settings.armature_name)
        mesh_obj = find_body_mesh(settings)
        if not armature or not mesh_obj or mesh_obj.type != "MESH":
            self.report({"ERROR"}, "找不到身体骨架或身体网格")
            return {"CANCELLED"}
        if settings.proportion_lod0_only and not mesh_obj.name.startswith("MH_Body_LOD0"):
            lod0_mesh = bpy.data.objects.get("MH_Body_LOD0")
            if lod0_mesh and lod0_mesh.type == "MESH":
                mesh_obj = lod0_mesh
            else:
                self.report({"ERROR"}, "已启用只处理LOD0体型，但找不到 MH_Body_LOD0")
                return {"CANCELLED"}
        progress_started = False
        try:
            if settings.make_backup:
                make_backup_if_saved()
            reveal_object_and_collections(mesh_obj)
            settings.body_mesh_name = mesh_obj.name
            dashboard = create_dashboard()
            total_changed = 0
            report = {}
            timings = []
            cleared_face_drivers = clear_torso_height_object_drivers()
            added_face_drivers = []
            total_items = len(PROPORTION_DEFS)
            context.window_manager.progress_begin(0, total_items)
            progress_started = True
            for index, item in enumerate(PROPORTION_DEFS, 1):
                settings.status = f"正在生成体型调节器 {index}/{total_items}: {item['prop']}"
                self.report({"INFO"}, settings.status)
                started_at = time.perf_counter()
                changed = build_shape_key(mesh_obj, armature, dashboard, item)
                seconds = time.perf_counter() - started_at
                report[item["prop"]] = changed
                timings.append({"prop": item["prop"], "changed": changed, "seconds": seconds})
                total_changed += changed
                context.window_manager.progress_update(index)
                if item["kind"] == "vertical":
                    added_face_drivers = add_torso_height_object_drivers(mesh_obj, armature, dashboard, item)
            text = bpy.data.texts.get("README_MHARP_Proportion") or bpy.data.texts.new("README_MHARP_Proportion")
            text.clear()
            text.write(
                "身体比例控制说明\n"
                "选择“身体比例控制”，在 N 面板 > MH > 体型参数中按上肢/下肢/躯干分组调整中文属性。\n"
                "本调节器使用形态键和驱动器，不修改骨骼 rest pose、顶点组权重或控制手柄层级。\n"
                "ControlRig 可见网格会用同步形态键跟随长度和躯干高度；控制物体原点与骨架约束不被体型参数直接移动，避免二次骨架变形。\n"
                "主面板可切换 ControlRig 粗细三档，并可一键隐藏/半透明/显示 ControlRig 与 LOD0 以外网格。\n"
                "默认值 1.0 等于无变化；建议先在 0.85 到 1.2 之间试。\n"
                "四肢长度会沿主 Control Rig 轴向生成累计位移，下游子链只继承父段末端位移。\n"
                "长度主段靠近子关节时会抹平 skin weight 打折，减少极限拉长时的肘/膝/腕/踝折叠。\n"
                "躯干高度会让肩带以下整条上肢链整体跟随顶部位移，避免手臂和肩部撕裂。\n"
                "骨末端衰减控制骨末端淡入范围和衰减曲线；末端最小效果固定为0。\n"
                "骨末端衰减、法向混合、躯干高度权重和平滑属于生成策略参数，改完需要点“应用并重建”。\n"
                "躯干高度由腰为主、胸为辅、胯极少的累计曲线生成，并让 Face LOD 随顶部过渡轻微跟随。\n"
            )
            visual_sync = sync_control_rig_proportion_follow(mesh_obj, armature, dashboard)
            record_profile_build_snapshot(dashboard)
            context.scene["mharp_proportion_shapes"] = report
            context.scene["mharp_proportion_shape_timings_json"] = json.dumps(timings, ensure_ascii=False)
            context.scene["mharp_cleared_face_torso_height_drivers"] = cleared_face_drivers
            context.scene["mharp_added_face_torso_height_drivers"] = added_face_drivers
            context.scene["mharp_control_visual_sync"] = visual_sync
            settings.status = (
                f"体型和Rig已同步：{len(PROPORTION_DEFS)} 个属性，影响顶点累计 {total_changed}，"
                f"Face高度跟随 {len(added_face_drivers)} 个，Rig外观同步 {visual_sync['controls']} 个"
            )
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"体型调节器失败: {exc!r}"
            print(traceback.format_exc())
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}
        finally:
            if progress_started:
                context.window_manager.progress_end()


class MHARP_OT_run_full_pipeline(Operator):
    bl_idname = "mharp.run_full_pipeline"
    bl_label = "一键完成MetaHuman流程"
    bl_description = "扫描DCCExport，导入Face/Body并接贴图，然后生成ControlRig和中文体型调节器"

    def execute(self, context):
        settings = context.scene.mharp_settings
        original_make_backup = bool(settings.make_backup)
        try:
            source = resolve_metahuman_source(settings)
            settings.character_name = source["character"]
            required = {
                "Face FBX": source["face_fbx"],
                "Body FBX": source["body_fbx"],
                "Maps": source["maps"],
            }
            missing = [name for name, path in required.items() if not path or not path.exists()]
            if missing:
                raise RuntimeError("缺失: " + ", ".join(missing))

            if original_make_backup:
                make_backup_if_saved()

            settings.make_backup = False
            steps = [
                ("导入MetaHuman并接贴图", bpy.ops.mharp.import_metahuman),
                ("生成专用ControlRig", bpy.ops.mharp.build_control_rig),
            ]
            if settings.run_proportion_shapes_in_full_pipeline:
                steps.append(("创建安全体型调节器", bpy.ops.mharp.create_proportion_shapes))
            for label, operator in steps:
                settings.status = f"正在{label}..."
                result = operator()
                if "FINISHED" not in result:
                    raise RuntimeError(f"{label}失败: {settings.status}")

            dashboard = bpy.data.objects.get(DASHBOARD_NAME)
            if dashboard:
                bpy.ops.object.select_all(action="DESELECT")
                dashboard.select_set(True)
                context.view_layer.objects.active = dashboard

            context.scene["mharp_full_pipeline"] = True
            suffix = "/体型调节器" if settings.run_proportion_shapes_in_full_pipeline else "，已跳过体型调节器"
            settings.status = f"一键流程完成：导入/贴图/ControlRig{suffix}"
            self.report({"INFO"}, settings.status)
            return {"FINISHED"}
        except Exception as exc:
            settings.status = f"一键流程失败: {exc!r}"
            print(traceback.format_exc())
            self.report({"ERROR"}, settings.status)
            return {"CANCELLED"}
        finally:
            settings.make_backup = original_make_backup


class MHARP_PT_panel(Panel):
    bl_idname = "MHARP_PT_panel"
    bl_label = "MetaForge"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MetaForge"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.mharp_settings
        row = layout.row(align=True)
        row.prop(settings, "interface_language", text=ui_text(settings, "language_name"))
        row.operator("mharp.toggle_ui_language", text=ui_text(settings, "language_switch"), icon="WORLD")
        layout.prop(settings, "use_builtin_metahuman", text=ui_text(settings, "builtin_toggle"))
        layout.operator("mharp.use_builtin_metahuman", text=ui_text(settings, "use_builtin"), icon="HOME")
        layout.prop(settings, "dcc_export_root", text=ui_text(settings, "dcc_export_root"))
        layout.prop(settings, "character_name", text=ui_text(settings, "character_name"))
        layout.prop(settings, "armature_name", text=ui_text(settings, "armature_name"))
        layout.prop(settings, "body_mesh_name", text=ui_text(settings, "body_mesh_name"))
        layout.prop(settings, "import_scale", text=ui_text(settings, "import_scale"))
        row = layout.row(align=True)
        row.prop(settings, "hide_non_lod0", text=ui_text(settings, "hide_non_lod0"))
        row.prop(settings, "make_backup", text=ui_text(settings, "make_backup"))
        layout.prop(settings, "hide_source_armature", text=ui_text(settings, "hide_source_armature"))
        layout.prop(settings, "proportion_lod0_only", text=ui_text(settings, "proportion_lod0_only"))
        layout.prop(settings, "run_proportion_shapes_in_full_pipeline", text=ui_text(settings, "run_proportion_shapes_in_full_pipeline"))
        layout.separator()
        layout.prop(settings, "control_rig_thickness", text=ui_text(settings, "control_rig_thickness"))
        layout.operator("mharp.apply_control_rig_thickness", text=ui_text(settings, "apply_control_rig_thickness"), icon="MOD_SOLIDIFY")
        row = layout.row(align=True)
        op = row.operator("mharp.set_control_rig_display", text=ui_text(settings, "rig_hide"), icon="HIDE_ON")
        op.mode = "HIDE"
        op = row.operator("mharp.set_control_rig_display", text=ui_text(settings, "transparent"), icon="MATERIAL")
        op.mode = "TRANSPARENT"
        op = row.operator("mharp.set_control_rig_display", text=ui_text(settings, "show"), icon="HIDE_OFF")
        op.mode = "SHOW"
        row = layout.row(align=True)
        op = row.operator("mharp.set_lod_display", text=ui_text(settings, "lod_hide"), icon="HIDE_ON")
        op.mode = "HIDE"
        op = row.operator("mharp.set_lod_display", text=ui_text(settings, "transparent"), icon="MATERIAL")
        op.mode = "TRANSPARENT"
        op = row.operator("mharp.set_lod_display", text=ui_text(settings, "show"), icon="HIDE_OFF")
        op.mode = "SHOW"
        layout.separator()
        layout.operator("mharp.run_full_pipeline", text=ui_text(settings, "run_full_pipeline"), icon="PLAY")
        layout.separator()
        layout.operator("mharp.scan_files", text=ui_text(settings, "scan"), icon="VIEWZOOM")
        layout.operator("mharp.import_metahuman", text=ui_text(settings, "import"), icon="IMPORT")
        layout.operator("mharp.repair_texture_index", text=ui_text(settings, "repair_textures"), icon="FILE_REFRESH")
        layout.operator("mharp.build_control_rig", text=ui_text(settings, "build_rig"), icon="ARMATURE_DATA")
        layout.operator("mharp.apply_pose_as_rest", text=ui_text(settings, "apply_pose_as_rest"), icon="ARMATURE_DATA")
        layout.operator("mharp.bind_selected_clothes", text=ui_text(settings, "bind_selected_clothes"), icon="MOD_ARMATURE")
        layout.operator("mharp.paint_cloth_weights_from_control", text=ui_text(settings, "paint_cloth_weights"), icon="WPAINT_HLT")
        layout.separator()
        layout.label(text=ui_text(settings, "body_workflow"), icon="SHAPEKEY_DATA")
        layout.operator("mharp.create_proportion_shapes", text=ui_text(settings, "apply_rebuild"), icon="FILE_REFRESH")
        layout.label(text=ui_text(settings, "body_workflow_hint"), icon="INFO")
        layout.separator()
        layout.label(text=ui_text(settings, "bake_workflow"), icon="PACKAGE")
        row = layout.row(align=True)
        row.operator("mharp.bake_static_proportion_copy", text=ui_text(settings, "bake_static_copy"), icon="MESH_DATA")
        row.operator("mharp.bake_advanced_proportion_copy", text=ui_text(settings, "bake_advanced_copy"), icon="OUTLINER_OB_ARMATURE")
        layout.label(text=ui_text(settings, "bake_workflow_hint"), icon="INFO")
        layout.separator()
        layout.label(text=ui_text(settings, "guide_workflow"), icon="EMPTY_ARROWS")
        row = layout.row(align=True)
        op = row.operator("mharp.create_torso_width_guides", text=ui_text(settings, "create_torso_guides"), icon="EMPTY_ARROWS")
        op.reset = False
        op = row.operator("mharp.create_torso_width_guides", text=ui_text(settings, "reset_torso_guides"), icon="LOOP_BACK")
        op.reset = True
        row = layout.row(align=True)
        op = row.operator("mharp.set_torso_guide_visibility", text=ui_text(settings, "hide_torso_guides"), icon="HIDE_ON")
        op.mode = "HIDE"
        op = row.operator("mharp.set_torso_guide_visibility", text=ui_text(settings, "show_torso_guides"), icon="HIDE_OFF")
        op.mode = "SHOW"
        layout.separator()
        row = layout.row(align=True)
        row.operator("mharp.mirror_left_to_right", text=ui_text(settings, "mirror_l_to_r"), icon="ARROW_LEFTRIGHT")
        row.operator("mharp.mirror_right_to_left", text=ui_text(settings, "mirror_r_to_l"), icon="ARROW_LEFTRIGHT")
        layout.separator()
        layout.label(text=settings.status)


def dashboard_param_label(group_name, prop_name):
    label = prop_name
    for prefix in (
        "上肢.长度.",
        "上肢.粗细.",
        "下肢.长度.",
        "下肢.粗细.",
        "四肢.长度.",
        "四肢.粗细.",
        "躯干.高度.",
        "躯干.粗细.",
        "胸部.粗细.",
        "腰部.粗细.",
        "胯部.粗细.",
        "四肢.",
        "躯干.",
    ):
        if prop_name.startswith(prefix):
            label = prop_name[len(prefix):]
            break
    if prop_name in INACTIVE_PROPORTION_PARAMS:
        return label if label.startswith("X") else "X" + label
    return label


class MHARP_PT_proportion_params(Panel):
    bl_idname = "MHARP_PT_proportion_params"
    bl_label = "体型参数"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MetaForge"
    bl_parent_id = "MHARP_PT_panel"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.mharp_settings
        layout.use_property_split = True
        layout.use_property_decorate = False
        dashboard = bpy.data.objects.get(DASHBOARD_NAME)
        if not dashboard:
            layout.label(text=ui_text(settings, "build_first"))
            return
        dirty_params, snapshot_missing = dirty_profile_params(dashboard)
        dirty_set = set(dirty_params)
        sync_missing = bool(control_objects()) and not has_control_visual_sync_shape_keys()
        status_box = layout.box()
        if dirty_params:
            status_box.alert = True
            if snapshot_missing:
                status_box.label(text=ui_text(settings, "snapshot_missing"), icon="ERROR")
            else:
                status_box.label(text=ui_text(settings, "dirty_params", count=len(dirty_params)), icon="ERROR")
        else:
            status_box.label(text=ui_text(settings, "params_clean"), icon="CHECKMARK")
        if sync_missing:
            status_box.alert = True
            status_box.label(text=ui_text(settings, "sync_missing"), icon="ERROR")
        row = layout.row(align=True)
        row.alert = bool(dirty_params)
        row.operator("mharp.create_proportion_shapes", text=ui_text(settings, "apply_rebuild"), icon="FILE_REFRESH")
        layout.label(text=ui_text(settings, "param_usage_hint"), icon="INFO")
        layout.separator()
        for group_name, prop_names in PROPORTION_PARAM_GROUPS:
            box = layout.box()
            row = box.row(align=True)
            row.label(text=group_name)
            op = row.operator("mharp.reset_proportion_group_defaults", text=ui_text(settings, "reset_apply"), icon="FILE_REFRESH")
            op.group_name = group_name
            for prop_name in prop_names:
                if prop_name in dashboard:
                    prop_row = box.row(align=True)
                    prop_row.alert = prop_name in dirty_set
                    prop_row.prop(dashboard, f'["{prop_name}"]', text=dashboard_param_label(group_name, prop_name))
                    action_label = param_action_label(prop_name)
                    if action_label:
                        prop_row.label(text=action_label)


classes = (
    MHARP_Settings,
    MHARP_OT_toggle_ui_language,
    MHARP_OT_use_builtin_metahuman,
    MHARP_OT_scan,
    MHARP_OT_import_metahuman,
    MHARP_OT_repair_texture_index,
    MHARP_OT_bind_selected_clothes,
    MHARP_OT_paint_cloth_weights_from_control,
    MHARP_OT_apply_pose_as_rest,
    MHARP_OT_build_control_rig,
    MHARP_OT_mirror_left_to_right,
    MHARP_OT_mirror_right_to_left,
    MHARP_OT_sync_control_rig_visuals,
    MHARP_OT_bake_static_proportion_copy,
    MHARP_OT_bake_advanced_proportion_copy,
    MHARP_OT_apply_control_rig_thickness,
    MHARP_OT_create_torso_width_guides,
    MHARP_OT_set_torso_guide_visibility,
    MHARP_OT_set_control_rig_display,
    MHARP_OT_set_lod_display,
    MHARP_OT_reset_proportion_group_defaults,
    MHARP_OT_create_proportion_shapes,
    MHARP_OT_run_full_pipeline,
    MHARP_PT_panel,
    MHARP_PT_proportion_params,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mharp_settings = PointerProperty(type=MHARP_Settings)


def unregister():
    if hasattr(bpy.types.Scene, "mharp_settings"):
        del bpy.types.Scene.mharp_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
