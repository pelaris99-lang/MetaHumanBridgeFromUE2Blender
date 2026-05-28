# Next Goals

## Stabilize Clothing QA On Real Scenes

Acceptance criteria:

- Re-run `Bind Selected Clothes to Body` on real clothing assets after applying the character rest pose.
- Confirm the clothing object has direct bone vertex groups, one `MH_Cloth_Armature`, and no live Data Transfer mapping.
- Use `Paint Cloth Weights from ControlRig` to manually clean sleeve, shoulder, vest, belt, and holster weights.

## Keep The Public Package Lean

Acceptance criteria:

- Keep source, docs, scripts, and small JSON validation outputs in git.
- Keep GraceSwat scenes, screenshots, DCC exports, textures, and generated release zips outside git.
- Regenerate the install zip from `scripts/package_release.ps1` instead of committing binary packages.

## Reduce Add-On Monolith Risk

Acceptance criteria:

- Split the large `addon/metahuman_blender_pipeline/__init__.py` only after the current clothing/rest-pose workflow has had real-scene testing.
- Preserve the current UI labels and operator IDs during any refactor.
- Keep smoke tests covering rest pose, clothing binding, and Weight Paint entry.
