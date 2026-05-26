# Engineering Notes

## Product Boundary

MetaForge is a Blender-side bridge and control layer for MetaHuman DCC exports. It should make the imported character inspectable and editable in Blender without corrupting scale, hiding recoverable LODs, or forcing long-running body-shape generation into the default import path.

## Add-on Architecture

The current add-on is concentrated in:

```text
addon/metahuman_blender_pipeline/__init__.py
```

That file owns registration, UI panels, import flow, material handling, control-rig generation, body-proportion shape generation, LOD display controls, baking workflows, torso guide handles, and status reporting.

The concentration is acceptable for the current release, but future work should split stable subsystems into modules:

- `import_pipeline.py`
- `materials.py`
- `control_rig.py`
- `proportion_shapes.py`
- `lod_display.py`
- `torso_guides.py`
- `validation.py`

Do not split during a release package unless behavior is covered by the background analyze scripts.

## Asset Policy

The repository is source-only. Public git should not contain MetaHuman DCC exports, FBX files, DNA files, texture maps, generated `.blend` files, or pycache.

Local-only development samples live outside this repository in:

```text
../BlendFiles/MetaForge/
```

The ignored local development asset folder is:

```text
addon/metahuman_blender_pipeline/bundled_metahuman/
```

## Validation Scripts

The `tools/analyze/` scripts are the current regression harness. They are designed to run in Blender background mode and write JSON metrics under `test_results/`.

Important scripts:

- `analyze_builtin_import.py`
- `analyze_torso_guide_handles.py`
- `analyze_language_builtin_torso_guides.py`
- `analyze_control_mirror_state_only.py`
- `analyze_advanced_bake_copy.py`
- `analyze_static_bake_copy.py`
- `analyze_reset_group_defaults.py`
- `analyze_param_action_guidance.py`

Use these scripts before large UI or shape-generation changes. Avoid visual QA unless specifically requested.

## Known Sensitive Areas

- FBX empty removal must preserve child `matrix_world`, or body scale can jump from roughly `1.44m` to `144m`.
- `normalize_metahuman_unit_scale()` should report abnormal scale; it should not compensate by scaling the root armature.
- Low LOD hiding should use recoverable Outliner visibility, not hard viewport/render disables.
- The one-click path should not build body-proportion shapes by default, because the generation step can be slow and should remain explicit.
- Body-shape parameters with generation-time semantics must be applied/rebuilt before their values affect baked shape keys.

## Release Checklist

- `bl_info["version"]` matches `RELEASE_NOTES.md`.
- `README.md`, `index.html`, and `MANIFEST.md` agree on the public asset boundary.
- `addon/metahuman_blender_pipeline/bundled_metahuman/` is not staged.
- No `.blend`, `.blend1`, `.blend2`, pycache, or generated zips are staged.
- `python -m compileall -q addon tools` passes.
- `powershell -ExecutionPolicy Bypass -File .\scripts\package_release.ps1 -Version 0.1.40` creates a zip with `metahuman_blender_pipeline/` at the root.
