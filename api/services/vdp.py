"""
SOC Platform — Service VDP / Bug-Bounty (pilier YesWeHack)
==========================================================
- Calculateur CVSS v3.1 (base score) — déterministe, sans dépendance.
- Grille de récompenses (sévérité × valeur métier).
- Machine à états des rapports + historique.
- Stockage OpenSearch (soc-vdp-reports / soc-vdp-programs), repli gracieux.
"""
from __future__ import annotations

import math
import uuid
import logging
from datetime import datetime, timezone

from api.core.config import settings
from api.models.vdp import (
    Report, ReportCreate, Program, Scope, TriageInfo, HistoryEntry,
    ReportStatus, Severity, BusinessValue, ALLOWED_TRANSITIONS,
)

logger = logging.getLogger(__name__)

REPORTS_INDEX  = settings.OPENSEARCH_INDEX_VDP
PROGRAMS_INDEX = settings.OPENSEARCH_INDEX_VDP + "-programs"


# ===========================================================================
# CVSS v3.1 — base score (cf. FIRST.org Specification, Appendix A)
# ===========================================================================
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}
_AC = {"L": 0.77, "H": 0.44}
_UI = {"N": 0.85, "R": 0.62}
_PR_U = {"N": 0.85, "L": 0.62, "H": 0.27}   # Scope Unchanged
_PR_C = {"N": 0.85, "L": 0.68, "H": 0.50}   # Scope Changed
_CIA = {"H": 0.56, "L": 0.22, "N": 0.0}


def _roundup(value: float) -> float:
    """Roundup officiel CVSS v3.1 (évite les artefacts flottants)."""
    int_input = round(value * 100000)
    if int_input % 10000 == 0:
        return int_input / 100000.0
    return (math.floor(int_input / 10000) + 1) / 10.0


def _severity_from_score(score: float) -> str:
    if score == 0:        return Severity.NONE
    if score < 4.0:       return Severity.LOW
    if score < 7.0:       return Severity.MEDIUM
    if score < 9.0:       return Severity.HIGH
    return Severity.CRITICAL


def parse_cvss_vector(vector: str) -> dict[str, str]:
    """Parse 'CVSS:3.1/AV:N/AC:L/...' → {AV:N, AC:L, ...}."""
    out: dict[str, str] = {}
    for part in (vector or "").split("/"):
        if ":" in part:
            k, v = part.split(":", 1)
            if k != "CVSS":
                out[k.strip().upper()] = v.strip().upper()
    return out


def compute_cvss(vector: str) -> tuple[float, str]:
    """
    Retourne (base_score, severity). 0.0/'none' si le vecteur est incomplet
    ou invalide (pas d'exception — robuste aux soumissions partielles).
    """
    m = parse_cvss_vector(vector)
    required = ("AV", "AC", "PR", "UI", "S", "C", "I", "A")
    if not all(k in m for k in required):
        return 0.0, Severity.NONE
    try:
        scope_changed = m["S"] == "C"
        av = _AV[m["AV"]]; ac = _AC[m["AC"]]; ui = _UI[m["UI"]]
        pr = (_PR_C if scope_changed else _PR_U)[m["PR"]]
        c = _CIA[m["C"]]; i = _CIA[m["I"]]; a = _CIA[m["A"]]
    except KeyError:
        return 0.0, Severity.NONE

    iss = 1 - ((1 - c) * (1 - i) * (1 - a))
    if scope_changed:
        impact = 7.52 * (iss - 0.029) - 3.25 * ((iss - 0.02) ** 15)
    else:
        impact = 6.42 * iss
    exploitability = 8.22 * av * ac * pr * ui

    if impact <= 0:
        return 0.0, Severity.NONE
    if scope_changed:
        base = _roundup(min(1.08 * (impact + exploitability), 10))
    else:
        base = _roundup(min(impact + exploitability, 10))
    return base, _severity_from_score(base)


# ===========================================================================
# Grille de récompenses : sévérité × valeur métier du scope
# ===========================================================================
_REWARD_GRID: dict[str, dict[str, int]] = {
    #               low    medium  high   critical   (valeur métier du scope)
    Severity.CRITICAL: {"low": 800, "medium": 1500, "high": 3000, "critical": 5000},
    Severity.HIGH:     {"low": 400, "medium": 800,  "high": 1500, "critical": 2500},
    Severity.MEDIUM:   {"low": 150, "medium": 300,  "high": 600,  "critical": 1000},
    Severity.LOW:      {"low": 50,  "medium": 100,  "high": 150,  "critical": 300},
    Severity.NONE:     {"low": 0,   "medium": 0,    "high": 0,    "critical": 0},
}


def suggest_reward(severity: str, business_value: str = "medium") -> int:
    return _REWARD_GRID.get(severity, _REWARD_GRID[Severity.NONE]).get(business_value, 0)


# ===========================================================================
# Accès OpenSearch
# ===========================================================================
async def _client():
    from api.services.opensearch import OpenSearchClient
    return await OpenSearchClient().get_client()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scope_business_value(program: Program | None, asset: str) -> str:
    if not program:
        return BusinessValue.MEDIUM
    for s in program.scopes:
        if s.asset and asset and (s.asset == asset or s.asset in asset):
            return s.business_value
    return BusinessValue.MEDIUM


