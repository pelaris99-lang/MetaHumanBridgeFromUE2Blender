import importlib.util
import json
import sys
from pathlib import Path

import bpy


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "addon" / "metahuman_blender_pipeline" / "__init__.py"
OUT = WORKSPACE / "test_results" / "weight_paint_from_control_smoke_metrics.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def load_addon_module():
    spec = importlib.util.spec_from_file_location("metahuman_blender_pipeline_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_quad_mesh(name, offset=0.0):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(
        [(-0.5, offset, 0.0), (0.5, offset, 0.0), (0.5, offset, 1.0), (-0.5, offset, 1.0)],
        [],
        [(0, 1, 2, 3)],
    )
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def make_control(module, bone_name):
    mesh = bpy.data.meshes.new("CTRL_MH_Bone_Mesh")
    mesh.from_pydata([(0, 0, 0), (0, 0, 0.25)], [(0, 1)], [])
    mesh.update()
    control = bpy.data.objects.new("CTRL_MH_Bone", mesh)
    bpy.context.scene.collection.objects.link(control)
    module.tag_control_object(control, bone_name)
    return control


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
        bpy.ops.object.armature_add(enter_editmode=False, location=(0, 0, 0))
        armature = bpy.context.object
        armature.name = "MH_Body_Root"
        bone_name = armature.pose.bones[0].name

        body = make_quad_mesh("MH_Body_LOD0")
        body.vertex_groups.new(name=bone_name).add([0, 1, 2, 3], 1.0, "REPLACE")
        body_modifier = body.modifiers.new("MH_Body_Armature", "ARMATURE")
        body_modifier.object = armature

        cloth = make_quad_mesh("SmokeSleeve", 0.2)
        live_transfer = cloth.modifiers.new("MH_Cloth_Weight_Projection", "DATA_TRANSFER")
        module.configure_weight_transfer_modifier(live_transfer, body)
        control = make_control(module, bone_name)

        settings = bpy.context.scene.mharp_settings
        settings.armature_name = armature.name
        settings.body_mesh_name = body.name

        bpy.ops.object.select_all(action="DESELECT")
        cloth.select_set(True)
        control.select_set(True)
        bpy.context.view_layer.objects.active = control

        result = module.enter_cloth_weight_paint_from_control(bpy.context, settings)
        active = bpy.context.view_layer.objects.active
        active_group = cloth.vertex_groups.active.name if cloth.vertex_groups.active else ""
        active_weight = group_weight_sum(cloth, bone_name)
        cloth_armatures = [modifier for modifier in cloth.modifiers if modifier.type == "ARMATURE"]
        live_transfers = [modifier for modifier in cloth.modifiers if modifier.type == "DATA_TRANSFER"]

        if active != cloth:
            failures.append(f"active object is not cloth: {active.name if active else ''}")
        if cloth.mode != "WEIGHT_PAINT":
            failures.append(f"cloth is not in weight paint mode: {cloth.mode}")
        if active_group != bone_name:
            failures.append(f"active vertex group is {active_group}, expected {bone_name}")
        if active_weight <= 0.0:
            failures.append(f"active vertex group has no baked weights: {active_weight}")
        if result["bone"] != bone_name or result["group"] != bone_name:
            failures.append(f"wrong result bone/group: {result}")
        if not cloth_armatures or cloth_armatures[0].object != armature:
            failures.append("cloth armature modifier was not prepared")
        if live_transfers:
            failures.append(f"live data transfer modifiers remain: {[modifier.name for modifier in live_transfers]}")

        OUT.write_text(
            json.dumps(
                {
                    "version": list(module.bl_info["version"]),
                    "result": result,
                    "active_object": active.name if active else "",
                    "active_group": active_group,
                    "active_group_weight": active_weight,
                    "cloth_mode": cloth.mode,
                    "armature_modifiers": [modifier.name for modifier in cloth_armatures],
                    "data_transfer_modifiers": [modifier.name for modifier in live_transfers],
                    "failures": failures,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        try:
            if bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
        module.unregister()
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
