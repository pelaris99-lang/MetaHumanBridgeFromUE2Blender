import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "addon" / "metahuman_blender_pipeline" / "__init__.py"
OUT = WORKSPACE / "test_results" / "pose_as_rest_smoke_metrics.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def load_addon_module():
    spec = importlib.util.spec_from_file_location("metahuman_blender_pipeline_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_body_mesh():
    mesh = bpy.data.meshes.new("MH_Body_LOD0_Mesh")
    mesh.from_pydata(
        [(-0.5, 0.0, 0.0), (0.5, 0.0, 0.0), (0.5, 0.0, 1.0), (-0.5, 0.0, 1.0)],
        [],
        [(0, 1, 2, 3)],
    )
    mesh.update()
    body = bpy.data.objects.new("MH_Body_LOD0", mesh)
    bpy.context.scene.collection.objects.link(body)
    group = body.vertex_groups.new(name="Bone")
    group.add([0, 1, 2, 3], 1.0, "REPLACE")
    return body


def max_abs_matrix_basis(pose_bone):
    values = []
    matrix = pose_bone.matrix_basis
    for row in range(4):
        for col in range(4):
            expected = 1.0 if row == col else 0.0
            values.append(abs(matrix[row][col] - expected))
    return max(values)


def evaluated_vertex_worlds(obj):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def max_point_delta(before, after):
    if len(before) != len(after):
        return float("inf")
    return max((a - b).length for a, b in zip(before, after))


def make_control(module, bone_name, matrix):
    mesh = bpy.data.meshes.new(f"{bone_name}_Control_Mesh")
    mesh.from_pydata([(0, 0, 0), (0, 0, 0.2)], [(0, 1)], [])
    mesh.update()
    control = bpy.data.objects.new(f"CTRL_MH_{bone_name}", mesh)
    control.matrix_world = matrix
    bpy.context.scene.collection.objects.link(control)
    module.tag_control_object(control, bone_name)
    return control


def main():
    module = load_addon_module()
    module.register()
    failures = []
    result = {}
    try:
        bpy.ops.object.armature_add(enter_editmode=False, location=(0, 0, 0))
        armature = bpy.context.object
        armature.name = "MH_Body_Root"
        armature.data.name = "MH_Body_Root_Armature"

        body = make_body_mesh()
        modifier = body.modifiers.new("MH_Body_Armature", "ARMATURE")
        modifier.object = armature

        settings = bpy.context.scene.mharp_settings
        settings.make_backup = False
        settings.hide_source_armature = True
        settings.armature_name = armature.name
        settings.body_mesh_name = body.name

        control = make_control(
            module,
            armature.pose.bones[0].name,
            Matrix.Rotation(math.radians(35.0), 4, "X"),
        )
        module.add_control_constraints(armature, {armature.pose.bones[0].name: control})
        bpy.context.view_layer.update()
        before_basis_delta = max_abs_matrix_basis(armature.pose.bones[0])
        before_points = evaluated_vertex_worlds(body)
        before_control_matrix = control.matrix_world.copy()

        module.hide_deform_rigs(armature, True)
        bpy.ops.object.select_all(action="DESELECT")
        body.select_set(True)
        bpy.context.view_layer.objects.active = body

        result = module.apply_current_body_pose_as_rest(bpy.context, settings)
        after_points = evaluated_vertex_worlds(body)
        point_delta = max_point_delta(before_points, after_points)
        after_basis_delta = max_abs_matrix_basis(armature.pose.bones[0])
        if result["armature"] != armature.name:
            failures.append(f"wrong armature: {result['armature']}")
        if after_basis_delta > 1e-4:
            failures.append(f"pose matrix basis was not cleared: {after_basis_delta}")
        if point_delta > 1e-4:
            failures.append(f"evaluated mesh moved after pose-as-rest: {point_delta}")
        if result["baked_control_constraints"] != 2:
            failures.append(f"expected two baked control constraints, got {result['baked_control_constraints']}")
        if result["restored_control_constraints"] != 2:
            failures.append(f"expected two restored control constraints, got {result['restored_control_constraints']}")
        if max_point_delta(
            [before_control_matrix @ Vector((0, 0, 0))],
            [control.matrix_world @ Vector((0, 0, 0))],
        ) > 1e-6:
            failures.append("control object moved during pose-as-rest")
        if not armature.get("mharp_pose_applied_as_rest_at"):
            failures.append("missing pose-as-rest marker")
        OUT.write_text(
            json.dumps(
                {
                    "version": list(module.bl_info["version"]),
                    "result": result,
                    "before_basis_delta": before_basis_delta,
                    "after_basis_delta": after_basis_delta,
                    "evaluated_mesh_point_delta": point_delta,
                    "control_constraints": {
                        "baked": result["baked_control_constraints"],
                        "restored": result["restored_control_constraints"],
                    },
                    "failures": failures,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        module.unregister()
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
