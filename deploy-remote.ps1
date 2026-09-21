# Pousse les fichiers du projet vers le VPS puis lance deploy.sh a distance.
# Usage (PowerShell, depuis ce dossier ou en passant -LocalProject) :
#   .\deploy-remote.ps1
#   .\deploy-remote.ps1 -VpsHost "gemining.duckdns.org" -RemotePath "/root/projets/GE-MINING"

param(
    [string]$VpsHost = "gemining.duckdns.org",
    [string]$RemotePath = "/root/projets/GE-MINING",
    [string]$LocalProject = $PSScriptRoot,
    [string]$SshUser = "root"
)

$ErrorActionPreference = "Stop"

$items = @(
    @{ Path = "app.py"; Required = $true },
    @{ Path = "equipment_models_catalog.py"; Required = $true },
    @{ Path = "assets"; Required = $true },
    @{ Path = "Dockerfile"; Required = $true },
    @{ Path = "docker-compose.yml"; Required = $true },
    @{ Path = "requirements.txt"; Required = $true },
    @{ Path = "deploy.sh"; Required = $true },
    @{ Path = ".streamlit\config.toml"; Required = $true }
)

Write-Host "=== Verification fichiers locaux ($LocalProject) ===" -ForegroundColor Cyan
foreach ($item in $items) {
    $full = Join-Path $LocalProject $item.Path
    if (-not (Test-Path -LiteralPath $full)) {
        if ($item.Required) {
            throw "Fichier manquant : $full"
        }
    } else {
        Write-Host "  OK $($item.Path)"
    }
}

$appPy = Join-Path $LocalProject "app.py"
$len = (Get-Item -LiteralPath $appPy).Length
if ($len -lt 50000) {
    throw "app.py trop petit ($len o). Mauvais fichier ?"
}

if (-not (Select-String -Path $appPy -Pattern "_ensure_fleet_summary_df" -Quiet)) {
    throw "app.py ne contient pas _ensure_fleet_summary_df - deploiement refuse."
}

$remote = "${SshUser}@${VpsHost}"
Write-Host "`n=== Creation du dossier distant ===" -ForegroundColor Cyan
ssh $remote "mkdir -p $RemotePath/.streamlit"

Write-Host "`n=== SCP vers ${remote}:$RemotePath ===" -ForegroundColor Cyan
scp -q "$(Join-Path $LocalProject "app.py")" "${remote}:${RemotePath}/app.py"
scp -q "$(Join-Path $LocalProject "equipment_models_catalog.py")" "${remote}:${RemotePath}/equipment_models_catalog.py"
scp -q -r "$(Join-Path $LocalProject "assets")" "${remote}:${RemotePath}/"
scp -q "$(Join-Path $LocalProject "Dockerfile")" "${remote}:${RemotePath}/Dockerfile"
scp -q "$(Join-Path $LocalProject "docker-compose.yml")" "${remote}:${RemotePath}/docker-compose.yml"
scp -q "$(Join-Path $LocalProject "requirements.txt")" "${remote}:${RemotePath}/requirements.txt"
scp -q "$(Join-Path $LocalProject "deploy.sh")" "${remote}:${RemotePath}/deploy.sh"
scp -q "$(Join-Path $LocalProject ".streamlit\config.toml")" "${remote}:${RemotePath}/.streamlit/config.toml"

Write-Host "`n=== Deploiement distant (bash deploy.sh) ===" -ForegroundColor Cyan
# Retrait eventuel des CRLF si le fichier a ete edite sous Windows
ssh $remote "sed -i 's/\r$//' $RemotePath/deploy.sh ; chmod +x $RemotePath/deploy.sh && cd $RemotePath && bash deploy.sh"

Write-Host "`nTermine." -ForegroundColor Green
