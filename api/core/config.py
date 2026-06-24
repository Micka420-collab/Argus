"""
Configuration centralisée — SOC Platform
Toutes les variables d'environnement sont typées et validées par Pydantic.
"""
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, field_validator
from typing import Optional
import secrets


class Settings(BaseSettings):
    # ----------------------------------------------------------
    # Application
    # ----------------------------------------------------------
    APP_NAME: str = "Argus SOC"
    APP_VERSION: str = "3.0.0"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    SECRET_KEY: str = secrets.token_hex(32)
    # Domaine/IP de la console — sert d'adresse de manager pour l'enrôlement des agents
    SOC_DOMAIN: str = "soc.lan"

    # Compte admin créé au premier démarrage (configurable par l'installeur)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "Admin@SOC2024!"   # bootstrap — à changer en production

    # ----------------------------------------------------------
    # OpenSearch
    # ----------------------------------------------------------
    OPENSEARCH_URL: str = "https://opensearch:9200"
    OPENSEARCH_USER: str = "admin"
    OPENSEARCH_PASSWORD: str = ""
    OPENSEARCH_INDEX_ALERTS: str = "wazuh-alerts-*"
    OPENSEARCH_INDEX_SURICATA: str = "soc-suricata-*"
    OPENSEARCH_INDEX_AI: str = "soc-investigations"   # rapports de l'agent IA autonome
    OPENSEARCH_INDEX_VDP: str = "soc-vdp-reports"     # rapports VDP / bug-bounty
    OPENSEARCH_INDEX_EXPOSURE: str = "soc-exposure"   # ASM/CTEM (assets + findings)

    # ----------------------------------------------------------
    # Wazuh API
    # ----------------------------------------------------------
    WAZUH_API_URL: str = "https://wazuh-manager:55000"
    WAZUH_API_USER: str = "wazuh-wui"
    WAZUH_API_PASSWORD: str = ""

    # ----------------------------------------------------------
    # Redis
    # ----------------------------------------------------------
    REDIS_URL: str = "redis://redis:6379"
    REDIS_PASSWORD: str = ""

    # ----------------------------------------------------------
    # Notifications
    # ----------------------------------------------------------
    PUSHOVER_TOKEN: Optional[str] = None
    PUSHOVER_USER: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    DISCORD_WEBHOOK: Optional[str] = None

    # ----------------------------------------------------------
    # Threat Intelligence
    # ----------------------------------------------------------
    ABUSEIPDB_KEY: Optional[str] = None
    VIRUSTOTAL_KEY: Optional[str] = None
    MISP_URL: Optional[str] = None
    MISP_KEY: Optional[str] = None

    # ----------------------------------------------------------
    # Alerting
    # ----------------------------------------------------------
    ALERT_MIN_LEVEL: int = 10          # Niveau minimum pour alerter
    ALERT_CRITICAL_LEVEL: int = 14     # Niveau pour alerte immédiate
    DEDUP_WINDOW_MINUTES: int = 10     # Fenêtre de déduplication
    GROUP_FLUSH_SECONDS: int = 30      # Intervalle de groupement
    POLL_INTERVAL_SECONDS: int = 15    # Intervalle polling OpenSearch

    # ----------------------------------------------------------
    # Enrichissement
    # ----------------------------------------------------------
    ENRICH_RISK_THRESHOLD: int = 90    # Score risque déclenchant escalade
    ENRICH_CACHE_TTL: int = 3600       # Cache enrichissement (1 heure)

    # ----------------------------------------------------------
    # Analyste IA autonome (pilier Qevlar) — LLM borné
    # Le LLM ne décide JAMAIS du verdict : il rédige seulement le rapport.
    # ----------------------------------------------------------
    LLM_PROVIDER: str = "none"             # none | ollama | claude
    LLM_BASE_URL: str = "http://ollama:11434"
    LLM_MODEL: Optional[str] = None        # ex. qwen2.5:7b | claude-sonnet-4-6
    # Inférence CPU (sans GPU) : chargement à froid + génération peuvent être
    # longs. 240 s offre une marge confortable même pour un modèle moyen en CPU.
    # Sur GPU les appels durent quelques secondes — cette valeur n'est qu'un plafond.
    LLM_TIMEOUT: float = 240.0
    # Durée pendant laquelle Ollama garde le modèle en RAM entre deux appels
    # (évite de recharger 4-5 Go à chaque investigation). "0" = décharge aussitôt.
    LLM_KEEP_ALIVE: str = "30m"
    # Plafond de tokens générés : borne la longueur du récit → réponse plus
    # rapide et prévisible (le verdict reste déterministe, le LLM ne fait que rédiger).
    LLM_NUM_PREDICT: int = 768
    ANTHROPIC_API_KEY: Optional[str] = None
    AI_AUTO_INVESTIGATE: bool = False      # auto-déclenche l'IA sur alertes critiques

    # ----------------------------------------------------------
    # Égress anonymisé (pilier Snowpack) — OSINT via Tor/proxy
    # ----------------------------------------------------------
    OUTBOUND_PROXY: Optional[str] = None   # ex. socks5://anon-gateway:9050
    OSINT_ANON: bool = False               # router l'OSINT par OUTBOUND_PROXY
    TOR_CONTROL_URL: Optional[str] = None  # endpoint HTTP NEWNYM (rotation IP)

    # ----------------------------------------------------------
    # Webhooks sortants (sync tickets — n8n / Slack / Jira…)
    # ----------------------------------------------------------
    WEBHOOK_URL: Optional[str] = None      # ex. http://n8n:5678/webhook/argus
    WEBHOOK_SECRET: Optional[str] = None   # signe les events (HMAC-SHA256)

    # ----------------------------------------------------------
    # Posture post-quantique (pilier CryptoNext)
    # ----------------------------------------------------------
    JWT_ALGORITHM: str = "HS256"
    PQC_JWT: bool = False                  # signatures JWT hybrides Ed25519+ML-DSA
    PQC_KEYS_DIR: str = "/var/lib/argus/pqc"  # persistance des clés ML-DSA (si liboqs)
    TLS_GROUPS: str = "X25519MLKEM768:X25519:secp256r1"  # groupes TLS edge (hybride PQC)
    TLS_CERT_SIG: str = "RSA-4096"         # type de signature du certificat serveur

    # ----------------------------------------------------------
    # CORS (pour le frontend React)
    # ----------------------------------------------------------
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:80",
        "http://soc-frontend",
    ]

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT doit être l'un de {allowed}")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


# Instance globale (singleton)
settings = Settings()
