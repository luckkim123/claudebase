# claudebase installer (Windows / PowerShell 7+)
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
$RepoDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ClaudeHome = Join-Path $env:USERPROFILE ".claude"

function Log([string]$msg)   { Write-Host "[install] $msg" }

# Runtime dependency check — warn-only so install.ps1 remains idempotent.
# `jq` is required by the statusLine command in claude/settings.json; without
# it the status line silently renders as literal template text (e.g. "ctx:%").
function Check-RuntimeDeps {
    if (-not (Get-Command jq -ErrorAction SilentlyContinue)) {
        Write-Host '[install] WARNING: "jq" not found — statusLine will degrade silently'
        Write-Host '[install]   install: winget install jqlang.jq  (or: scoop install jq)'
    }

    # gemini CLI — required by the gen-image skill (Google nano banana image
    # generation). Without it /gen-image falls back to direct REST API calls
    # which work but bypass the MCP tool path documented in the skill.
    if (-not (Get-Command gemini -ErrorAction SilentlyContinue)) {
        Write-Host '[install] WARNING: "gemini" CLI not found — gen-image skill needs it'
        Write-Host '[install]   install: npm install -g @google/gemini-cli'
    } else {
        # gemini present — also verify the nano banana extension is installed.
        # The extension exposes the mcp_nanobanana_generate_image tool the
        # gen-image skill expects. Without it the skill silently degrades to
        # text-only Gemini responses.
        $nanoExt = Join-Path $env:USERPROFILE ".gemini/extensions/nanobanana"
        if (-not (Test-Path -LiteralPath $nanoExt)) {
            Write-Host '[install] WARNING: nano banana extension missing — gen-image MCP path disabled'
            Write-Host '[install]   install: gemini extensions install https://github.com/gemini-cli-extensions/nanobanana'
        }
    }
}
Check-RuntimeDeps

# Opt-in convenience-tool install (INSTALL_TOOLS=1) — mirror of deps.sh's
# ensure_convenience_tools. DIVERGENCE (intentional): on Unix this installs
# tmux + a clipboard helper so tmux.conf's mouse-copy works. Neither applies on
# Windows — there is no native tmux, and clipboard access is already built in
# (PowerShell Set-Clipboard / clip.exe / Get-Clipboard), which shell/tmux.conf's
# $COPY_CMD never runs here anyway (.tmux.conf is a Unix artifact). So this is a
# documented no-op kept for parity; if a Windows tmux convenience tool is ever
# wanted, add it here.
function Ensure-ConvenienceTools {
    if ($env:INSTALL_TOOLS -ne '1') { return }
    Debug "convenience tools: no Windows-native tmux/clipboard install needed (skip)"
}

function Debug([string]$msg) { if ($Verbose) { Write-Host "[debug]   $msg" } }
function Run([scriptblock]$block) {
    if ($DryRun) { Write-Host "[dry-run] $($block.ToString().Trim())" }
    else { & $block }
}
# Called after Debug is defined (it relies on it).
Ensure-ConvenienceTools

# Opt-in: launch the `claude` CLI with the fullscreen renderer — mirror of
# install.sh's maybe_enable_claude_mouse. DIVERGENCE (intentional, documented):
# the Unix path is a `claude()` shell function sourced from ~/.zshrc|~/.bashrc,
# and the reason it exists there is to keep the pref out of the claudebase-
# symlinked ~/.claude/settings.json — a Unix-symlink concern. The env var itself
# (CLAUDE_CODE_NO_FLICKER) is cross-platform, but this path is unverified on
# native Windows Terminal, where upstream also warns about stale-cell artifacts
# (CLAUDE_CODE_ALT_SCREEN_FULL_REPAINT). So this is a documented no-op kept for
# parity; if a Windows user needs it, add a $PROFILE
# `function claude { $env:CLAUDE_CODE_NO_FLICKER=1; & claude.exe @args }`.
function Enable-ClaudeMouse {
    if ($env:INSTALL_CLAUDE_MOUSE -ne '1') { return }
    Debug "claude-mouse: Unix shell-rc wrapper only; no Windows equivalent shipped (skip)"
}
Enable-ClaudeMouse

function Already-Linked([string]$target, [string]$src) {
    if (-not (Test-Path -LiteralPath $target)) { return $false }
    $item = Get-Item -LiteralPath $target -Force
    if (-not $item.LinkType) { return $false }
    return ($item.Target -eq $src) -or ($item.Target -contains $src)
}

function Remove-IfExists([string]$target) {
    # Clear a path so a fresh symlink (or rendered file) can replace it.
    # No backup is made — recovery is via git history. See repo CLAUDE.md
    # ("Idempotency is non-negotiable" / "Don'ts: backups in install").
    if (Test-Path -LiteralPath $target) {
        Run { Remove-Item -LiteralPath $target -Recurse -Force }
    }
}

function Link-OrCopy([string]$src, [string]$dest) {
    if (-not (Test-Path -LiteralPath $src)) { Log "skip (missing source): $src"; return }
    if (-not $Copy -and (Already-Linked $dest $src)) {
        Debug "already linked: $dest -> $src (skip)"
        return
    }
    Remove-IfExists $dest
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
Link-OrCopy "$RepoDir/config/settings.json" "$ClaudeHome/settings.json"

# 2b. user-level CLAUDE.md — universal behavioral rules applied across all projects
Link-OrCopy "$RepoDir/config/CLAUDE.md" "$ClaudeHome/CLAUDE.md"

# 3. mcp.json — render template (substitute ${VAR} from secrets.env if present, else copy as-is).
#    Idempotent: skip rewrite when rendered content matches the existing file.
$SecretsFile = "$RepoDir/secrets/secrets.env"
$Template = "$RepoDir/config/mcp.template.json"
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
            Remove-IfExists "$ClaudeHome/mcp.json"
            Set-Content -Path "$ClaudeHome/mcp.json" -Value $content -NoNewline
            Log "rendered: $ClaudeHome/mcp.json"
        }
    }
}

# 4. user-scope skills — symlink each subdirectory individually so we don't
#    clobber any other skills the user has under ~/.claude/skills/.
$SkillsRoot = "$RepoDir/runtime/skills"
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

    # OMC shell CLI (oh-my-claude-sisyphus) — required for `omc team` / tmux pane workers.
    # Plugin alone only provides slash commands; the shell `omc` binary is a separate npm package.
    if (-not (Get-Command omc -ErrorAction SilentlyContinue)) {
        if (Get-Command npm -ErrorAction SilentlyContinue) {
            Log "installing omc shell CLI: npm i -g oh-my-claude-sisyphus@latest"
            Run { npm i -g oh-my-claude-sisyphus@latest 2>$null | Out-Null }
            if (-not (Get-Command omc -ErrorAction SilentlyContinue)) {
                Log "  WARNING: failed to install oh-my-claude-sisyphus; run manually"
            }
        } else {
            Log "  WARNING: npm not found; skipping omc shell CLI install"
        }
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
    $drift = git -C $RepoDir status --porcelain config/settings.json 2>$null
    if ($drift) {
        Log "drift: config/settings.json modified by Claude CLI - review with: git -C $RepoDir diff config/settings.json"
    }
}

Log "done."