# ---- Programmes -----------------------------------------------------------
async def list_programs() -> list[dict]:
    try:
        client = await _client()
        resp = await client.search(index=PROGRAMS_INDEX, body={"size": 100, "query": {"match_all": {}}})
        return [h["_source"] for h in resp.get("hits", {}).get("hits", [])]
    except Exception as e:
        logger.info("list_programs indisponible (%s)", e)
        return []


async def get_program(program_id: str) -> Program | None:
    try:
        client = await _client()
        resp = await client.get(index=PROGRAMS_INDEX, id=program_id)
        return Program(**resp["_source"])
    except Exception:
        return None


async def create_program(program: Program) -> Program:
    program.id = program.id or uuid.uuid4().hex[:12]
    program.created_at = _now()
    try:
        client = await _client()
        await client.index(index=PROGRAMS_INDEX, id=program.id, body=program.model_dump(), refresh=True)
    except Exception as e:
        logger.warning("create_program impossible (%s)", e)
    return program


async def ensure_default_program() -> Program:
    """Crée un programme par défaut si aucun n'existe (démo prête à l'emploi)."""
    progs = await list_programs()
    if progs:
        return Program(**progs[0])
    default = Program(
        name="Argus — Programme par défaut",
        description="Programme VDP par défaut couvrant l'infrastructure supervisée.",
        scopes=[
            Scope(asset="*.local", type="web", business_value=BusinessValue.HIGH),
            Scope(asset="api", type="api", business_value=BusinessValue.CRITICAL),
        ],
    )
    return await create_program(default)


# ---- Rapports -------------------------------------------------------------
async def create_report(payload: ReportCreate, researcher: str) -> Report:
    score, severity = compute_cvss(payload.cvss_vector)
    program = await get_program(payload.program_id) if payload.program_id else None
    if program is None:
        program = await ensure_default_program()
    bv = _scope_business_value(program, payload.asset)

    report = Report(
        id=uuid.uuid4().hex[:12],
        program_id=program.id,
        title=payload.title,
        description=payload.description,
        asset=payload.asset,
        endpoint=payload.endpoint,
        vuln_type=payload.vuln_type,
        cvss_vector=payload.cvss_vector,
        cvss_score=score,
        severity=severity,
        status=ReportStatus.NEW,
        researcher=researcher,
        poc=payload.poc,
        attachments=payload.attachments,
        reward_suggested=suggest_reward(severity, bv),
        created_at=_now(),
        updated_at=_now(),
        history=[HistoryEntry(at=_now(), actor=researcher, action="submitted",
                              detail=f"Rapport soumis ({severity}, CVSS {score})")],
    )

    # Triage assisté (best-effort)
    try:
        from api.services.vdp_triage import triage_report
        report.triage = await triage_report(report)
        if report.triage.is_duplicate:
            report.history.append(HistoryEntry(at=_now(), actor="argus-ai", action="flagged_duplicate",
                                               detail=f"Doublon possible de {report.triage.duplicate_of}"))
    except Exception as e:
        logger.debug("Triage IA indisponible (%s)", e)

    try:
        client = await _client()
        await client.index(index=REPORTS_INDEX, id=report.id, body=report.model_dump(), refresh=True)
    except Exception as e:
        logger.warning("create_report: persistance impossible (%s)", e)
    return report


async def get_report(report_id: str) -> dict | None:
    try:
        client = await _client()
        resp = await client.get(index=REPORTS_INDEX, id=report_id)
        return resp["_source"]
    except Exception:
        return None


async def list_reports(status: str | None = None, size: int = 100) -> list[dict]:
    try:
        client = await _client()
        query = {"term": {"status": status}} if status else {"match_all": {}}
        resp = await client.search(
            index=REPORTS_INDEX,
            body={"size": size, "query": query, "sort": [{"created_at": {"order": "desc"}}]},
        )
        return [h["_source"] for h in resp.get("hits", {}).get("hits", [])]
    except Exception as e:
        logger.info("list_reports indisponible (%s)", e)
        return []


async def transition(report_id: str, new_status: str, actor: str, note: str = "") -> dict:
    """Applique une transition d'état validée + journalise l'historique."""
    raw = await get_report(report_id)
    if not raw:
        raise ValueError("Rapport introuvable")
    current = raw.get("status", ReportStatus.NEW)
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new_status != current and new_status not in allowed:
        raise ValueError(f"Transition interdite : {current} → {new_status}")

    raw["status"] = new_status
    raw["updated_at"] = _now()
    raw.setdefault("history", []).append(
        HistoryEntry(at=_now(), actor=actor, action=f"status:{new_status}", detail=note).model_dump()
    )
    try:
        client = await _client()
        await client.index(index=REPORTS_INDEX, id=report_id, body=raw, refresh=True)
    except Exception as e:
        logger.warning("transition: persistance impossible (%s)", e)
    return raw


async def stats() -> dict:
    """Compteurs par statut/sévérité pour le dashboard VDP."""
    reports = await list_reports(size=500)
    by_status: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    total_reward = 0
    for r in reports:
        by_status[r.get("status", "new")] = by_status.get(r.get("status", "new"), 0) + 1
        by_severity[r.get("severity", "none")] = by_severity.get(r.get("severity", "none"), 0) + 1
        if r.get("status") in ("accepted", "resolved"):
            total_reward += int(r.get("reward_suggested", 0) or 0)
    return {"total": len(reports), "by_status": by_status, "by_severity": by_severity,
            "reward_committed": total_reward}
