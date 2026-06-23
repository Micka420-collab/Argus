<#
  Argus - Mise a jour (Windows / Docker Desktop)
  Recupere la derniere version, reconstruit et redemarre. Preserve .env, certs, donnees.
  Usage : powershell -ExecutionPolicy Bypass -File .\update.ps1 [-Yes]
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

$pf = @()
if ((Test-Path ".env") -and (Select-String -Path .env -Pattern '^LLM_PROVIDER=ollama' -Quiet)) { $pf += "--profile"; $pf += "ai" }
if ((Test-Path ".env") -and (Select-String -Path .env -Pattern '^OSINT_ANON=true' -Quiet))     { $pf += "--profile"; $pf += "anon" }

Info "Recuperation de la derniere version (git pull)..."
try { git pull --ff-only } catch { Warn "git pull impossible (modifs locales ?). Poursuite avec le code actuel." }

Info "Reconstruction des images..."
docker compose @pf build
Info "Redemarrage de la stack..."
docker compose @pf up -d

if (AskYN "Nettoyer les anciennes images Docker inutilisees ?" "y") {
  try { docker image prune -f | Out-Null; Ok "Images inutilisees nettoyees." } catch {}
}

Ok "Mise a jour terminee."
docker compose @pf ps
