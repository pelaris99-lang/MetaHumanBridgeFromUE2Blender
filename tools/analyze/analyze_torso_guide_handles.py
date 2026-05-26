import importlib.util
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "addon" / "metahuman_blender_pipeline" / "__init__.py"
OUT = WORKSPACE / "test_results" / "torso_guide_handles_metrics.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def load_addon_module():
    spec = importlib.util.spec_from_file_location("metahuman_blender_pipeline_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def guide_center(module, mesh_obj, armature, dashboard, prop, guide_id):
    item = next(item for item in module.PROPORTION_DEFS if item["prop"] == prop)
    center = module.average_axis_center_local(mesh_obj, armature, item["axis_bones"])
    _low_z, _high_z, torso_height = module.torso_height_data(mesh_obj, armature)
    smooth = module.profile_param(dashboard, "躯干.粗细.边界平滑")
    plane_x = module.torso_symmetry_plane_x_local(mesh_obj, armature)
    guides = module.torso_width_guides(mesh_obj, prop, center, torso_height, smooth, plane_x)
    return next(guide["center"] for guide in guides if guide["id"] == guide_id), torso_height


def main():
    module = load_addon_module()
    mesh_obj = bpy.data.objects.get("MH_Body_LOD0")
    armature = bpy.data.objects.get("MH_Body_Root")
    dashboard = module.create_dashboard()
    failures = []
    result = module.create_or_update_torso_guides(mesh_obj, armature, dashboard, reset=True)
    expected_total = 12
    if result["total"] != expected_total:
        failures.append(f"expected {expected_total} torso guides, got {result['total']}")
    if result.get("labels") != expected_total:
        failures.append(f"expected {expected_total} torso guide labels, got {result.get('labels')}")

    guide_name = module.torso_guide_object_name("chest_l_front")
    guide_obj = bpy.data.objects.get(guide_name)
    if not guide_obj:
        failures.append("missing chest_l_front guide object")
    elif guide_obj.get("mharp_torso_guide_prop") != "胸部粗细":
        failures.append("guide custom prop did not record torso region")

    glute_guide_name = module.torso_guide_object_name("pelvis_l_back_glute")
    glute_guide_obj = bpy.data.objects.get(glute_guide_name)
    if not glute_guide_obj:
        failures.append("missing pelvis_l_back_glute guide object")
    elif glute_guide_obj.get("mharp_torso_guide_label") != "臀顶（左）":
        failures.append("glute rear guide label was not recorded")
    anus_label = bpy.data.objects.get(module.torso_guide_label_object_name("pelvis_back_center"))
    if not anus_label or anus_label.type != "FONT" or anus_label.data.body != "肛门":
        failures.append("center rear anatomy text label was not created")

    original_center, torso_height = guide_center(module, mesh_obj, armature, dashboard, "胸部粗细", "chest_l_front")
    plane_x = module.torso_symmetry_plane_x_local(mesh_obj, armature)
    moved_center = original_center + Vector((-torso_height * 0.05, torso_height * 0.10, 0.0))
    guide_obj.location = mesh_obj.matrix_world @ moved_center
    bpy.context.view_layer.update()
    sampled_center, _ = guide_center(module, mesh_obj, armature, dashboard, "胸部粗细", "chest_l_front")
    mirrored_center, _ = guide_center(module, mesh_obj, armature, dashboard, "胸部粗细", "chest_r_front")
    move_error = (sampled_center - moved_center).length
    if move_error > 1e-4:
        failures.append(f"moved guide was not read by torso field: error={move_error}")
    expected_mirror = moved_center.copy()
    expected_mirror.x = plane_x * 2.0 - expected_mirror.x
    mirror_error = (mirrored_center - expected_mirror).length
    right_guide_obj = bpy.data.objects.get(module.torso_guide_object_name("chest_r_front"))
    if mirror_error > 1e-4:
        failures.append(f"right ghost guide was not mirrored from left guide: error={mirror_error}")
    if not right_guide_obj or not right_guide_obj.get("mharp_torso_guide_is_ghost") or not right_guide_obj.hide_select:
        failures.append("right guide should be an unselectable ghost")

    abdomen_obj = bpy.data.objects.get(module.torso_guide_object_name("abdomen_front"))
    if abdomen_obj:
        abdomen_obj.location.x += torso_height * 0.20
        bpy.context.view_layer.update()
        abdomen_center, _ = guide_center(module, mesh_obj, armature, dashboard, "腰部粗细", "abdomen_front")
        if abs(abdomen_center.x - plane_x) > 1e-4:
            failures.append("center abdomen guide should stay locked on pelvis YZ plane")
    else:
        failures.append("missing abdomen center guide")

    module.create_or_update_torso_guides(mesh_obj, armature, dashboard, reset=True)
    reset_center, _ = guide_center(module, mesh_obj, armature, dashboard, "胸部粗细", "chest_l_front")
    reset_error = (reset_center - original_center).length
    if reset_error > 1e-4:
        failures.append(f"reset did not restore default guide location: error={reset_error}")

    hide_result = module.apply_torso_guide_visibility("HIDE")
    hidden_count = len([obj for obj in module.torso_guide_objects() if obj.hide_get()])
    hidden_label_count = len([obj for obj in module.torso_guide_label_objects() if obj.hide_get()])
    if hidden_count != expected_total:
        failures.append(f"hide guides should hide all {expected_total} objects, got {hidden_count}")
    if hidden_label_count != expected_total:
        failures.append(f"hide guides should hide all {expected_total} labels, got {hidden_label_count}")
    show_result = module.apply_torso_guide_visibility("SHOW")
    visible_count = len([obj for obj in module.torso_guide_objects() if not obj.hide_get()])
    visible_label_count = len([obj for obj in module.torso_guide_label_objects() if not obj.hide_get()])
    if visible_count != expected_total:
        failures.append(f"show guides should reveal all {expected_total} objects, got {visible_count}")
    if visible_label_count != expected_total:
        failures.append(f"show guides should reveal all {expected_total} labels, got {visible_label_count}")

    OUT.write_text(
        json.dumps(
            {
                "version": list(module.bl_info["version"]),
                "created": result,
                "guide_name": guide_name,
                "glute_guide_name": glute_guide_name,
                "move_error": move_error,
                "mirror_error": mirror_error,
                "reset_error": reset_error,
                "visibility": {
                    "hide": hide_result,
                    "hidden_count": hidden_count,
                    "hidden_label_count": hidden_label_count,
                    "show": show_result,
                    "visible_count": visible_count,
                    "visible_label_count": visible_label_count,
                },
                "guide_count": len(module.torso_guide_objects()),
                "label_count": len(module.torso_guide_label_objects()),
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

