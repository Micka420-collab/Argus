"""
SOC Platform — Moteur de verdict unifié
========================================

Source de vérité UNIQUE pour le scoring de risque. Remplace les deux
logiques divergentes qui existaient auparavant :
  - investigation.InvestigationService._assess_risk  (riche, OSINT complet)
  - enrichment.EnrichmentService._compute_risk        (simple, 60/40 abuse/VT)

Le verdict est **déterministe** (calculé en Python pur). Aucun LLM n'intervient
ici : c'est le principe « bounded LLM » — le modèle ne sert qu'à rédiger le
rapport, jamais à décider si une IP est malveillante.

Sortie : un `RiskAssessment` contenant
  - score 0-100 + level (low|medium|high|critical)
  - verdict 3 états (malicious|benign|inconclusive) + confidence 0-100
  - factors (explications lisibles) + recommended_actions
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Modèles partagés (canoniques — importés par investigation.py & co.)
# ---------------------------------------------------------------------------
class RecommendedAction(BaseModel):
    action:      str
    label:       str
    description: str
    priority:    str   # high|medium|low


class RiskAssessment(BaseModel):
    score:               int                     = 0
    level:               str                     = "low"        # low|medium|high|critical
    verdict:             str                     = "inconclusive"  # malicious|benign|inconclusive
    confidence:          int                     = 0            # 0-100
    factors:             list[str]               = []
    recommended_actions: list[RecommendedAction] = []


# ---------------------------------------------------------------------------
# Conteneur de preuves — découple le scorer des modèles OSINT (pas d'import
# circulaire avec investigation.py).
# ---------------------------------------------------------------------------
@dataclass
class Evidence:
    # AbuseIPDB
    abuse_confidence:    int        = 0
    abuse_total_reports: int        = 0
    abuse_categories:    list[str]  = field(default_factory=list)
    is_tor:              bool       = False
    # VirusTotal
    vt_malicious:        int        = 0
    vt_suspicious:       int        = 0
    # Profil d'attaque interne (alertes Wazuh/Suricata liées à l'IP)
    attack_type:         str        = "unknown"
    attack_intensity:    str        = "low"      # low|medium|high|critical
    attack_alert_count:  int        = 0
    attack_rpm:          float      = 0.0
    targeted_services:   list[str]  = field(default_factory=list)
    # Infrastructure
    is_proxy:            bool       = False
    is_hosting:          bool       = False
    asn:                 str        = ""
    asn_name:            str        = ""
    isp:                 str        = ""


# Catégories AbuseIPDB considérées comme dangereuses (boost de score)
DANGER_CATS = {
    "DDoS Attack", "Brute-Force", "SSH Brute-Force", "FTP Brute-Force",
    "Web App Attack", "Hacking", "SQL Injection", "Exploited Host",
}


# ---------------------------------------------------------------------------
# Calcul du score (0-100) + facteurs explicatifs
# ---------------------------------------------------------------------------
def _score_and_factors(ev: Evidence) -> tuple[int, list[str], int, int]:
    """
    Retourne (score, factors, malicious_signals, benign_signals).
    malicious_signals / benign_signals servent au verdict 3 états + confiance.
    """
    score = 0
    factors: list[str] = []
    mal = 0   # nombre de signaux pointant vers « malveillant »
    ben = 0   # nombre de signaux pointant vers « bénin »

    # --- AbuseIPDB : score de confiance communautaire -----------------------
    if ev.abuse_confidence >= 90:
        score += 40; mal += 2
        factors.append(f"Score AbuseIPDB très élevé : {ev.abuse_confidence}/100")
    elif ev.abuse_confidence >= 50:
        score += 25; mal += 1
        factors.append(f"Score AbuseIPDB élevé : {ev.abuse_confidence}/100")
    elif ev.abuse_confidence >= 20:
        score += 10
        factors.append(f"Score AbuseIPDB modéré : {ev.abuse_confidence}/100")
    elif ev.abuse_confidence == 0 and ev.abuse_total_reports == 0:
        ben += 1  # aucune réputation négative connue

    # --- Volume de signalements --------------------------------------------
    if ev.abuse_total_reports >= 100:
        score += 15; mal += 1
        factors.append(f"Signalée {ev.abuse_total_reports}× sur AbuseIPDB")
    elif ev.abuse_total_reports >= 10:
        score += 8
        factors.append(f"Signalée {ev.abuse_total_reports}× sur AbuseIPDB")

    # --- VirusTotal ---------------------------------------------------------
    if ev.vt_malicious >= 10:
        score += 25; mal += 2
        factors.append(f"Détectée malveillante par {ev.vt_malicious} moteurs VirusTotal")
    elif ev.vt_malicious >= 5:
        score += 20; mal += 1
        factors.append(f"Détectée malveillante par {ev.vt_malicious} moteurs VirusTotal")
    elif ev.vt_malicious >= 1:
        score += 10; mal += 1
        factors.append(f"Détectée par {ev.vt_malicious} moteur(s) VirusTotal")
    elif ev.vt_suspicious >= 3:
        score += 6
        factors.append(f"Marquée suspecte par {ev.vt_suspicious} moteur(s) VirusTotal")

    # --- Intensité de l'activité interne -----------------------------------
    intensity_pts = {"critical": 20, "high": 12, "medium": 7, "low": 3}
    score += intensity_pts.get(ev.attack_intensity, 0)
    if ev.attack_intensity in ("critical", "high"):
        mal += 1
        factors.append(
            f"Intensité {ev.attack_intensity.upper()} "
            f"({ev.attack_alert_count} alertes, {ev.attack_rpm} req/min)"
        )

    # --- Infrastructure suspecte -------------------------------------------
    if ev.is_tor:
        score += 10; mal += 1
        factors.append("Nœud de sortie Tor identifié")
    if ev.is_proxy:
        score += 10
        factors.append("IP identifiée comme proxy / VPN / anonymiseur")
    if ev.is_hosting:
        score += 5
        factors.append("IP hébergée en datacenter (VPS / cloud)")

    # --- Catégories dangereuses connues ------------------------------------
    matched = DANGER_CATS & set(ev.abuse_categories)
    if matched:
        score += 8; mal += 1
        factors.append(f"Catégories d'abus connues : {', '.join(sorted(matched))}")

    return min(score, 100), factors, mal, ben


def _level(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 55:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def _verdict_and_confidence(
    ev: Evidence, score: int, mal: int, ben: int
) -> tuple[str, int]:
    """
    Verdict 3 états + confiance, façon Qevlar :
      - malicious     : faisceau d'indices concordant et fort
      - benign        : signaux faibles + réputation propre
      - inconclusive  : signaux contradictoires ou données insuffisantes
    """
    strong_malicious = (
        score >= 70
        or ev.vt_malicious >= 3
        or ev.abuse_confidence >= 85
        or (ev.attack_intensity == "critical" and ev.abuse_confidence >= 40)
    )
    clearly_benign = (
        score < 25
        and ev.vt_malicious == 0
        and ev.abuse_confidence < 15
        and ev.attack_intensity in ("low", "medium")
        and not ev.is_tor
    )

    if strong_malicious:
        verdict = "malicious"
    elif clearly_benign:
        verdict = "benign"
    else:
        verdict = "inconclusive"

    # --- Confiance : combien de sources corroborent + à quel point ----------
    sources_seen = 0
    if ev.abuse_confidence or ev.abuse_total_reports:
        sources_seen += 1
    if ev.vt_malicious or ev.vt_suspicious:
        sources_seen += 1
    if ev.attack_alert_count:
        sources_seen += 1

    if verdict == "malicious":
        confidence = 40 + 15 * mal + 8 * sources_seen
    elif verdict == "benign":
        confidence = 45 + 10 * sources_seen + (10 if ev.attack_alert_count == 0 else 0)
    else:  # inconclusive — la confiance reflète le manque de consensus
        confidence = 25 + 6 * sources_seen
        # signaux opposés → on baisse encore
        if mal and ben:
            confidence = max(15, confidence - 15)

    return verdict, max(0, min(confidence, 100))


# ---------------------------------------------------------------------------
# Actions recommandées (dérivées du score / verdict)
# ---------------------------------------------------------------------------
def _recommended_actions(ev: Evidence, score: int, verdict: str) -> list[RecommendedAction]:
    actions: list[RecommendedAction] = []

    if score >= 50 or verdict == "malicious":
        actions.append(RecommendedAction(
            action="block_ip",
            label="🚫 Bloquer l'IP immédiatement",
            description="Ajouter à la liste noire Wazuh + règle iptables/nftables sur tous les hôtes",
            priority="high",
        ))
    if score >= 70 and ev.asn:
        actions.append(RecommendedAction(
            action="block_asn",
            label=f"🌐 Bloquer l'ASN entier ({ev.asn})",
            description=f"Toutes les IPs de {ev.asn_name or ev.isp} seront bloquées (attention aux faux positifs)",
            priority="medium",
        ))
    if ev.attack_type == "ddos":
        actions.append(RecommendedAction(
            action="rate_limit",
            label="⚡ Appliquer un rate limit agressif",
            description="Limiter à 10 req/s depuis cette IP (nginx limit_req ou iptables --hashlimit)",
            priority="high",
        ))
    if ev.attack_type == "bruteforce":
        actions.append(RecommendedAction(
            action="change_credentials",
            label="🔑 Vérifier les comptes ciblés",
            description=f"Services visés : {', '.join(ev.targeted_services or ['?'])} — auditer les logs d'accès",
            priority="high",
        ))
    if ev.abuse_confidence >= 30:
        actions.append(RecommendedAction(
            action="report_abuseipdb",
            label="📋 Signaler sur AbuseIPDB",
            description="Contribuer à la protection communautaire en soumettant un rapport",
            priority="low",
        ))
    if verdict == "inconclusive":
        actions.append(RecommendedAction(
            action="escalate",
            label="🧑‍💻 Escalader à un analyste",
            description="Verdict incertain — revue humaine recommandée avant toute action irréversible",
            priority="medium",
        ))
    actions.append(RecommendedAction(
        action="monitor",
        label="👁️ Surveillance renforcée 72h",
        description="Créer une règle d'alerte prioritaire pour cette IP et son sous-réseau /24",
        priority="low",
    ))
    return actions


# ---------------------------------------------------------------------------
# Point d'entrée public
# ---------------------------------------------------------------------------
def compute_verdict(ev: Evidence) -> RiskAssessment:
    """Calcule le verdict déterministe complet à partir des preuves agrégées."""
    score, factors, mal, ben = _score_and_factors(ev)
    verdict, confidence = _verdict_and_confidence(ev, score, mal, ben)
    return RiskAssessment(
        score=score,
        level=_level(score),
        verdict=verdict,
        confidence=confidence,
        factors=factors,
        recommended_actions=_recommended_actions(ev, score, verdict),
    )


def compute_risk_score(enrichment: dict) -> RiskAssessment:
    """
    Adaptateur pour le pipeline d'enrichissement temps réel (dictionnaires
    bruts AbuseIPDB / VirusTotal). Construit un `Evidence` minimal puis délègue
    à `compute_verdict` afin de conserver UN seul scorer.
    """
    abuse = enrichment.get("abuseipdb") or {}
    vt    = enrichment.get("virustotal") or {}
    ev = Evidence(
        abuse_confidence=int(abuse.get("abuse_score", 0) or 0),
        abuse_total_reports=int(abuse.get("reports", 0) or 0),
        is_tor=bool(abuse.get("is_tor", False)),
        vt_malicious=int(vt.get("malicious", 0) or 0),
        vt_suspicious=int(vt.get("suspicious", 0) or 0),
        isp=abuse.get("isp", "") or vt.get("as_owner", ""),
    )
    return compute_verdict(ev)
