# MetaForge Bundle Manifest

Created from workspace state after `0.1.50`.

This manifest describes the source bundle that is safe to publish. Large local
sample `.blend` files, MetaHuman exports, GraceSwat project assets, screenshots,
and generated release zips are kept outside git; see `docs/PUBLIC_RELEASE.md`.

## Core Hashes

```text
CD6DFAE1D9D6255705E0BC9594C4D708A58011475BD991950B5C0B0C583439F3  addon/metahuman_blender_pipeline/__init__.py
3A4578D4D89976B9572A25F9038BFAF6DB680712EBEED57BFBAE18D9738369A3  README.md
2DF0C05BFA9A5CF68BDB35F642F5B9AE8622BC6255D4DAAB5B555DE7332D49C4  RELEASE_NOTES.md
1A23BD88CF574000FD5758F056CF570520CD6302697BA726DD6B697D9C2AAC51  docs/CLOTHING_WORKFLOW.md
FCAB8C73A0EE9D56136DE677B62820B8AB753C255573DFD583C01372DFB79AD8  docs/TEST_INDEX.md
C56DA56B75AEE6AA902D769F9716398E47458C1FD829CD0920331937DC78792C  tools/analyze/analyze_cloth_bind_smoke.py
BDA03F6E8AE32F29C93A1F8472ADD66CD3096283D9B54DB3E87D57F53AA95847  tools/analyze/analyze_pose_as_rest_smoke.py
480CF025BBBE3902EE1707823677C06A129B193930E0CAC0A87AE2DBFE02B8C6  tools/analyze/analyze_weight_paint_from_control_smoke.py
```

## Verified In This Bundle

- `tools/analyze/analyze_pose_as_rest_smoke.py`
- `tools/analyze/analyze_cloth_bind_smoke.py`
- `tools/analyze/analyze_weight_paint_from_control_smoke.py`

These were run with Blender 5.1.1 using `--background --factory-startup` and
wrote passing JSON outputs to `test_results/`.
