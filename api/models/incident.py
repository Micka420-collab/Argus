"""
Modèles Pydantic — Incidents SOC
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class IncidentSeverity(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    OPEN        = "open"
    INVESTIGATING = "investigating"
    CONTAINED   = "contained"
    ERADICATED  = "eradicated"
    RECOVERED   = "recovered"
    CLOSED      = "closed"


class IncidentCategory(str, Enum):
    MALWARE           = "malware"
    RANSOMWARE        = "ransomware"
    PHISHING          = "phishing"
    DATA_BREACH       = "data_breach"
    INSIDER_THREAT    = "insider_threat"
    BRUTE_FORCE       = "brute_force"
    LATERAL_MOVEMENT  = "lateral_movement"
    C2                = "command_and_control"
    VULNERABILITY     = "vulnerability_exploitation"
    OTHER             = "other"


class TimelineEntry(BaseModel):
    """Entrée dans la chronologie d'un incident."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    author: str = "system"
    action: str
    details: Optional[str] = None


class Incident(BaseModel):
    """Incident de sécurité."""
    id: Optional[str] = None
    title: str
    description: Optional[str] = None
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    status: IncidentStatus = IncidentStatus.OPEN
    category: IncidentCategory = IncidentCategory.OTHER

    # Alertes associées
    alert_ids: List[str] = []
    # Assets impactés
    affected_assets: List[str] = []
    # IPs liées
    iocs: List[str] = []
    # MITRE ATT&CK TTPs
    ttps: List[str] = []

    # Assignation et timing
    assigned_to: Optional[str] = None
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    sla_breach: bool = False

    # Timeline des actions
    timeline: List[TimelineEntry] = []

    # Rapport post-incident
    root_cause: Optional[str] = None
    remediation: Optional[str] = None
    lessons_learned: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class IncidentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    category: IncidentCategory = IncidentCategory.OTHER
    alert_ids: List[str] = []
    assigned_to: Optional[str] = None


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[IncidentSeverity] = None
    status: Optional[IncidentStatus] = None
    assigned_to: Optional[str] = None
    affected_assets: Optional[List[str]] = None
    iocs: Optional[List[str]] = None
    ttps: Optional[List[str]] = None
    root_cause: Optional[str] = None
    remediation: Optional[str] = None
    lessons_learned: Optional[str] = None


class IncidentAddNote(BaseModel):
    note: str
    author: str = "analyst"
