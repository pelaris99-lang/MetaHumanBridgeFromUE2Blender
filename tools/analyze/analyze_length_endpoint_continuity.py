import importlib.util
import json
import sys
from pathlib import Path

import bpy


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "addon" / "metahuman_blender_pipeline" / "__init__.py"
OUT = WORKSPACE / "test_results" / "length_endpoint_continuity_metrics.json"
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
    if not values:
        return {"count": 0}
    values = sorted(float(value) for value in values)
    return {
        "count": len(values),
        "min": values[0],
        "max": values[-1],
        "mean": sum(values) / len(values),
        "p05": values[int((len(values) - 1) * 0.05)],
        "p50": values[int((len(values) - 1) * 0.50)],
        "p95": values[int((len(values) - 1) * 0.95)],
    }


def item_by_prop(module, prop):
    return next(item for item in module.PROPORTION_DEFS if item["prop"] == prop)


def analyze_item(module, mesh_obj, armature, dashboard, prop):
    item = item_by_prop(module, prop)
    module.build_shape_key(mesh_obj, armature, dashboard, item)
    shape = mesh_obj.data.shape_keys.key_blocks["MH_" + module.safe_name(prop)]
    basis = mesh_obj.data.shape_keys.key_blocks["Basis"]
    all_group_names = {group.name for group in mesh_obj.vertex_groups}
    segment_endpoint_ratios = []
    follow_ratios = []
    segment_weights = []
    side_stats = {}
    axis_cache = {}

    for vertex in mesh_obj.data.vertices:
        group_name, weight = primary_group(mesh_obj, vertex)
        role = module.length_primary_role(prop, group_name)
        if role not in {"segment", "follow"}:
            continue
        side = module.vertex_group_side(group_name or "")
        if not side:
            continue
        bone = module.axis_bone_for_length_group(armature, item, group_name if role == "segment" else None, group_name)
        if not bone:
            continue
        head, axis, length = module.length_chain_axis_data(mesh_obj, armature, item, bone, side, axis_cache)
        if length <= 1e-8:
            continue
        co = basis.data[vertex.index].co
        t = module.clamp01((co - head).dot(axis) / length)
        delta = shape.data[vertex.index].co - co
        ratio = delta.dot(axis) / length
        side_bucket = side_stats.setdefault(side, {"segment_endpoint": [], "follow": []})
        if role == "segment" and t >= 0.92:
            segment_endpoint_ratios.append(ratio)
            segment_weights.append(weight)
            side_bucket["segment_endpoint"].append(ratio)
        elif role == "follow":
            follow_ratios.append(ratio)
            side_bucket["follow"].append(ratio)

    failures = []
    segment_summary = summarize(segment_endpoint_ratios)
    follow_summary = summarize(follow_ratios)
    if segment_summary["count"] == 0:
        failures.append("no segment endpoint vertices found")
    elif segment_summary["p05"] < 0.97:
        failures.append("segment endpoint vertices are still discounted below downstream offset")
    if follow_summary["count"] == 0:
        failures.append("no downstream follow vertices found")
    elif abs(follow_summary["p50"] - 1.0) > 0.02:
        failures.append("downstream follow vertices are not rigid endpoint followers")

    side_report = {}
    for side, values in side_stats.items():
        seg = summarize(values["segment_endpoint"])
        fol = summarize(values["follow"])
        gap = None
        if seg.get("count", 0) and fol.get("count", 0):
            gap = abs(seg["p50"] - fol["p50"])
            if gap > 0.04:
                failures.append(f"{prop}_{side} endpoint/follow median gap too large: {gap:.4f}")
        side_report[side] = {"segment_endpoint": seg, "follow": fol, "median_gap": gap}

    return {
        "prop": prop,
        "segment_endpoint_ratio": segment_summary,
        "segment_endpoint_weight": summarize(segment_weights),
        "follow_ratio": follow_summary,
        "side_report": side_report,
        "failures": failures,
    }


def main():
    module = load_addon_module()
    mesh_obj = bpy.data.objects.get("MH_Body_LOD0")
    armature = bpy.data.objects.get("MH_Body_Root")
    if not mesh_obj or not armature:
        raise SystemExit("Need MH_Body_LOD0 and MH_Body_Root in the test blend")
    dashboard = module.create_dashboard()
    for name, meta in module.PROPORTION_PROFILE_PARAMS.items():
        dashboard[name] = meta["default"]

    props = ["上臂长度", "小臂长度", "大腿长度", "小腿长度"]
    items = [analyze_item(module, mesh_obj, armature, dashboard, prop) for prop in props]
    failures = [failure for item in items for failure in item["failures"]]
    OUT.write_text(
        json.dumps(
            {
                "version": list(module.bl_info["version"]),
                "items": items,
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

