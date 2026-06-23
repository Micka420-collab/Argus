<#
  Argus - Desinstallation (Windows / Docker Desktop)
  Arrete la stack. Optionnel : supprimer les donnees (volumes) et/ou les images.
  Usage : powershell -ExecutionPolicy Bypass -File .\uninstall.ps1 [-Yes]
#>
param([switch]$Yes)
$ErrorActionPreference = "Stop"
function Info($m){ Write-Host ">> $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "OK: $m" -ForegroundColor Green }
function Warn($m){ Write-Host "!  $m" -ForegroundColor Yellow }
function Die($m){ Write-Host "X  $m" -ForegroundColor Red; exit 1 }
function AskYN($q,$def){ if($Yes){return ($def -match '^[Yy]')}; $a=Read-Host "$q (y/n) [$def]"; if([string]::IsNullOrWhiteSpace($a)){$a=$def}; return ($a -match '^[Yy]') }

if (-not (Test-Path "docker-compose.yml")) { Die "Lancez ce script depuis le dossier Argus." }
try { docker compose version | Out-Null } catch { Die "Docker Compose introuvable." }

Warn "Cette operation va ARRETER Argus et supprimer ses conteneurs."
if (-not (AskYN "Continuer ?" "n")) { Info "Annule."; exit 0 }

$dargs = @("down","--remove-orphans")
if (AskYN "Supprimer aussi les DONNEES (volumes : alertes, investigations... IRREVERSIBLE) ?" "n") { $dargs += "-v"; Warn "Les volumes de donnees seront supprimes." }
if (AskYN "Supprimer les images Docker construites par Argus ?" "n") { $dargs += "--rmi"; $dargs += "local" }

Info "Arret de la stack..."
docker compose --profile ai --profile anon @dargs

Ok "Argus a ete arrete et desinstalle."
if ($dargs -contains "-v") { Warn "Donnees supprimees (volumes effaces)." }
Write-Host ""
Info "Pour tout retirer definitivement, supprimez ce dossier :"
Write-Host "    $((Get-Location).Path)"
Write-Host "  (il contient encore .env et nginx\certs - secrets et certificat)."
