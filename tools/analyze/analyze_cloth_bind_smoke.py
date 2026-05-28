import importlib.util
import json
import sys
from pathlib import Path

import bpy


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "addon" / "metahuman_blender_pipeline" / "__init__.py"
OUT = WORKSPACE / "test_results" / "cloth_bind_smoke_metrics.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def load_addon_module():
    spec = importlib.util.spec_from_file_location("metahuman_blender_pipeline_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_quad_object(name, z):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(
        [(-1, -1, z), (1, -1, z), (1, 1, z), (-1, 1, z)],
        [],
        [(0, 1, 2, 3)],
    )
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def group_weight_sum(obj, group_name):
    group = obj.vertex_groups.get(group_name)
    if group is None:
        return 0.0
    total = 0.0
    for vertex in obj.data.vertices:
        for assignment in vertex.groups:
            if assignment.group == group.index:
                total += assignment.weight
    return total


def main():
    module = load_addon_module()
    module.register()
    failures = []
    result = {}
    try:
        body = make_quad_object("MH_Body_LOD0", 0.0)
        pelvis = body.vertex_groups.new(name="pelvis")
        pelvis.add([0, 1, 2, 3], 0.6, "REPLACE")
        spine = body.vertex_groups.new(name="spine_01")
        spine.add([0, 1, 2, 3], 0.4, "REPLACE")

        wrong_arm_data = bpy.data.armatures.new("Old_Cloth_Armature_Data")
        wrong_armature = bpy.data.objects.new("Old_Cloth_Armature", wrong_arm_data)
        bpy.context.scene.collection.objects.link(wrong_armature)

        arm_data = bpy.data.armatures.new("MH_Body_Root_Armature")
        armature = bpy.data.objects.new("MH_Body_Root", arm_data)
        bpy.context.scene.collection.objects.link(armature)
        body_armature = body.modifiers.new("MH_Body_Armature", "ARMATURE")
        body_armature.object = armature

        cloth = make_quad_object("SmokeVest", 0.05)
        cloth.parent = armature
        cloth["mharp_cloth_bound_to_body"] = True
        stale_modifier = cloth.modifiers.new("Old_Cloth_Armature", "ARMATURE")
        stale_modifier.object = wrong_armature
        settings = bpy.context.scene.mharp_settings
        settings.armature_name = wrong_armature.name
        settings.body_mesh_name = body.name
        bpy.ops.object.select_all(action="DESELECT")
        cloth.select_set(True)
        bpy.context.view_layer.objects.active = cloth

        result = module.bind_selected_clothes_to_body(bpy.context, settings)
        if result["count"] != 1:
            failures.append(f"expected one bound target, got {result['count']}")
        direct_transfer = result["targets"][0].get("direct_weight_transfer", {})
        if direct_transfer.get("assigned_vertices", 0) != len(cloth.data.vertices):
            failures.append(f"direct weights were not written to every cloth vertex: {direct_transfer}")
        for group_name in ("pelvis", "spine_01"):
            if cloth.vertex_groups.get(group_name) is None:
                failures.append(f"missing transferred group: {group_name}")
            if group_weight_sum(cloth, group_name) <= 0.0:
                failures.append(f"transferred group has no weights: {group_name}")
        if not any(mod.type == "ARMATURE" and mod.object == armature for mod in cloth.modifiers):
            failures.append("missing cloth armature modifier")
        if any(mod.type == "ARMATURE" and mod.object == wrong_armature for mod in cloth.modifiers):
            failures.append("stale cloth armature modifier was not removed")
        if cloth.parent is not None:
            failures.append("cloth should not be parented by the binding operator")
        if result["armature"] != armature.name:
            failures.append(f"body driver armature was not preferred: {result['armature']}")
        if result["removed_armature_modifier_count"] != 1:
            failures.append(f"expected one stale armature removal, got {result['removed_armature_modifier_count']}")
        if result["detached_parent_count"] != 1:
            failures.append(f"expected one stale parent detach, got {result['detached_parent_count']}")
        if not cloth.get("mharp_cloth_bound_to_body"):
            failures.append("missing cloth binding marker")
        OUT.write_text(
            json.dumps(
                {
                    "version": list(module.bl_info["version"]),
                    "result": result,
                    "cloth_vertex_groups": [group.name for group in cloth.vertex_groups],
                    "cloth_weight_sums": {
                        "pelvis": group_weight_sum(cloth, "pelvis"),
                        "spine_01": group_weight_sum(cloth, "spine_01"),
                    },
                    "cloth_modifiers": [modifier.type for modifier in cloth.modifiers],
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
