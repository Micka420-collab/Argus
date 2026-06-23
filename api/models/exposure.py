"""
SOC Platform — Modèles ASM / CTEM (gestion de surface d'attaque)
================================================================
Assets exposés et findings (vulnérabilités) priorisés par exposition réelle :
CVSS × EPSS × KEV × valeur métier.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from api.models.vdp import BusinessValue   # réutilise l'échelle de valeur métier


class FindingStatus(str, Enum):
    OPEN           = "open"
    TRIAGED        = "triaged"
    MITIGATED      = "mitigated"
    ACCEPTED       = "accepted"
    FALSE_POSITIVE = "false_positive"


class ExposureAsset(BaseModel):
    id:             str           = ""
    name:           str                           # hostname, URL, IP, service
    type:           str           = "host"        # host | web | api | service
    business_value: BusinessValue = BusinessValue.MEDIUM
    tags:           list[str]     = []
    first_seen:     str           = ""
    last_seen:      str           = ""


class FindingCreate(BaseModel):
    asset:       str
    title:       str
    cve:         str  = ""
    cvss:        float = 0.0
    description: str  = ""
    source:      str  = "manual"   # manual | nuclei | import | scan


class Finding(BaseModel):
    id:              str          = ""
    asset:           str
    title:           str
    cve:             str          = ""
    cvss:            float        = 0.0
    epss:            float        = 0.0
    epss_percentile: float        = 0.0
    in_kev:          bool         = False
    priority_score:  int          = 0
    priority_tier:   str          = "low"   # critical | high | medium | low
    status:          FindingStatus = FindingStatus.OPEN
    source:          str          = "manual"
    description:     str          = ""
    created_at:      str          = ""
    updated_at:      str          = ""


class FindingStatusUpdate(BaseModel):
    status: FindingStatus
