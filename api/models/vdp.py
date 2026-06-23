"""
SOC Platform — Modèles VDP / Bug-Bounty (pilier YesWeHack)
==========================================================
Programmes, scopes (avec valeur métier), rapports de vulnérabilité avec
machine à états, scoring CVSS et grille de récompenses.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Énumérations
# ---------------------------------------------------------------------------
class ReportStatus(str, Enum):
    NEW          = "new"
    TRIAGING     = "triaging"
    NEED_INFO    = "need_info"
    ACCEPTED     = "accepted"
    RESOLVED     = "resolved"
    DUPLICATE    = "duplicate"
    OUT_OF_SCOPE = "out_of_scope"
    SPAM         = "spam"
    REJECTED     = "rejected"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    NONE     = "none"


class BusinessValue(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"


# Transitions autorisées de la machine à états
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    ReportStatus.NEW:       {ReportStatus.TRIAGING, ReportStatus.DUPLICATE, ReportStatus.OUT_OF_SCOPE, ReportStatus.SPAM, ReportStatus.REJECTED},
    ReportStatus.TRIAGING:  {ReportStatus.NEED_INFO, ReportStatus.ACCEPTED, ReportStatus.DUPLICATE, ReportStatus.OUT_OF_SCOPE, ReportStatus.REJECTED},
    ReportStatus.NEED_INFO: {ReportStatus.TRIAGING, ReportStatus.ACCEPTED, ReportStatus.REJECTED},
    ReportStatus.ACCEPTED:  {ReportStatus.RESOLVED, ReportStatus.NEED_INFO},
    ReportStatus.RESOLVED:  set(),
    ReportStatus.DUPLICATE: set(),
    ReportStatus.OUT_OF_SCOPE: set(),
    ReportStatus.SPAM:      set(),
    ReportStatus.REJECTED:  set(),
}


# ---------------------------------------------------------------------------
# Modèles
# ---------------------------------------------------------------------------
class Scope(BaseModel):
    asset:          str
    type:           str           = "web"   # web | api | mobile | network
    business_value: BusinessValue = BusinessValue.MEDIUM


class Program(BaseModel):
    id:          str        = ""
    name:        str
    description: str        = ""
    scopes:      list[Scope] = []
    active:      bool       = True
    created_at:  str        = ""


class TriageInfo(BaseModel):
    summary:      str  = ""
    ai_severity:  str  = ""
    is_duplicate: bool = False
    duplicate_of: str  = ""
    notes:        str  = ""
    generated_by: str  = ""


class HistoryEntry(BaseModel):
    at:     str
    actor:  str
    action: str
    detail: str = ""


class ReportCreate(BaseModel):
    """Charge utile de soumission par un chercheur."""
    program_id:  str       = ""
    title:       str
    description: str
    asset:       str       = ""
    endpoint:    str       = ""
    vuln_type:   str       = ""   # ex. CWE-89 / SQLi / XSS
    cvss_vector: str       = ""   # ex. CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H
    poc:         str       = ""
    attachments: list[str] = []


class Report(BaseModel):
    id:               str                = ""
    program_id:       str                = ""
    title:            str
    description:      str
    asset:            str                = ""
    endpoint:         str                = ""
    vuln_type:        str                = ""
    cvss_vector:      str                = ""
    cvss_score:       float              = 0.0
    severity:         str                = "none"
    status:           ReportStatus       = ReportStatus.NEW
    researcher:       str                = ""
    poc:              str                = ""
    attachments:      list[str]          = []
    reward_suggested: int                = 0
    reward_currency:  str                = "EUR"
    triage:           TriageInfo         = TriageInfo()
    history:          list[HistoryEntry] = []
    created_at:       str                = ""
    updated_at:       str                = ""


class StatusUpdate(BaseModel):
    status: ReportStatus
    note:   str = ""
