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
    APP_NAME: str = "SOC Platform"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    SECRET_KEY: str = secrets.token_hex(32)

    # ----------------------------------------------------------
    # OpenSearch
    # ----------------------------------------------------------
    OPENSEARCH_URL: str = "https://opensearch:9200"
    OPENSEARCH_USER: str = "admin"
    OPENSEARCH_PASSWORD: str = ""
    OPENSEARCH_INDEX_ALERTS: str = "wazuh-alerts-*"
    OPENSEARCH_INDEX_SURICATA: str = "soc-suricata-*"

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
