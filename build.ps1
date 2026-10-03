# Build this content pack's zip with forward-slash entries AND an explicit directory
# entry for every ancestor path. Java's ZipFileSystem.isDirectory() returns false
# without them, so Hytale's I18nModule.loadMessagesFromPack would skip the
# Server/Languages tree (and any .lang the pack ships). Never use Compress-Archive: it
# writes backslash separators that Hytale silently drops on Windows.
#
# Cross-platform: runs on Windows PowerShell 5.1 and on pwsh (macOS/Linux).
#
#   .\build.ps1                  # build, then install if a Mods folder is known
#   .\build.ps1 -Install:$false  # build only, no copy
#   .\build.ps1 -ModsDir <path>  # build + install into an explicit folder
#
# The install target resolves from -ModsDir, then $env:HYTALE_MODS_DIR. If neither is
# set the copy is skipped (the build still succeeds) with a hint to set the env var.
param(
    [bool]$Install = $true,
    [string]$ModsDir = $env:HYTALE_MODS_DIR
)
$ErrorActionPreference = 'Stop'

# --- PER-PACK ---
$PackName          = 'HallowsEvePack'       # zip base name; the manifest Version is appended
$ExtraExcludeNames = @('.gitattributes') # extra top-level file names to leave out of the zip
$ExtraExcludeDirs  = @('tools') # extra top-level dir names (at the pack root) to skip
# ----------------

$pack = $PSScriptRoot
# The pack version comes from manifest.json so the zip name always carries it
# (single source of truth — bump the manifest, not this script).
$version = (Get-Content (Join-Path $pack 'manifest.json') -Raw | ConvertFrom-Json).Version
if (-not $version) { throw 'manifest.json is missing a Version field' }
$ZipName = "$PackName-$version.zip"
$zipPath = Join-Path $pack $ZipName
$excludeNames = @('README.md', 'CURSEFORGE.md', 'CLAUDE.md', 'LICENSE', '.gitignore', 'build.ps1', 'icon-400.png') + $ExtraExcludeNames
$excludeDirs  = @('.git', '.github', 'patch-notes') + $ExtraExcludeDirs

# Remove any prior zip for this pack (old non-versioned name or older versions).
Get-ChildItem -Path $pack -Filter "$PackName*.zip" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
try { Add-Type -AssemblyName 'System.IO.Compression.FileSystem' -ErrorAction Stop } catch { }
$zip = [System.IO.Compression.ZipFile]::Open($zipPath, 'Create')
try {
    $files = Get-ChildItem -Path $pack -Recurse -File -Force | Where-Object {
        $rel = $_.FullName.Substring($pack.Length + 1).Replace('\', '/')
        $top = ($rel -split '/')[0]
        ($_.Name -notin $excludeNames) -and ($_.Extension -ne '.zip') -and ($top -notin $excludeDirs)
    }
    # Emit a directory entry for every ancestor path (once) before writing each file,
    # so the zip reports real directories to Java's ZipFileSystem.
    $createdDirs = @{}
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($pack.Length + 1).Replace('\', '/')
        $parts = $rel -split '/'
        for ($i = 1; $i -lt $parts.Length; $i++) {
            $dir = ($parts[0..($i - 1)] -join '/') + '/'
            if (-not $createdDirs.ContainsKey($dir)) {
                $zip.CreateEntry($dir, [System.IO.Compression.CompressionLevel]::NoCompression).Open().Close()
                $createdDirs[$dir] = $true
            }
        }
        $entry = $zip.CreateEntry($rel, [System.IO.Compression.CompressionLevel]::Optimal)
        $stream = $entry.Open()
        $bytes = [System.IO.File]::ReadAllBytes($f.FullName)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Close()
    }
    Write-Host "Built $zipPath ($($files.Count) files, $($createdDirs.Count) dir entries)"
} finally {
    $zip.Dispose()
}

if ($Install) {
    if (-not $ModsDir) {
        Write-Host "No Mods folder set - pass -ModsDir <path> or set `$env:HYTALE_MODS_DIR to auto-install. Built zip only."
    } elseif (-not (Test-Path $ModsDir)) {
        Write-Warning "Mods folder '$ModsDir' not found. Built zip only."
    } else {
        # Remove older zips for this pack so only the current version loads.
        Get-ChildItem -Path $ModsDir -Filter "$PackName*.zip" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
        $dest = Join-Path $ModsDir $ZipName
        Copy-Item $zipPath $dest -Force
        Write-Host "Installed to $dest"
    }
}
