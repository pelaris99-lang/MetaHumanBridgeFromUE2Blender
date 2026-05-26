import importlib.util
import json
import sys
from pathlib import Path

import bpy


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "addon" / "metahuman_blender_pipeline" / "__init__.py"
OUT = WORKSPACE / "test_results" / "static_bake_copy_metrics.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def load_addon_module():
    spec = importlib.util.spec_from_file_location("metahuman_blender_pipeline_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeSettings:
    body_mesh_name = "MH_Body_LOD0"


def ensure_current_shape_keys(module, mesh_obj, armature, dashboard):
    existing = mesh_obj.data.shape_keys.key_blocks if mesh_obj.data.shape_keys else {}
    missing = [item for item in module.PROPORTION_DEFS if f"MH_{module.safe_name(item['prop'])}" not in existing]
    if missing:
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
        "上臂长度": 1.70,
        "小臂粗细": 1.45,
        "躯干高度": 1.35,
        "胸部粗细": 1.55,
        "腰部粗细": 1.40,
        "胯部粗细": 1.45,
    }.items():
        if prop in dashboard:
            dashboard[prop] = value
    bpy.context.view_layer.update()

    original_shape_count = len(mesh_obj.data.shape_keys.key_blocks) if mesh_obj.data.shape_keys else 0
    original_data_name = mesh_obj.data.name
    result = module.bake_current_proportion_static_copy(FakeSettings())
    source_points = evaluated_mesh_points(mesh_obj)
    auto_apply = json_safe(bpy.context.scene.get("mharp_auto_apply_before_bake", {}))
    baked_body = bpy.data.objects.get(result["objects"][0])
    if not baked_body:
        failures.append("baked body object was not created")
        baked_points = []
        max_error = float("inf")
    else:
        baked_points = object_mesh_points(baked_body)
        max_error = max_point_error(source_points, baked_points)
        if max_error > 1e-5:
            failures.append(f"baked mesh does not match evaluated body: max_error={max_error}")
        if baked_body.data.shape_keys:
            failures.append("baked body should not have shape keys")
        if baked_body.animation_data or baked_body.data.animation_data:
            failures.append("baked body should not have animation data or drivers")
        if baked_body.modifiers:
            failures.append("baked body should not keep modifiers")
        if baked_body.parent:
            failures.append("baked body should not keep a parent")

    if mesh_obj.data.name != original_data_name:
        failures.append("source body mesh data was replaced")
    current_shape_count = len(mesh_obj.data.shape_keys.key_blocks) if mesh_obj.data.shape_keys else 0
    if current_shape_count != original_shape_count:
        failures.append("source body shape keys changed during static bake")

    face_names = [name for name in result["objects"] if "Face" in name]
    if not face_names:
        failures.append("baked face LOD0 object was not created")
    else:
        face_obj = bpy.data.objects.get(face_names[0])
        if face_obj and (face_obj.data.shape_keys or face_obj.modifiers or face_obj.parent):
            failures.append("baked face should be static without shape keys/modifiers/parent")

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
                "max_body_world_error": max_error,
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

