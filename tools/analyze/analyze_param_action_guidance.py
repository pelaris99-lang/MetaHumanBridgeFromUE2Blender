import importlib.util
import json
import sys
from pathlib import Path

import bpy


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "addon" / "metahuman_blender_pipeline" / "__init__.py"
OUT = WORKSPACE / "test_results" / "param_action_guidance_metrics.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def load_addon_module():
    spec = importlib.util.spec_from_file_location("metahuman_blender_pipeline_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    module = load_addon_module()
    dashboard = module.create_dashboard()
    failures = []

    expected_labels = {
        "上臂长度": "实时",
        "躯干高度": "实时",
        "上臂粗细": "实时",
        "胸部粗细": "实时",
        "四肢.长度.骨末端衰减": "需应用",
        "上肢.粗细.法向混合": "需应用",
        "躯干.高度.腰权重": "需应用",
    }
    actual_labels = {name: module.param_action_label(name) for name in expected_labels}
    for name, expected in expected_labels.items():
        if actual_labels[name] != expected:
            failures.append(f"{name} action label expected {expected} got {actual_labels[name]}")

    dirty, snapshot_missing = module.dirty_profile_params(dashboard)
    if not snapshot_missing or len(dirty) != len(module.PROPORTION_PROFILE_PARAMS):
        failures.append("new dashboard without snapshot should ask for rebuild guidance")

    module.record_profile_build_snapshot(dashboard)
    dirty_after_record, snapshot_missing_after_record = module.dirty_profile_params(dashboard)
    if snapshot_missing_after_record or dirty_after_record:
        failures.append("recorded profile snapshot should be clean")

    dashboard["躯干.高度.腰权重"] = float(dashboard["躯干.高度.腰权重"]) + 0.25
    dirty_after_change, snapshot_missing_after_change = module.dirty_profile_params(dashboard)
    if snapshot_missing_after_change or dirty_after_change != ["躯干.高度.腰权重"]:
        failures.append(f"dirty profile params did not isolate changed strategy param: {dirty_after_change}")

    OUT.write_text(
        json.dumps(
            {
                "version": list(module.bl_info["version"]),
                "labels": actual_labels,
                "dirty_without_snapshot_count": len(dirty),
                "dirty_after_record": dirty_after_record,
                "dirty_after_change": dirty_after_change,
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

