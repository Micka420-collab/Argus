"""
Modèles Pydantic — Assets / Inventaire
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AssetType(str, Enum):
    WORKSTATION = "workstation"
    SERVER      = "server"
    NETWORK     = "network_device"
    IOT         = "iot"
    MOBILE      = "mobile"
    CLOUD       = "cloud_instance"
    OTHER       = "other"


class AssetOS(str, Enum):
    WINDOWS = "windows"
    LINUX   = "linux"
    MACOS   = "macos"
    OTHER   = "other"


class AssetCriticality(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class Asset(BaseModel):
    """Asset réseau inventorié."""
    id: Optional[str] = None
    hostname: str
    ip: str
    mac: Optional[str] = None
    type: AssetType = AssetType.WORKSTATION
    os: AssetOS = AssetOS.OTHER
    os_version: Optional[str] = None
    criticality: AssetCriticality = AssetCriticality.MEDIUM

    # Wazuh
    wazuh_agent_id: Optional[str] = None
    wazuh_status: Optional[str] = None  # active, disconnected, never_connected

    # Réseau
    vlan: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    owner: Optional[str] = None

    # Sécurité
    in_maintenance: bool = False
    maintenance_until: Optional[datetime] = None
    tags: List[str] = []

    # Timing
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_in_maintenance(self) -> bool:
        """Vérifie si l'asset est en maintenance active."""
        if not self.in_maintenance:
            return False
        if self.maintenance_until and datetime.utcnow() > self.maintenance_until:
            return False
        return True


class AssetCreate(BaseModel):
    hostname: str
    ip: str
    mac: Optional[str] = None
    type: AssetType = AssetType.WORKSTATION
    os: AssetOS = AssetOS.OTHER
    criticality: AssetCriticality = AssetCriticality.MEDIUM
    department: Optional[str] = None
    owner: Optional[str] = None


class AssetUpdate(BaseModel):
    hostname: Optional[str] = None
    ip: Optional[str] = None
    type: Optional[AssetType] = None
    criticality: Optional[AssetCriticality] = None
    in_maintenance: Optional[bool] = None
    maintenance_until: Optional[datetime] = None
    department: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[List[str]] = None
