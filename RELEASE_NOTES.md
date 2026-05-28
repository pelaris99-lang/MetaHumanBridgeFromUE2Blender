# Release Notes

## v0.1.50

Clothing and repair-focused developer release for the `metahuman_blender_pipeline` Blender add-on.

### Added

- `Repair MetaHuman Texture Index` relinks material texture nodes and image datablocks after a moved DCC export or missing local paths.
- `Apply Current Pose as Rest` bakes the current ControlRig-driven deform rig pose into the rest pose and writes the visible mesh state back into mesh data so edit mode sees the permanent pose.
- `Bind Selected Clothes to Body` now writes body bone weights directly into selected clothing/equipment vertex groups. It does not leave a live Data Transfer mapping behind.
- `Paint Cloth Weights from ControlRig` lets the user select a clothing mesh plus a ControlRig handle, then enters Weight Paint with the corresponding bone vertex group active.

### Changed

- Clothing binding now samples the current visible body with a four-nearest-vertex blend and adds only the final Armature modifier to the clothing object.
- Legacy clothing objects with leftover `MH_Cloth_Weight_Projection` Data Transfer modifiers are cleaned up when rebinding or entering the weight-paint helper.
- The clothing and rest-pose flows have dedicated background smoke tests in `tools/analyze/`.

### Validated

- `analyze_pose_as_rest_smoke.py`
- `analyze_cloth_bind_smoke.py`
- `analyze_weight_paint_from_control_smoke.py`

### Package

Generate the install package with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package_release.ps1 -Version 0.1.50
```

## v0.1.40

Initial public developer release for the `metahuman_blender_pipeline` Blender add-on.

### Included

- MetaHuman DCC import flow.
- Material connection helpers for nearby DCC texture maps.
- Scale-stable imported empty cleanup.
- Blender-side control-rig handle generation and display controls.
- LOD0-first visibility with recoverable lower LODs.
- Body-proportion controls with explicit rebuild behavior.
- Torso guide handles, mirroring helpers, static mesh copy, and advanced rig copy paths.
- Background analysis scripts and small validation result JSON files.

### Public Asset Boundary

This release does not include MetaHuman sample exports, DNA files, FBX files, texture maps, or `.blend` scenes in git. Use your own DCC export path in Blender, or keep local test assets outside the repository under `../BlendFiles/MetaForge/`.

### Known Limits

- The main add-on implementation is still concentrated in one large `__init__.py` file.
- Visual QA is intentionally not part of this release pass.
- Body-shape generation is explicit and can be slow on dense meshes.
- Built-in sample export support is a local-development convenience and is ignored by git.

### Package

Generate the install package with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package_release.ps1 -Version 0.1.40
```
