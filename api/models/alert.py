"""
Modèles Pydantic — Alertes SOC
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


class AlertSeverity(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    NEW        = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED   = "resolved"
    FALSE_POSITIVE = "false_positive"
    SUPPRESSED = "suppressed"


class MitreInfo(BaseModel):
    id: List[str] = []
    tactic: Optional[List[str]] = None
    technique: Optional[List[str]] = None


class RuleInfo(BaseModel):
    id: Optional[str] = None
    level: Optional[int] = None
    description: Optional[str] = None
    groups: Optional[List[str]] = []
    mitre: Optional[MitreInfo] = None


class AgentInfo(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    ip: Optional[str] = None
    os: Optional[str] = None
    labels: Optional[dict] = {}


class GeoInfo(BaseModel):
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    isp: Optional[str] = None


class EnrichmentInfo(BaseModel):
    ip: Optional[str] = None
    risk_score: Optional[int] = None
    abuseipdb: Optional[dict] = None
    virustotal: Optional[dict] = None
    geo: Optional[GeoInfo] = None
    is_tor: Optional[bool] = False
    tags: Optional[List[str]] = []


class Alert(BaseModel):
    """Alerte Wazuh normalisée."""
    id: str
    timestamp: datetime
    rule: Optional[RuleInfo] = None
    agent: Optional[AgentInfo] = None
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    protocol: Optional[str] = None
    severity: AlertSeverity = AlertSeverity.LOW
    status: AlertStatus = AlertStatus.NEW
    enrichment: Optional[EnrichmentInfo] = None
    raw: Optional[dict] = None
    incident_id: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def from_opensearch(cls, hit: dict) -> "Alert":
        """Construit une alerte depuis un hit OpenSearch."""
        source = hit.get("_source", {})
        rule = source.get("rule", {})
        agent = source.get("agent", {})
        data = source.get("data", {})

        # Calcul severity depuis niveau Wazuh
        level = rule.get("level", 0)
        if level >= 14:
            severity = AlertSeverity.CRITICAL
        elif level >= 10:
            severity = AlertSeverity.HIGH
        elif level >= 7:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW

        return cls(
            id=hit.get("_id", ""),
            timestamp=source.get("timestamp", datetime.utcnow()),
            rule=RuleInfo(
                id=str(rule.get("id", "")),
                level=rule.get("level"),
                description=rule.get("description"),
                groups=rule.get("groups", []),
                mitre=MitreInfo(id=rule.get("mitre", {}).get("id", [])),
            ),
            agent=AgentInfo(
                id=agent.get("id"),
                name=agent.get("name"),
                ip=agent.get("ip"),
            ),
            src_ip=data.get("srcip") or source.get("src_ip"),
            severity=severity,
            raw=source,
        )


class AlertCreate(BaseModel):
    """Création manuelle d'une alerte."""
    title: str
    description: str
    severity: AlertSeverity = AlertSeverity.MEDIUM
    src_ip: Optional[str] = None
    agent_name: Optional[str] = None


class AlertUpdate(BaseModel):
    """Mise à jour d'une alerte."""
    status: Optional[AlertStatus] = None
    notes: Optional[str] = None
    assigned_to: Optional[str] = None
    incident_id: Optional[str] = None


class AlertListResponse(BaseModel):
    """Réponse paginée pour la liste d'alertes."""
    total: int
    page: int
    per_page: int
    items: List[Alert]
    has_next: bool
