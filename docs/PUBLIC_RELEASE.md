# Public Release Boundary

MetaForge is being published as source code, documentation, validation scripts, and release packaging.

The public repository intentionally excludes local MetaHuman sample exports and `.blend` scenes.

## Excluded From Git

- `addon/metahuman_blender_pipeline/bundled_metahuman/`
- `examples/*.blend`
- `*.blend1`, `*.blend2`
- `__pycache__/` and `*.pyc`
- generated release zips

## Why

MetaHuman DCC exports, textures, DNA files, FBX files, and local Blender scenes can be large and may carry external licensing or project-specific ownership constraints. The add-on should work against a user's own MetaHuman export path instead of relying on a checked-in sample character.

## Local Development Assets

This workspace keeps the clean validation sample outside the repository:

```text
../BlendFiles/MetaForge/metahuman_pipeline_example_clean.blend
```

If you need the bundled-development path locally, place your own DCC export under:

```text
addon/metahuman_blender_pipeline/bundled_metahuman/OutPut/
```

That folder is ignored by git.
