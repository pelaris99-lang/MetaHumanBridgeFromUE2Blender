# MetaForge Bundle Manifest

Created from workspace state after `0.1.40`.

This manifest describes the source bundle that is safe to publish. Large local
sample `.blend` files and MetaHuman exports are kept outside git; see
`docs/PUBLIC_RELEASE.md`.

## Core Hashes

```text
BA906CECF2C6D04F191791C3B5EF6E189341C64F4367B189ECDAA23C3AE20BCE  addon/metahuman_blender_pipeline/__init__.py
C501977F5517B7349A751B88476EA2F5C3396D8DB99D021BF3CE730E1AF7132B  ../BlendFiles/MetaForge/metahuman_pipeline_example_clean.blend (local only)
0201C949B95D68079B68D1D587E1779879166CDD65946D51E835236112318103  docs/HANDOFF.md
6D003C42795FAF6927907DFB177B6C263470117C645981DDE103D32BFAB01F34  docs/TEST_INDEX.md
```

## Verified In This Bundle

- `tools/analyze/analyze_torso_guide_handles.py`
- `tools/analyze/analyze_language_builtin_torso_guides.py`

Both were run against the local workspace sample in
`../BlendFiles/MetaForge/metahuman_pipeline_example_clean.blend` and wrote
passing results to `test_results/`.
