import importlib.util
import json
import sys
from pathlib import Path

import bpy


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "addon" / "metahuman_blender_pipeline" / "__init__.py"
OUT = WORKSPACE / "test_results" / "reset_group_defaults_metrics.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def load_addon():
    spec = importlib.util.spec_from_file_location("metahuman_blender_pipeline_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.register()
    return module


def dirty_value(default):
    if abs(float(default) - 1.0) > 0.001:
        return 1.0
    return 1.7


def main():
    module = load_addon()
    failures = []
    try:
        dashboard = module.create_dashboard()
        module.record_profile_build_snapshot(dashboard)
        group_name = "上肢长度"
        prop_names = module.proportion_group_props(group_name)
        unrelated_prop = "大腿长度"
        dashboard[unrelated_prop] = 2.25

        for prop_name in prop_names:
            default = module.proportion_param_default(prop_name)
            if default is not None:
                dashboard[prop_name] = dirty_value(default)

        dirty_before, missing_before = module.dirty_profile_params(dashboard)
        result = bpy.ops.mharp.reset_proportion_group_defaults(group_name=group_name)
        dirty_after, missing_after = module.dirty_profile_params(dashboard)
        apply_info = dict(bpy.context.scene.get("mharp_last_reset_group_apply", {}))

        if "FINISHED" not in result:
            failures.append(f"operator returned {sorted(result)}")
        for prop_name in prop_names:
            default = module.proportion_param_default(prop_name)
            if default is None:
                continue
            actual = float(dashboard[prop_name])
            if abs(actual - float(default)) > 1e-8:
                failures.append(f"{prop_name} expected {default} got {actual}")
        if abs(float(dashboard[unrelated_prop]) - 2.25) > 1e-8:
            failures.append("reset changed unrelated main control")
        if missing_after or dirty_after:
            failures.append(f"reset default apply should clean profile dirty state, got {dirty_after}")
        if not apply_info.get("needs_rebuild"):
            failures.append("reset group apply did not request rebuild for strategy params")
        if apply_info.get("applied") != "已应用并重建":
            failures.append(f"reset group apply did not rebuild, got {apply_info.get('applied')}")
        if not dashboard.get(module.PROFILE_BUILD_SNAPSHOT_PROP):
            failures.append("rebuild did not record profile snapshot")

        group_action_summary = {}
        for name, names in module.PROPORTION_PARAM_GROUPS:
            group_action_summary[name] = sorted({module.param_action_kind(prop_name) for prop_name in names})

        OUT.write_text(
            json.dumps(
                {
                    "version": list(module.bl_info["version"]),
                    "group_checked": group_name,
                    "dirty_before": dirty_before,
                    "missing_before": missing_before,
                    "dirty_after": dirty_after,
                    "missing_after": missing_after,
                    "apply_info": apply_info,
                    "group_action_summary": group_action_summary,
                    "failures": failures,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if failures:
            raise SystemExit(1)
    finally:
        try:
            module.unregister()
        except Exception:
            pass


if __name__ == "__main__":
    main()

