import importlib.util
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "addon" / "metahuman_blender_pipeline" / "__init__.py"
OUT = WORKSPACE / "test_results" / "language_builtin_torso_guides_metrics.json"
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


def summarize(values):
    values = [float(v) for v in values if v is not None]
    if not values:
        return {"count": 0, "mean": 0.0, "max": 0.0}
    return {"count": len(values), "mean": sum(values) / len(values), "max": max(values)}


class FakeSettings:
    def __init__(self):
        self.interface_language = "ZH"
        self.status = ""
        self.use_builtin_metahuman = True
        self.dcc_export_root = ""
        self.character_name = ""


class FakeScene:
    def __init__(self):
        self.mharp_settings = FakeSettings()


class FakeContext:
    def __init__(self):
        self.scene = FakeScene()


def torso_distribution(module, mesh_obj, armature, dashboard, prop):
    item = next(item for item in module.PROPORTION_DEFS if item["prop"] == prop)
    center = module.average_axis_center_local(mesh_obj, armature, item["axis_bones"])
    _low_z, _high_z, unit = module.torso_height_data(mesh_obj, armature)
    buckets = {"front": [], "back": [], "side": [], "side_back": []}
    for vertex in mesh_obj.data.vertices:
        group_name, _weight = primary_group(mesh_obj, vertex)
        if not module.is_torso_width_vertex_group(group_name):
            continue
        co = vertex.co
        rel = co - center
        normal = Vector((vertex.normal.x, vertex.normal.y, vertex.normal.z))
        _delta, weight = module.torso_width_delta(mesh_obj, armature, dashboard, item, co, normal, group_name)
        if weight <= 0.0:
            continue
        if rel.y > unit * 0.08:
            buckets["front"].append(weight)
        if rel.y < -unit * 0.08:
            buckets["back"].append(weight)
        if abs(rel.x) > unit * 0.24:
            buckets["side"].append(weight)
        if abs(rel.x) > unit * 0.20 and rel.y < -unit * 0.02:
            buckets["side_back"].append(weight)
    return {name: summarize(values) for name, values in buckets.items()}


