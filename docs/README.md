# MetaForge 交接包

这个文件夹是给下一个 Codex 窗口接手用的。建议新窗口先读取：

`C:\Users\Siyuan Ouyang\OneDrive\Art\3D\CodexWorkSpace\handoff_metahuman_pipeline_20260525\docs\HANDOFF.md`

插件显示名已改为 `MetaForge`，源码模块名仍是 `metahuman_blender_pipeline`。当前插件约为 `0.1.25`，源码快照在：

`C:\Users\Siyuan Ouyang\OneDrive\Art\3D\CodexWorkSpace\handoff_metahuman_pipeline_20260525\artifacts\metahuman_blender_pipeline_snapshot\__init__.py`

下一窗口不要从旧问题重来。当前重点是等用户基于 `0.1.25` 的实际测试反馈，再围绕这些位置微调：

1. ControlRig 三档粗细与隐藏/半透明/显示。
2. LOD 隐藏/半透明/显示。
3. ControlRig 体型外观同步。
4. 体型参数分组、命名、hint 和形变语义。

注意：用户要求不要主动目视检查，让他自己看。继续跑 Blender 保存类脚本前先检查 C 盘空间。
