# platform/windows/install.ps1 — Windows system package auto-install via winget.
# Invoked by ../../install.ps1 after dotfile sync. Idempotent: skips packages
# already present. Non-fatal: any failure does not stop the parent installer.

$ErrorActionPreference = "Continue"

# winget package IDs
# GitHub.cli (gh): the household's sole GitHub interface (clone/push/auth) —
# claudebase relies on it instead of any github plugin (see config/settings.json).
$RequiredWinget = @(
    @{ Id = "sunbk201.Pretendard"; Name = "Pretendard font" }
    @{ Id = "GitHub.cli"; Name = "GitHub CLI (gh)" }
)
# pip packages (import_name -> package_name)
$RequiredPip = @(
    @{ Import = "pptx"; Package = "python-pptx" }
)

function Has-Winget {
    return [bool](Get-Command winget -ErrorAction SilentlyContinue)
}

function Is-WingetInstalled([string]$id) {
    if (-not (Has-Winget)) { return $false }
    $output = winget list --id $id --exact 2>$null | Out-String
    return $output -match $id
}

# winget packages
if (-not (Has-Winget)) {
    Write-Host "[platform/windows] WARNING: winget not found - install from Microsoft Store (App Installer)"
} else {
    foreach ($pkg in $RequiredWinget) {
        if (Is-WingetInstalled $pkg.Id) {
            Write-Host "[platform/windows] $($pkg.Name) already present (skip): $($pkg.Id)"
        } else {
            Write-Host "[platform/windows] installing $($pkg.Name): $($pkg.Id)"
            $result = winget install --silent --accept-package-agreements --accept-source-agreements --id $pkg.Id 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[platform/windows] installed: $($pkg.Id)"
            } else {
                Write-Host "[platform/windows] WARNING: winget install failed for $($pkg.Id) - try manually: winget install $($pkg.Id)"
            }
        }
    }
}

# Python packages (for ppt-academic skill via mckinsey-pptx plugin)
$python = Get-Command python -ErrorAction SilentlyContinue
$pip = Get-Command pip -ErrorAction SilentlyContinue
if ($python -and $pip) {
    foreach ($pkg in $RequiredPip) {
        $installed = python -c "import $($pkg.Import)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[platform/windows] pip package already present (skip): $($pkg.Package)"
        } else {
            Write-Host "[platform/windows] installing pip: $($pkg.Package)"
            pip install --user --quiet $pkg.Package 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[platform/windows] installed pip: $($pkg.Package)"
            } else {
                Write-Host "[platform/windows] WARNING: pip install failed for $($pkg.Package)"
            }
        }
    }
} else {
    Write-Host "[platform/windows] python/pip not found - skipping pip packages (install Python first via: winget install Python.Python.3.11)"
}

# Optional: LibreOffice (visual verification for ppt-academic) - heavy, manual only
$soffice = Get-Command soffice -ErrorAction SilentlyContinue
if (-not $soffice) {
    Write-Host "[platform/windows] HINT: LibreOffice missing - visual verification disabled for ppt-academic"
    Write-Host "[platform/windows]       optional: winget install TheDocumentFoundation.LibreOffice"
    Write-Host "[platform/windows]                 winget install oschwartz10612.Poppler"
}
