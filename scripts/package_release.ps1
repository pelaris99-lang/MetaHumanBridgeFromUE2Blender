param(
  [string]$Version = "0.1.40"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
$Addon = Join-Path $Root "addon\metahuman_blender_pipeline"
$Dist = Join-Path $Root "dist"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$StageRoot = Join-Path $Dist "stage_$Stamp"
$StageAddon = Join-Path $StageRoot "metahuman_blender_pipeline"
$ZipPath = Join-Path $Dist "metaforge_${Version}_$Stamp.zip"

New-Item -ItemType Directory -Path $StageAddon -Force | Out-Null

Get-ChildItem -LiteralPath $Addon -Recurse -File |
  Where-Object {
    $_.FullName -notmatch "\\__pycache__\\" -and
    $_.FullName -notmatch "\\bundled_metahuman\\" -and
    $_.Extension -ne ".pyc" -and
    $_.Extension -notin @(".blend", ".blend1", ".blend2")
  } |
  ForEach-Object {
    $relative = $_.FullName.Substring($Addon.Length).TrimStart("\")
    $target = Join-Path $StageAddon $relative
    $targetDir = Split-Path -Parent $target
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $target -Force
  }

Compress-Archive -LiteralPath $StageAddon -DestinationPath $ZipPath -Force
$ResolvedDist = (Resolve-Path $Dist).Path
$ResolvedStage = (Resolve-Path $StageRoot).Path
if ($ResolvedStage.StartsWith($ResolvedDist)) {
  Remove-Item -LiteralPath $ResolvedStage -Recurse -Force
}
Write-Output $ZipPath
