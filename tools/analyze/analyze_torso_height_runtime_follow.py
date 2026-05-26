import importlib.util
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "addon" / "metahuman_blender_pipeline" / "__init__.py"
OUT = WORKSPACE / "test_results" / "torso_height_runtime_follow_metrics.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def load_addon_module():
    spec = importlib.util.spec_from_file_location("metahuman_blender_pipeline_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def primary_group(mesh_obj, vertex):
    best_name = None
    best_weight = 0.0
    groups = mesh_obj.vertex_groups
    for item in vertex.groups:
        if item.weight > best_weight:
            best_weight = float(item.weight)
            best_name = groups[item.group].name
    return best_name, best_weight


def group_bucket(name):
    if not name:
        return None
    lowered = name.lower()
    for token in ("clavicle", "upperarm", "lowerarm", "hand", "wrist", "metacarpal", "thumb_", "index_", "middle_", "ring_", "pinky_"):
        if lowered.startswith(token) or token in lowered:
            return token.replace("_", "")
    if lowered.startswith(("neck", "head")):
        return "head_neck"
    return None


def summarize(values):
    if not values:
        return {"count": 0}
    values = sorted(float(v) for v in values)
    return {
        "count": len(values),
        "min": values[0],
        "max": values[-1],
        "mean": sum(values) / len(values),
        "p05": values[int((len(values) - 1) * 0.05)],
        "p50": values[int((len(values) - 1) * 0.50)],
        "p95": values[int((len(values) - 1) * 0.95)],
    }


def object_eval_center_z(obj, depsgraph):
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    try:
        if not mesh.vertices:
            return float(eval_obj.matrix_world.translation.z)
        total = 0.0
        for vertex in mesh.vertices:
            total += (eval_obj.matrix_world @ vertex.co).z
        return total / len(mesh.vertices)
    finally:
        eval_obj.to_mesh_clear()


def main():
    module = load_addon_module()
    mesh_obj = bpy.data.objects.get("MH_Body_LOD0")
    armature = bpy.data.objects.get("MH_Body_Root")
    if not mesh_obj or not armature:
        raise SystemExit("Need MH_Body_LOD0 and MH_Body_Root")
    dashboard = module.create_dashboard()
    item = next(item for item in module.PROPORTION_DEFS if item["prop"] == "躯干高度")
    module.build_shape_key(mesh_obj, armature, dashboard, item)
    module.sync_control_rig_proportion_follow(mesh_obj, armature, dashboard)
    module.record_profile_build_snapshot(dashboard)

    bpy.context.view_layer.update()
    basis = mesh_obj.data.shape_keys.key_blocks["Basis"]
    shape = mesh_obj.data.shape_keys.key_blocks["MH_躯干高度"]
    shape_delta_by_bucket = {}
    for vertex in mesh_obj.data.vertices:
        group_name, _weight = primary_group(mesh_obj, vertex)
        bucket = group_bucket(group_name)
        if not bucket:
            continue
        dz = shape.data[vertex.index].co.z - basis.data[vertex.index].co.z
        shape_delta_by_bucket.setdefault(bucket, []).append(dz)

    controls = [
        "CTRL_MH_clavicle_l",
        "CTRL_MH_upperarm_l",
        "CTRL_MH_lowerarm_l",
        "CTRL_MH_hand_l",
        "CTRL_MH_middle_metacarpal_l",
        "CTRL_MH_index_01_l",
    ]
    depsgraph = bpy.context.evaluated_depsgraph_get()
    control_before = {
        name: object_eval_center_z(bpy.data.objects[name], depsgraph)
        for name in controls
        if bpy.data.objects.get(name)
    }
    dashboard["躯干高度"] = 2.0
    dashboard.update_tag()
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    control_after = {
        name: object_eval_center_z(bpy.data.objects[name], depsgraph)
        for name in control_before
    }
    control_delta = {name: control_after[name] - control_before[name] for name in control_before}

    body_world_scale = module.average_matrix_scale(mesh_obj.matrix_world)
    expected_runtime = module.torso_height_data(mesh_obj, armature)[2] * body_world_scale * item["driver_strength"]
    failures = []
    for bucket in ("lowerarm", "hand", "metacarpal", "index"):
        stats = summarize(shape_delta_by_bucket.get(bucket, []))
        if stats.get("count", 0) == 0:
            failures.append(f"no shape-key vertices for {bucket}")
        elif abs(stats["p50"]) > 1e-6:
            failures.append(f"{bucket} should not be moved directly by torso height shape key after control follow drivers")
    for name, delta in control_delta.items():
        if "lowerarm" in name or "hand" in name or "metacarpal" in name or "index" in name:
            if delta < 0.85 * expected_runtime:
                failures.append(f"{name} evaluated control visual did not move enough: {delta}")

    OUT.write_text(
        json.dumps(
            {
                "version": list(module.bl_info["version"]),
                "expected_runtime_delta": expected_runtime,
                "shape_delta_by_bucket": {k: summarize(v) for k, v in shape_delta_by_bucket.items()},
                "control_delta": control_delta,
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

