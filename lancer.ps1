# GOOD ENGINEERS OS — lancement local Streamlit
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot
$port = 8501

Write-Host ""
Write-Host " Demarrage GOOD ENGINEERS OS" -ForegroundColor Cyan
Write-Host " Dossier: $PSScriptRoot"
Write-Host " URL:     http://localhost:$port"
Write-Host ""

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPy) {
    & $venvPy -m streamlit run app.py --server.port $port
    exit $LASTEXITCODE
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m streamlit run app.py --server.port $port
    exit $LASTEXITCODE
}
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -m streamlit run app.py --server.port $port
    exit $LASTEXITCODE
}

Write-Host "[ERREUR] Python ou Streamlit introuvable." -ForegroundColor Red
Write-Host "  python -m venv .venv"
Write-Host "  .venv\Scripts\pip install -r requirements.txt"
exit 1
