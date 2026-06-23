<#
  Argus - Installeur guide (Windows / Docker Desktop)
  Usage :
    powershell -ExecutionPolicy Bypass -File .\install.ps1
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -Yes   # valeurs par defaut
#>
param([switch]$Yes)
$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/Micka420-collab/Argus.git"

function Info($m){ Write-Host ">> $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "OK: $m" -ForegroundColor Green }
function Warn($m){ Write-Host "!  $m" -ForegroundColor Yellow }
function Die($m){ Write-Host "X  $m" -ForegroundColor Red; exit 1 }

function Ask($q,$def){ if($Yes){return $def}; $a=Read-Host "$q [$def]"; if([string]::IsNullOrWhiteSpace($a)){return $def}; return $a }
function AskYN($q,$def){ $a=Ask "$q (y/n)" $def; return ($a -match '^[Yy]') }

function New-Secret([int]$bytes=32){
  $b=New-Object byte[] $bytes
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
  return (($b | ForEach-Object { $_.ToString('x2') }) -join '')
}
function New-Pass {
  $b=New-Object byte[] 24
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
  $s=([Convert]::ToBase64String($b)) -replace '[^A-Za-z0-9]',''
  return ($s.Substring(0,[Math]::Min(24,$s.Length)) + 'Aa1!')
}

Write-Host ""
Write-Host "  Argus - SOC autonome et post-quantique" -ForegroundColor Cyan
Write-Host "  Installeur guide (Windows)" -ForegroundColor Cyan
Write-Host ""

# 1. Prerequis
Info "Verification de Docker..."
try { docker version | Out-Null } catch { Die "Docker Desktop requis : https://www.docker.com/products/docker-desktop/" }
try { docker compose version | Out-Null } catch { Die "Docker Compose v2 requis (inclus dans Docker Desktop)." }
Ok "Docker et Compose detectes."

# 2. Depot
if (-not (Test-Path "docker-compose.yml")) {
  Info "Clonage du depot Argus..."
  try { git --version | Out-Null } catch { Die "git requis pour cloner." }
  git clone --depth 1 $RepoUrl Argus
  Set-Location Argus
}
Ok "Depot pret : $(Get-Location)"

# 3. .env
if (Test-Path ".env") { if (AskYN ".env existe deja. Le REGENERER (ecrase les secrets) ?" "n") { Remove-Item .env } }

if (-not (Test-Path ".env")) {
  Info "Configuration de la plateforme..."
  $Domain    = Ask "Nom de domaine de la console" "soc.lan"
  $AdminUser = Ask "Identifiant administrateur"    "admin"
  $LlmProvider="none"; $LlmModel=""
  if (AskYN "Activer l'analyste IA local (Ollama) ? (~8 Go RAM)" "n") { $LlmProvider="ollama"; $LlmModel=Ask "Modele Ollama" "qwen2.5:7b" }
  $PqcJwt = "false"; if (AskYN "Activer les jetons post-quantiques (JWT Ed25519) ?" "n") { $PqcJwt="true" }
  $OsintAnon="false"; $EnableAnon=$false
  if (AskYN "Anonymiser l'OSINT via Tor (passerelle anon-gateway) ?" "n") { $OsintAnon="true"; $EnableAnon=$true }
  $AbuseKey = Ask "Cle AbuseIPDB (optionnel)" ""
  $VtKey    = Ask "Cle VirusTotal (optionnel)" ""

  Info "Generation des secrets..."
  $AdminPass = New-Pass
  $envLines = @(
    "# Genere par install.ps1",
    "SECRET_KEY=$(New-Secret)",
    "JWT_ALGORITHM=HS256",
    "ENVIRONMENT=production",
    "SOC_DOMAIN=$Domain",
    "NETWORK_INTERFACE=eth0",
    "WAZUH_API_USER=wazuh-wui",
    "DASHBOARD_USERNAME=kibanaserver",
    "",
    "ADMIN_USERNAME=$AdminUser",
    "ADMIN_PASSWORD=$AdminPass",
    "",
    "OPENSEARCH_PASSWORD=$(New-Pass)",
    "REDIS_PASSWORD=$(New-Pass)",
    "WAZUH_API_PASSWORD=$(New-Pass)",
    "DASHBOARD_PASSWORD=$(New-Pass)",
    "",
    "LLM_PROVIDER=$LlmProvider",
    "LLM_MODEL=$LlmModel",
    "AI_AUTO_INVESTIGATE=false",
    "",
    "PQC_JWT=$PqcJwt",
    "TLS_GROUPS=X25519MLKEM768:X25519:secp256r1",
    "",
    "OSINT_ANON=$OsintAnon"
  )
  if ($OsintAnon -eq "true") { $envLines += "OUTBOUND_PROXY=socks5://anon-gateway:9050"; $envLines += "TOR_CONTROL_URL=http://anon-gateway:9052/newnym" }
  $envLines += @("", "ABUSEIPDB_KEY=$AbuseKey", "VIRUSTOTAL_KEY=$VtKey")
  [IO.File]::WriteAllText((Join-Path (Get-Location) ".env"), ($envLines -join "`n"), (New-Object System.Text.UTF8Encoding($false)))
  Ok "Fichier .env genere."
} else {
  Ok ".env conserve."
  $lines = Get-Content .env | Where-Object { $_ -match '=' }
  function Cfg($k){ foreach($l in $lines){ $p=$l -split '=',2; if($p[0] -eq $k){ return $p[1] } }; return "" }
  $Domain=Cfg "SOC_DOMAIN"; if(-not $Domain){$Domain="soc.lan"}
  $AdminUser=Cfg "ADMIN_USERNAME"; $AdminPass=Cfg "ADMIN_PASSWORD"
  $LlmProvider=Cfg "LLM_PROVIDER"; $LlmModel=Cfg "LLM_MODEL"
  $EnableAnon = ((Cfg "OSINT_ANON") -eq "true")
}

# 4. Certificat TLS (via conteneur, pas besoin d'OpenSSL local)
New-Item -ItemType Directory -Force nginx\certs | Out-Null
if (-not (Test-Path "nginx\certs\soc.crt")) {
  Info "Generation d'un certificat TLS auto-signe (via Docker)..."
  $subj = "/C=FR/O=Argus/CN=$Domain"
  $san  = "subjectAltName=DNS:$Domain,DNS:localhost,IP:127.0.0.1"
  $cmd  = "apk add --no-cache openssl >/dev/null 2>&1 && openssl req -x509 -newkey rsa:4096 -nodes -days 825 -keyout /certs/soc.key -out /certs/soc.crt -subj '$subj' -addext '$san'"
  $mount = "$((Get-Location).Path)\nginx\certs:/certs"
  docker run --rm -v $mount alpine:3.20 sh -c $cmd
  if (Test-Path "nginx\certs\soc.crt") { Ok "Certificat genere." } else { Warn "Echec - fournir nginx\certs\soc.crt et soc.key manuellement." }
} else { Ok "Certificat deja present." }

# 5. Build et demarrage
$pf = @()
if ($LlmProvider -eq "ollama") { $pf += "--profile"; $pf += "ai" }
if ($EnableAnon)               { $pf += "--profile"; $pf += "anon" }

Info "Construction des images (quelques minutes)..."
docker compose @pf build
Info "Demarrage de la stack..."
docker compose @pf up -d

if ($LlmProvider -eq "ollama") {
  $m = if($LlmModel){$LlmModel}else{"qwen2.5:7b"}
  Info "Telechargement du modele LLM ($m)..."
  try { docker compose exec -T ollama ollama pull $m } catch { Warn "A relancer : docker compose exec ollama ollama pull $m" }
}

# 6. Recapitulatif
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Ok "Argus est lance !"
Write-Host ""
Write-Host "  Console      : https://$Domain  (ou https://localhost)"
Write-Host "  Presentation : https://localhost/welcome"
Write-Host "  Identifiant  : $AdminUser"
Write-Host "  Mot de passe : $AdminPass"
Write-Host ""
Warn "Certificat auto-signe : avertissement navigateur normal en local."
Write-Host "  Etat : docker compose ps  |  Logs : docker compose logs -f soc-api  |  Arret : docker compose down" -ForegroundColor DarkGray
Write-Host "========================================" -ForegroundColor Green
