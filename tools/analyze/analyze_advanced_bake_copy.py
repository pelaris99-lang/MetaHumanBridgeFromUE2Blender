import importlib.util
import json
import sys
from pathlib import Path

import bpy


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "addon" / "metahuman_blender_pipeline" / "__init__.py"
OUT = WORKSPACE / "test_results" / "advanced_bake_copy_metrics.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def load_addon_module():
    spec = importlib.util.spec_from_file_location("metahuman_blender_pipeline_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeSettings:
    armature_name = "MH_Body_Root"
    body_mesh_name = "MH_Body_LOD0"


def ensure_current_shape_keys(module, mesh_obj, armature, dashboard):
    existing = mesh_obj.data.shape_keys.key_blocks if mesh_obj.data.shape_keys else {}
    if any(f"MH_{module.safe_name(item['prop'])}" not in existing for item in module.PROPORTION_DEFS):
        for item in module.PROPORTION_DEFS:
            module.build_shape_key(mesh_obj, armature, dashboard, item)


def evaluated_mesh_points(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph, preserve_all_data_layers=True)
    try:
        return [obj.matrix_world @ vertex.co for vertex in mesh.vertices]
    finally:
        bpy.data.meshes.remove(mesh)


def object_mesh_points(obj):
    return [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]


def max_point_error(a, b):
    if len(a) != len(b):
        return float("inf")
    if not a:
        return 0.0
    return max((pa - pb).length for pa, pb in zip(a, b))


def bone_world_point(armature, bone_name, attr):
    bone = armature.data.bones[bone_name]
    return armature.matrix_world @ getattr(bone, attr)


def json_safe(value):
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def main():
    module = load_addon_module()
    failures = []
    mesh_obj = bpy.data.objects.get("MH_Body_LOD0")
    armature = bpy.data.objects.get("MH_Body_Root")
    dashboard = module.create_dashboard()
    if not mesh_obj or not armature:
        failures.append("missing body mesh or body armature")
    else:
        ensure_current_shape_keys(module, mesh_obj, armature, dashboard)

    for prop, value in {
        "上臂长度": 1.85,
        "小臂长度": 1.55,
        "大腿长度": 1.55,
        "小腿长度": 1.45,
        "躯干高度": 1.45,
        "胸部粗细": 1.30,
        "腰部粗细": 1.25,
        "胯部粗细": 1.25,
    }.items():
        if prop in dashboard:
            dashboard[prop] = value
    bpy.context.view_layer.update()

    original_shape_count = len(mesh_obj.data.shape_keys.key_blocks) if mesh_obj.data.shape_keys else 0
    original_lowerarm_head = bone_world_point(armature, "lowerarm_l", "head_local")
    original_hand_head = bone_world_point(armature, "hand_l", "head_local")
    original_clavicle_head = bone_world_point(armature, "clavicle_l", "head_local")
    original_upper_axis = (
        bone_world_point(armature, "lowerarm_l", "head_local")
        - bone_world_point(armature, "upperarm_l", "head_local")
    ).normalized()

    result = module.bake_current_proportion_advanced_copy(FakeSettings())
    source_points = evaluated_mesh_points(mesh_obj)
    auto_apply = json_safe(bpy.context.scene.get("mharp_auto_apply_before_bake", {}))
    new_armature = bpy.data.objects.get(result["armature"])
    baked_body = bpy.data.objects.get(result["objects"][0]) if result["objects"] else None
    if not new_armature or new_armature.type != "ARMATURE":
        failures.append("advanced armature was not created")
    if not baked_body or baked_body.type != "MESH":
        failures.append("advanced baked body was not created")

    if baked_body:
        baked_points = object_mesh_points(baked_body)
        max_data_error = max_point_error(source_points, baked_points)
        max_eval_error = max_point_error(source_points, evaluated_mesh_points(baked_body))
        if max_data_error > 1e-5:
            failures.append(f"advanced baked body mesh does not match source evaluated data: {max_data_error}")
        if max_eval_error > 1e-5:
            failures.append(f"advanced baked body evaluated result is not stable at rest: {max_eval_error}")
        if baked_body.data.shape_keys:
            failures.append("advanced baked body should not have shape keys")
        armature_mods = [mod for mod in baked_body.modifiers if mod.type == "ARMATURE"]
        if len(armature_mods) != 1:
            failures.append("advanced baked body should have exactly one armature modifier")
        elif armature_mods[0].object != new_armature:
            failures.append("advanced baked body armature modifier does not point to new armature")
        if len(baked_body.vertex_groups) != len(mesh_obj.vertex_groups):
            failures.append("advanced baked body should copy source vertex groups")
        if baked_body.parent != new_armature:
            failures.append("advanced baked body should be parented to the new armature")
    else:
        baked_points = []
        max_data_error = float("inf")
        max_eval_error = float("inf")

    if new_armature:
        new_lowerarm_head = bone_world_point(new_armature, "lowerarm_l", "head_local")
        new_hand_head = bone_world_point(new_armature, "hand_l", "head_local")
        new_clavicle_head = bone_world_point(new_armature, "clavicle_l", "head_local")
        lowerarm_shift = new_lowerarm_head - original_lowerarm_head
        hand_shift = new_hand_head - original_hand_head
        clavicle_shift = new_clavicle_head - original_clavicle_head
        if lowerarm_shift.dot(original_upper_axis) <= 0.001:
            failures.append("lowerarm head should move outward along upperarm length axis")
        if hand_shift.length <= lowerarm_shift.length:
            failures.append("hand should include upperarm and lowerarm length shifts")
        if clavicle_shift.z <= 0.001:
            failures.append("clavicle should move upward with torso height in advanced rest pose")
        pose_constraint_count = sum(len(pose_bone.constraints) for pose_bone in new_armature.pose.bones)
        if pose_constraint_count:
            failures.append("advanced armature should not keep pose constraints")
        rest_eval_points = evaluated_mesh_points(baked_body) if baked_body else []
        pose_bone = new_armature.pose.bones.get("lowerarm_l")
        if pose_bone and baked_body:
            pose_bone.rotation_mode = "XYZ"
            pose_bone.rotation_euler[0] = 0.25
            bpy.context.view_layer.update()
            pose_deform_error = max_point_error(rest_eval_points, evaluated_mesh_points(baked_body))
            pose_bone.rotation_euler[0] = 0.0
            bpy.context.view_layer.update()
            if pose_deform_error <= 1e-4:
                failures.append("advanced body should deform when posing the new armature")
        else:
            pose_deform_error = 0.0
    else:
        lowerarm_shift = hand_shift = clavicle_shift = None
        pose_constraint_count = -1
        pose_deform_error = 0.0

    current_shape_count = len(mesh_obj.data.shape_keys.key_blocks) if mesh_obj.data.shape_keys else 0
    if current_shape_count != original_shape_count:
        failures.append("source body shape keys changed during advanced bake")

    OUT.write_text(
        json.dumps(
            {
                "version": list(module.bl_info["version"]),
                "result": result,
                "auto_apply_before_bake": auto_apply,
                "source_shape_keys": original_shape_count,
                "source_shape_keys_after": current_shape_count,
                "body_vertex_count": len(source_points),
                "baked_body_vertex_count": len(baked_points),
                "max_body_data_world_error": max_data_error,
                "max_body_evaluated_world_error": max_eval_error,
                "lowerarm_head_shift": list(lowerarm_shift) if lowerarm_shift else None,
                "hand_head_shift": list(hand_shift) if hand_shift else None,
                "clavicle_head_shift": list(clavicle_shift) if clavicle_shift else None,
                "pose_constraint_count": pose_constraint_count,
                "pose_deform_error": pose_deform_error,
                "failures": failures,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

