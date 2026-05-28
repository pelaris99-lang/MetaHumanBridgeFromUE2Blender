# Clothing Workflow

This workflow is for bringing clothing or equipment meshes onto the MetaHuman body rig, then manually cleaning up deformation weights in Blender.

## Recommended Order

1. Use `Apply Current Pose as Rest` if the character has already been permanently reposed.
2. Select the clothing or equipment mesh objects.
3. Click `Bind Selected Clothes to Body`.
4. Select one clothing mesh and one ControlRig handle.
5. Click `Paint Cloth Weights from ControlRig`.
6. Brush the active vertex group in Weight Paint.

## What Binding Does

`Bind Selected Clothes to Body` writes real vertex group weights onto each selected clothing mesh.

It does not keep a live Data Transfer dependency. The final clothing object should have:

- MetaHuman bone-named vertex groups copied from the body by direct sampling.
- One `MH_Cloth_Armature` modifier targeting the body deform rig.
- No `MH_Cloth_Weight_Projection` Data Transfer modifier.
- No stale armature parent left over from older binding attempts.

The direct transfer samples the current visible body position and blends the four nearest body vertices for each clothing vertex. This gives a useful first pass that can be corrected with normal Blender Weight Paint.

## What Weight Paint From ControlRig Does

`Paint Cloth Weights from ControlRig` treats the selected ControlRig handle as a bone picker:

- The selected clothing mesh becomes the active object.
- Blender enters Weight Paint mode.
- The vertex group matching the selected ControlRig handle's target bone becomes active.
- Legacy Data Transfer modifiers are applied or removed before painting when found.

This means the user can click a visible control handle instead of hunting through a long MetaHuman bone list.

## Troubleshooting

If the active group is black:

- Confirm the selected ControlRig handle corresponds to the body region you intend to paint.
- Re-run `Bind Selected Clothes to Body` on the clothing mesh to rewrite direct weights.
- Check that the clothing object has `MH_Cloth_Armature` and no live Data Transfer modifier.
- Use Blender's Weight Paint brush to add weight manually where the automatic body sampling is too sparse.

## Validation

The current regression coverage is:

- `tools/analyze/analyze_cloth_bind_smoke.py`
- `tools/analyze/analyze_weight_paint_from_control_smoke.py`

The expected result is direct nonzero clothing weights, no live Data Transfer modifier, and a usable Weight Paint mode entry from a selected ControlRig handle.
