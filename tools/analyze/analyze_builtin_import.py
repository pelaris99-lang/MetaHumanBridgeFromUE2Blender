import importlib.util
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "addon" / "metahuman_blender_pipeline" / "__init__.py"
OUT = WORKSPACE / "test_results" / "builtin_import_metrics.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def load_addon_module():
    spec = importlib.util.spec_from_file_location("metahuman_blender_pipeline_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def world_bbox_height(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return max(corner.z for corner in corners) - min(corner.z for corner in corners)


def main():
    module = load_addon_module()
    module.register()
    failures = []
    try:
        settings = bpy.context.scene.mharp_settings
        settings.use_builtin_metahuman = True
        settings.dcc_export_root = ""
        settings.make_backup = False
        scan_result = bpy.ops.mharp.scan_files()
        import_result = bpy.ops.mharp.import_metahuman()
        body = bpy.data.objects.get("MH_Body_LOD0")
        face = bpy.data.objects.get("MH_Face_LOD0")
        if "FINISHED" not in scan_result:
            failures.append(f"scan failed: {scan_result}")
        if "FINISHED" not in import_result:
            failures.append(f"import failed: {import_result}")
        if not body:
            failures.append("MH_Body_LOD0 was not imported")
        if not face:
            failures.append("MH_Face_LOD0 was not imported")
        height = world_bbox_height(body) if body else 0.0
        if body and not (1.0 <= height <= 2.2):
            failures.append(f"body height out of expected meter range: {height}")
        OUT.write_text(
            json.dumps(
                {
                    "version": list(module.bl_info["version"]),
                    "character_name": settings.character_name,
                    "dcc_export_root": settings.dcc_export_root,
                    "scan_result": sorted(scan_result),
                    "import_result": sorted(import_result),
                    "body_height": height,
                    "body_exists": bool(body),
                    "face_exists": bool(face),
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

