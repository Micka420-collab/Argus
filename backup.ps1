<#
  Argus - Sauvegarde des donnees (Windows / Docker Desktop)
  Sauvegarde les volumes Docker + .env + certificats dans backups\argus-<horodatage>\.
  Usage : powershell -ExecutionPolicy Bypass -File .\backup.ps1 [-Yes] [-Dest <dossier>]
#>
param([switch]$Yes, [string]$Dest = "backups")
$ErrorActionPreference = "Stop"
function Info($m){ Write-Host ">> $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "OK: $m" -ForegroundColor Green }
function Warn($m){ Write-Host "!  $m" -ForegroundColor Yellow }
function Die($m){ Write-Host "X  $m" -ForegroundColor Red; exit 1 }
function AskYN($q,$def){ if($Yes){return ($def -match '^[Yy]')}; $a=Read-Host "$q (y/n) [$def]"; if([string]::IsNullOrWhiteSpace($a)){$a=$def}; return ($a -match '^[Yy]') }

if (-not (Test-Path "docker-compose.yml")) { Die "Lancez ce script depuis le dossier Argus." }
try { docker version | Out-Null } catch { Die "Docker introuvable." }

$suffixes = @("opensearch_data","wazuh_etc","wazuh_data","wazuh_queue","redis_data","pqc_keys","suricata_rules")
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$destDir = Join-Path $Dest "argus-$stamp"
New-Item -ItemType Directory -Force $destDir | Out-Null
$destAbs = (Resolve-Path $destDir).Path

$stopped = $false
if (AskYN "Arreter la stack pendant la sauvegarde (recommande) ?" "y") { Info "Arret temporaire..."; try { docker compose stop | Out-Null } catch {}; $stopped = $true }

Info "Sauvegarde des volumes..."
$count = 0
$vols = docker volume ls -q
foreach ($v in $vols) {
  foreach ($s in $suffixes) {
    if ($v -match "(^|_)$([regex]::Escape($s))$") {
      Info "  - $v"
      docker run --rm -v "${v}:/v:ro" -v "${destAbs}:/out" alpine:3.20 sh -c "tar czf /out/$s.tgz -C /v . 2>/dev/null"
      Add-Content "$destDir\manifest.txt" "$s.tgz <= $v"
      $count++
    }
  }
}

if (Test-Path ".env") { Copy-Item .env "$destDir\env.backup"; Info "  - .env" }
if (Test-Path "nginx\certs") { Copy-Item -Recurse "nginx\certs" "$destDir\certs"; Info "  - nginx\certs" }
Add-Content "$destDir\manifest.txt" "argus_backup=$stamp; volumes=$count"

if ($stopped) { Info "Redemarrage de la stack..."; try { docker compose start | Out-Null } catch { docker compose up -d | Out-Null } }

Ok "Sauvegarde terminee : $destDir  ($count volume(s))"
Write-Host "  Restaurer avec : .\restore.ps1 `"$destDir`""
Warn "Ce dossier contient des SECRETS (.env, cles, certificats) - stockez-le de facon securisee."
