import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "addon" / "metahuman_blender_pipeline" / "__init__.py"
OUT = WORKSPACE / "test_results" / "control_mirror_state_only_metrics.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def load_addon_module():
    spec = importlib.util.spec_from_file_location("metahuman_blender_pipeline_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def mesh_signature(obj):
    if obj.type != "MESH":
        return None
    verts = tuple((round(v.co.x, 8), round(v.co.y, 8), round(v.co.z, 8)) for v in obj.data.vertices)
    edges = tuple(tuple(edge.vertices) for edge in obj.data.edges)
    polys = tuple(tuple(poly.vertices) for poly in obj.data.polygons)
    shape_keys = []
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:
            shape_keys.append(
                (
                    key.name,
                    tuple((round(v.co.x, 8), round(v.co.y, 8), round(v.co.z, 8)) for v in key.data),
                )
            )
    return (verts, edges, polys, tuple(shape_keys))


def max_matrix_abs_delta(a, b):
    return max(abs(a[row][col] - b[row][col]) for row in range(4) for col in range(4))


def nudge_left_controls(module):
    names = [
        "CTRL_MH_clavicle_l",
        "CTRL_MH_upperarm_l",
        "CTRL_MH_lowerarm_l",
        "CTRL_MH_hand_l",
        "CTRL_MH_thigh_l",
        "CTRL_MH_calf_l",
        "CTRL_MH_foot_l",
    ]
    moved = []
    for index, name in enumerate(names, 1):
        obj = bpy.data.objects.get(name)
        if not obj:
            continue
        translation = Matrix.Translation(Vector((0.0, 0.015 * index, 0.006 * index)))
        rotation = Matrix.Rotation(math.radians(2.0 * index), 4, "Z")
        obj.matrix_world = translation @ obj.matrix_world @ rotation
        moved.append(name)
    bpy.context.view_layer.update()
    return moved


def main():
    module = load_addon_module()
    armature = bpy.data.objects.get("MH_Body_Root")
    if not armature:
        raise SystemExit("Need MH_Body_Root in test blend")
    moved = nudge_left_controls(module)
    mirror_op = module.get_mirror_operator(armature)
    pairs = []
    expected_worlds = {}
    target_mesh_before = {}
    for source in list(bpy.data.objects):
        target_name = module.counterpart_name(source.name, "_l", "_r")
        if not target_name:
            continue
        target = bpy.data.objects.get(target_name)
        if not target:
            continue
        pairs.append((source.name, target.name))
        expected_worlds[target.name] = mirror_op @ source.matrix_world.copy() @ mirror_op
        target_mesh_before[target.name] = mesh_signature(target)

    count = module.mirror_control_states("_l", "_r", armature)

    matrix_failures = []
    mesh_failures = []
    max_matrix_delta = 0.0
    for _source_name, target_name in pairs:
        target = bpy.data.objects.get(target_name)
        delta = max_matrix_abs_delta(target.matrix_world, expected_worlds[target_name])
        max_matrix_delta = max(max_matrix_delta, delta)
        if delta > 1e-5:
            matrix_failures.append({"target": target_name, "max_abs_delta": delta})
        if mesh_signature(target) != target_mesh_before[target_name]:
            mesh_failures.append(target_name)

    failures = []
    if count != len(pairs):
        failures.append(f"expected {len(pairs)} pairs but mirrored {count}")
    if matrix_failures:
        failures.append("target world matrices do not match mirrored source state")
    if mesh_failures:
        failures.append("mirror operation changed target mesh vertex data")

    OUT.write_text(
        json.dumps(
            {
                "version": list(module.bl_info["version"]),
                "nudged_left_controls": moved,
                "pair_count": len(pairs),
                "mirrored_count": count,
                "max_matrix_delta": max_matrix_delta,
                "matrix_failures": matrix_failures[:20],
                "mesh_failures": mesh_failures[:20],
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

