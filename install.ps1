# claude-settings installer (Windows / PowerShell 7+)
# Usage: pwsh ./install.ps1 [-Copy] [-DryRun] [-Verbose]
#   -Copy     Force copy mode (default tries symlink, falls back to copy)
#   -DryRun   Show actions without executing
#   -Verbose  Print extra detail (idempotent skips, resolved secrets count)
#
# Note: Symbolic links on Windows require either admin privileges or
#       Developer Mode enabled (Settings > Privacy > For developers).

param(
    [switch]$Copy,
    [switch]$DryRun,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$RepoDir = $PSScriptRoot
$ClaudeHome = Join-Path $env:USERPROFILE ".claude"
$BackupDir = Join-Path $ClaudeHome (".backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))

function Log([string]$msg)   { Write-Host "[install] $msg" }

# Runtime dependency check — warn-only so install.ps1 remains idempotent.
# `jq` is required by the statusLine command in claude/settings.json; without
# it the status line silently renders as literal template text (e.g. "ctx:%").
function Check-RuntimeDeps {
    if (Get-Command jq -ErrorAction SilentlyContinue) { return }
    Write-Host '[install] WARNING: "jq" not found — statusLine will degrade silently'
    Write-Host '[install]   install: winget install jqlang.jq  (or: scoop install jq)'
}
Check-RuntimeDeps

function Debug([string]$msg) { if ($Verbose) { Write-Host "[debug]   $msg" } }
function Run([scriptblock]$block) {
    if ($DryRun) { Write-Host "[dry-run] $($block.ToString().Trim())" }
    else { & $block }
}

function Already-Linked([string]$target, [string]$src) {
    if (-not (Test-Path -LiteralPath $target)) { return $false }
    $item = Get-Item -LiteralPath $target -Force
    if (-not $item.LinkType) { return $false }
    return ($item.Target -eq $src) -or ($item.Target -contains $src)
}

function Backup-IfNeeded([string]$target) {
    if (-not (Test-Path -LiteralPath $target)) { return }
    $item = Get-Item -LiteralPath $target -Force
    if ($item.LinkType) {
        Run { Remove-Item -LiteralPath $target -Force }
        return
    }
    Run { New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null }
    Run { Move-Item -LiteralPath $target -Destination "$BackupDir/" -Force }
    Log "backed up: $target -> $BackupDir/"
}

function Link-OrCopy([string]$src, [string]$dest) {
    if (-not (Test-Path -LiteralPath $src)) { Log "skip (missing source): $src"; return }
    if (-not $Copy -and (Already-Linked $dest $src)) {
        Debug "already linked: $dest -> $src (skip)"
        return
    }
    Backup-IfNeeded $dest
    $useCopy = $Copy
    if (-not $useCopy) {
        try {
            Run { New-Item -ItemType SymbolicLink -Path $dest -Target $src -Force | Out-Null }
            Log "linked:  $dest -> $src"
            return
        } catch {
            Log "symlink failed (need admin or Developer Mode), falling back to copy"
            $useCopy = $true
        }
    }
    if ($useCopy) {
        Run { Copy-Item -LiteralPath $src -Destination $dest -Recurse -Force }
        Log "copied:  $dest"
    }
}

# 1. ensure ~/.claude
if (-not (Test-Path $ClaudeHome)) { Run { New-Item -ItemType Directory -Path $ClaudeHome -Force | Out-Null } }

# 2. settings.json
Link-OrCopy "$RepoDir/claude/settings.json" "$ClaudeHome/settings.json"

# 2b. user-level CLAUDE.md — universal behavioral rules applied across all projects
Link-OrCopy "$RepoDir/claude/CLAUDE.md" "$ClaudeHome/CLAUDE.md"

# 3. mcp.json — render template (substitute ${VAR} from secrets.env if present, else copy as-is).
#    Idempotent: skip backup + rewrite when rendered content matches the existing file.
$SecretsFile = "$RepoDir/secrets/secrets.env"
$Template = "$RepoDir/claude/mcp.template.json"
if (Test-Path $Template) {
    if ($DryRun) {
        Log "would render: $ClaudeHome/mcp.json"
    } else {
        $env_table = @{}
        if (Test-Path $SecretsFile) {
            Get-Content $SecretsFile | ForEach-Object {
                if ($_ -match '^\s*([^#=\s][^=]*)=(.*)$') {
                    $env_table[$matches[1].Trim()] = $matches[2].Trim()
                }
            }
        }
        $content = Get-Content $Template -Raw
        $resolved = 0
        $content = [regex]::Replace($content, '\$\{(\w+)\}', {
            param($m)
            if ($env_table.ContainsKey($m.Groups[1].Value)) {
                $script:resolved++
                $env_table[$m.Groups[1].Value]
            } else { $m.Value }
        })
        Debug "resolved $resolved `${VAR} placeholder(s) from secrets.env"
        if ($content -match '\$\{') {
            Log "WARNING: unresolved `${...} placeholders remain — check secrets/secrets.env"
        }
        $existing = if (Test-Path -LiteralPath "$ClaudeHome/mcp.json") { Get-Content -LiteralPath "$ClaudeHome/mcp.json" -Raw } else { $null }
        if ($null -ne $existing -and $existing -eq $content) {
            Debug "mcp.json unchanged (skip)"
        } else {
            Backup-IfNeeded "$ClaudeHome/mcp.json"
            Set-Content -Path "$ClaudeHome/mcp.json" -Value $content -NoNewline
            Log "rendered: $ClaudeHome/mcp.json"
        }
    }
}

# 4. user-scope skills — symlink each subdirectory individually so we don't
#    clobber any other skills the user has under ~/.claude/skills/.
$SkillsRoot = "$RepoDir/skills"
if (Test-Path -LiteralPath $SkillsRoot) {
    $SkillsDest = Join-Path $ClaudeHome "skills"
    if (-not (Test-Path -LiteralPath $SkillsDest)) {
        Run { New-Item -ItemType Directory -Path $SkillsDest -Force | Out-Null }
    }
    Get-ChildItem -LiteralPath $SkillsRoot -Directory | ForEach-Object {
        Link-OrCopy $_.FullName (Join-Path $SkillsDest $_.Name)
    }
}

# 5. platform-specific (Windows extras, if any)
$PlatformInstaller = "$RepoDir/platform/windows/install.ps1"
if (Test-Path $PlatformInstaller) {
    Log "running platform installer: windows"
    Run { & $PlatformInstaller }
}

# 5b. plugin marketplaces — mirror of install.sh's sync_plugins marketplace-add
#     block. install.ps1 does NOT yet implement the full plugin-sync flow
#     (parity gap vs install.sh — tracked separately); these adds are a no-op
#     until a Windows machine actually exercises `claude plugin install`, but
#     keeping them aligned avoids drift later.
$Enabled = @()
try {
    $Enabled = (Get-Content "$ClaudeHome/settings.json" -Raw | ConvertFrom-Json).enabledPlugins.PSObject.Properties | Where-Object { $_.Value -eq $true } | ForEach-Object { $_.Name }
} catch {}

# Marketplace-exists check (mirror of install.sh helper). `claude plugin
# marketplace list` prints entries as `  ❯ <name>` — extract just the names
# and exact-match. The previous per-marketplace -match patterns matched
# arbitrary substrings, causing axlabs to re-add on every run.
function Marketplace-Exists([string]$name) {
    $list = claude plugin marketplace list 2>$null
    if (-not $list) { return $false }
    $names = $list | Select-String -Pattern '❯\s+(\S+)' | ForEach-Object { $_.Matches[0].Groups[1].Value }
    return $names -contains $name
}

if ($Enabled -match '@axlabs') {
    if (-not (Marketplace-Exists 'axlabs')) {
        Log "adding marketplace: seulee26/mckinsey-pptx (axlabs)"
        Run { claude plugin marketplace add seulee26/mckinsey-pptx 2>$null | Out-Null }
    }
}

if ($Enabled -match '@omc') {
    if (-not (Marketplace-Exists 'omc')) {
        Log "adding marketplace: Yeachan-Heo/oh-my-claudecode (omc)"
        Run { claude plugin marketplace add Yeachan-Heo/oh-my-claudecode 2>$null | Out-Null }
    }
}

# 6. local-overrides hint
$LocalFile = Join-Path $ClaudeHome "settings.local.json"
if (-not (Test-Path -LiteralPath $LocalFile)) {
    Log "hint: no $LocalFile - see templates/settings.local.example.json for per-machine plugin overrides"
}

# 7. oh-my-claudecode HUD setup hint (mirror of install.sh step 8)
if ($Enabled -match 'oh-my-claudecode@omc') {
    if (-not (Test-Path -LiteralPath "$ClaudeHome/hud/omc-hud.mjs")) {
        Log "next: open Claude Code and run '/oh-my-claudecode:omc-setup' to finish HUD install"
    }
}

# 8. settings.json drift check (mirror of install.sh step 9) — warn-only.
#    Claude Code CLI writes straight back into the symlinked repo file when
#    it auto-formats or persists new settings.
if (Get-Command git -ErrorAction SilentlyContinue) {
    $drift = git -C $RepoDir status --porcelain claude/settings.json 2>$null
    if ($drift) {
        Log "drift: claude/settings.json modified by Claude CLI - review with: git -C $RepoDir diff claude/settings.json"
    }
}

Log "done. backup dir created only if a non-symlink file was overwritten."