def main():
    module = load_addon_module()
    failures = []

    fake_context = FakeContext()
    if module.ui_language(fake_context.scene.mharp_settings) != "ZH":
        failures.append("default interface language should be Chinese")
    module.MHARP_OT_toggle_ui_language.execute(object(), fake_context)
    if fake_context.scene.mharp_settings.interface_language != "EN":
        failures.append("language toggle did not switch to English")
    module.MHARP_OT_toggle_ui_language.execute(object(), fake_context)
    if fake_context.scene.mharp_settings.interface_language != "ZH":
        failures.append("language toggle did not switch back to Chinese")

    controls = module.control_objects()
    if controls:
        fake_context.scene.mharp_settings.interface_language = "ZH"
        zh_result = module.apply_scene_language_artifacts(fake_context.scene.mharp_settings)
        if not any(obj.name.startswith("控制_MH_") for obj in controls):
            failures.append("Chinese language should rename ControlRig handles to Chinese display names")
        fake_context.scene.mharp_settings.interface_language = "EN"
        en_result = module.apply_scene_language_artifacts(fake_context.scene.mharp_settings)
        if not any(obj.name.startswith("CTRL_MH_") for obj in controls):
            failures.append("English language should rename ControlRig handles back to CTRL_MH names")
    else:
        zh_result = {"control_rig": {"controls": 0, "renamed": 0}}
        en_result = {"control_rig": {"controls": 0, "renamed": 0}}

    source = module.resolve_metahuman_source(fake_context.scene.mharp_settings)
    if not source["face_fbx"] or not source["face_fbx"].exists():
        failures.append("bundled Face FBX was not resolved")
    if not source["body_fbx"] or not source["body_fbx"].exists():
        failures.append("bundled Body FBX was not resolved")
    if not source["maps"] or not source["maps"].exists():
        failures.append("bundled Maps folder was not resolved")

    mesh_obj = bpy.data.objects.get("MH_Body_LOD0")
    armature = bpy.data.objects.get("MH_Body_Root")
    dashboard = module.create_dashboard()
    fake_context.scene.mharp_settings.interface_language = "ZH"
    guide_result = module.create_or_update_torso_guides(mesh_obj, armature, dashboard, reset=True)
    navel_label = bpy.data.objects.get(module.torso_guide_label_object_name("abdomen_front"))
    if not navel_label or navel_label.data.body != "肚脐眼":
        failures.append("Chinese torso guide text label was not created")
    fake_context.scene.mharp_settings.interface_language = "EN"
    module.apply_scene_language_artifacts(fake_context.scene.mharp_settings)
    if navel_label and navel_label.data.body != "navel":
        failures.append("English language should update torso guide text labels")
    fake_context.scene.mharp_settings.interface_language = "ZH"
    module.apply_scene_language_artifacts(fake_context.scene.mharp_settings)

    defaults = {
        "胸部.粗细.法向混合": dashboard["胸部.粗细.法向混合"],
        "腰部.粗细.法向混合": dashboard["腰部.粗细.法向混合"],
        "胯部.粗细.法向混合": dashboard["胯部.粗细.法向混合"],
    }
    if abs(defaults["胸部.粗细.法向混合"] - 0.85) > 1e-6:
        failures.append("chest normal mix default should be 0.85")
    if abs(defaults["腰部.粗细.法向混合"] - 0.85) > 1e-6:
        failures.append("waist normal mix default should be 0.85")
    if abs(defaults["胯部.粗细.法向混合"] - 0.90) > 1e-6:
        failures.append("pelvis normal mix default should be 0.90")

    dashboard["躯干.高度.胸权重"] = module.PROPORTION_PROFILE_PARAMS["躯干.高度.胸权重"]["default"] + 0.10
    chest_boosted = module.boosted_profile_weight(dashboard, "躯干.高度.胸权重")
    if abs(chest_boosted - (module.PROPORTION_PROFILE_PARAMS["躯干.高度.胸权重"]["default"] + 0.20)) > 1e-6:
        failures.append("torso height weight edits should be boosted 2x")

    distributions = {
        prop: torso_distribution(module, mesh_obj, armature, dashboard, prop)
        for prop in ("胸部粗细", "腰部粗细", "胯部粗细")
    }
    chest = distributions["胸部粗细"]
    waist = distributions["腰部粗细"]
    pelvis = distributions["胯部粗细"]
    if chest["front"]["mean"] <= chest["back"]["mean"]:
        failures.append("chest guide field should favor front over back")
    if chest["side"]["mean"] > chest["front"]["mean"] * 0.85:
        failures.append("chest guide field side rib influence is too high")
    waist_active = max(waist["front"]["mean"], waist["side"]["mean"])
    if waist["back"]["mean"] > waist_active * 0.65:
        failures.append("waist/abdomen guide field should suppress back influence")
    if pelvis["back"]["mean"] <= 0.0:
        failures.append("pelvis guide field should include rear glute support")
    if pelvis["front"]["mean"] <= pelvis["back"]["mean"] * 1.20:
        failures.append("pelvis guide field should still favor low front over rear glutes")
    if pelvis["side_back"]["mean"] > max(pelvis["front"]["mean"], pelvis["back"]["mean"]) * 0.75:
        failures.append("pelvis guide field side/back influence is too broad")

    OUT.write_text(
        json.dumps(
            {
                "version": list(module.bl_info["version"]),
                "bundled_source": {k: str(v) for k, v in source.items() if k in {"dcc_export", "character_dir", "maps", "face_fbx", "body_fbx"}},
                "control_language": {"zh": zh_result, "en": en_result},
                "guide_language": guide_result,
                "normal_mix_defaults": defaults,
                "chest_weight_boosted": chest_boosted,
                "distributions": distributions,
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

