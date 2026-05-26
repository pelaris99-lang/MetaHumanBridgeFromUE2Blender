# MetaForge

MetaForge is a Blender add-on for bringing Unreal/MetaHuman DCC exports into Blender with usable materials, LOD visibility controls, larger control-rig handles, body-proportion tools, and validation scripts.

The GitHub repository is `MetaHumanBridgeFromUE2Blender`; the add-on package is `metahuman_blender_pipeline`.

## Current Release

Version: `0.1.40`

This release is a local-stable developer build extracted from the CodexWorkSpace safe zone. It focuses on preserving correct MetaHuman scale, importing DCC assets, building a Blender-side control rig, and exposing body-shape controls without forcing slow generation into the default one-click path.

## What It Does

- Imports MetaHuman body/face FBX assets from a DCC export.
- Connects material slots to nearby MetaHuman texture maps where available.
- Keeps body scale stable by preserving child world matrices before imported FBX empties are removed.
- Builds larger selectable Blender control-rig handle meshes.
- Supports LOD0-first visibility while leaving lower LODs recoverable through the Outliner eye.
- Provides body-proportion controls, torso guide handles, mirroring, static mesh copy, and advanced rig copy workflows.
- Ships background analysis scripts for repeatable validation.

## Install

Package a clean add-on zip:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package_release.ps1 -Version 0.1.40
```

Install the generated zip from `dist/` in Blender:

```text
Edit > Preferences > Add-ons > Install
```

Enable `MetaForge`, then open:

```text
3D View > Sidebar > MetaForge
```

## Asset Setup

Public git does not include MetaHuman sample exports or `.blend` scenes.

Set `DCCExport Folder` in the add-on UI to your own MetaHuman DCC export. Local development samples, when present, live outside the repository:

```text
../BlendFiles/MetaForge/metahuman_pipeline_example_clean.blend
```

Read `docs/PUBLIC_RELEASE.md` before adding any sample assets.

## Repository Map

| Path | Purpose |
| --- | --- |
| `addon/metahuman_blender_pipeline/` | Blender add-on source. |
| `tools/analyze/` | Background validation scripts. |
| `docs/` | Handoff notes, technical notes, test index, public release boundary, and engineering docs. |
| `test_results/` | Small JSON validation outputs from the safe-zone bundle. |
| `scripts/` | Release packaging helpers. |

## Validation

Run syntax checks before packaging:

```powershell
python -m compileall -q addon tools
```

When Blender and a local sample file are available:

```powershell
& "C:\SiyuanApps\Art\blender.exe" --background "..\BlendFiles\MetaForge\metahuman_pipeline_example_clean.blend" --python ".\tools\analyze\analyze_torso_guide_handles.py"
& "C:\SiyuanApps\Art\blender.exe" --background "..\BlendFiles\MetaForge\metahuman_pipeline_example_clean.blend" --python ".\tools\analyze\analyze_language_builtin_torso_guides.py"
```

## License

No open-source license has been declared yet. Do not assume reuse rights until a license file is added. MetaHuman, Unreal Engine, and related asset names belong to their respective owners.
