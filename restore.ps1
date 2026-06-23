<#
  Argus - Restauration des donnees (Windows / Docker Desktop)
  Restaure une sauvegarde produite par backup.ps1. ECRASE les donnees actuelles.
  Usage : powershell -ExecutionPolicy Bypass -File .\restore.ps1 <dossier_de_sauvegarde> [-Yes]
#>
param([Parameter(Mandatory=$true)][string]$Source, [switch]$Yes)
$ErrorActionPreference = "Stop"
function Info($m){ Write-Host ">> $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "OK: $m" -ForegroundColor Green }
function Warn($m){ Write-Host "!  $m" -ForegroundColor Yellow }
function Die($m){ Write-Host "X  $m" -ForegroundColor Red; exit 1 }
function AskYN($q,$def){ if($Yes){return ($def -match '^[Yy]')}; $a=Read-Host "$q (y/n) [$def]"; if([string]::IsNullOrWhiteSpace($a)){$a=$def}; return ($a -match '^[Yy]') }

if (-not (Test-Path $Source)) { Die "Dossier introuvable : $Source" }
if (-not (Test-Path "docker-compose.yml")) { Die "Lancez ce script depuis le dossier Argus." }
try { docker version | Out-Null } catch { Die "Docker introuvable." }
$srcAbs = (Resolve-Path $Source).Path

# Prefixe de projet Compose : volume existant, sinon nom du dossier
$existing = docker volume ls -q | Where-Object { $_ -match '_opensearch_data$' } | Select-Object -First 1
if ($existing) { $project = $existing -replace '_opensearch_data$','' }
elseif ($env:COMPOSE_PROJECT_NAME) { $project = $env:COMPOSE_PROJECT_NAME }
else { $project = ((Split-Path -Leaf (Get-Location)).ToLower() -replace '[^a-z0-9_-]','') }
Info "Projet Compose cible : $project"

Warn "La restauration va ECRASER les donnees actuelles d'Argus."
if (-not (AskYN "Continuer ?" "n")) { Info "Annule."; exit 0 }

Info "Arret de la stack..."; try { docker compose stop | Out-Null } catch {}

Info "Restauration des volumes..."
Get-ChildItem "$srcAbs\*.tgz" | ForEach-Object {
  $s = $_.BaseName
  $vol = "${project}_${s}"
  docker volume create $vol | Out-Null
  Info "  - $($_.Name) -> $vol"
  docker run --rm -v "${vol}:/v" -v "${srcAbs}:/in:ro" alpine:3.20 sh -c "rm -rf /v/* /v/..?* 2>/dev/null; tar xzf /in/$s.tgz -C /v"
}

if ((Test-Path "$srcAbs\env.backup") -and (AskYN "Restaurer aussi le fichier .env (secrets) ?" "y")) {
  Copy-Item "$srcAbs\env.backup" .env -Force; Ok "  .env restaure"
}
if ((Test-Path "$srcAbs\certs") -and (AskYN "Restaurer les certificats TLS ?" "y")) {
  New-Item -ItemType Directory -Force "nginx\certs" | Out-Null
  Copy-Item -Recurse -Force "$srcAbs\certs\*" "nginx\certs\"; Ok "  certificats restaures"
}

if (AskYN "Redemarrer Argus maintenant ?" "y") {
  $pf = @()
  if ((Test-Path ".env") -and (Select-String -Path .env -Pattern '^LLM_PROVIDER=ollama' -Quiet)) { $pf += "--profile"; $pf += "ai" }
  if ((Test-Path ".env") -and (Select-String -Path .env -Pattern '^OSINT_ANON=true' -Quiet))     { $pf += "--profile"; $pf += "anon" }
  docker compose @pf up -d
}

Ok "Restauration terminee."
