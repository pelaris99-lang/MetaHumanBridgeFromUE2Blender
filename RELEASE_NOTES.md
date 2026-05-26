# Release Notes

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
