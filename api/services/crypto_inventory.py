"""
SOC Platform — Inventaire cryptographique & posture post-quantique (CBOM)
=========================================================================

Inspiré de l'approche CryptoNext / « crypto-agility ». Deux capacités :

  1. AUTO-ÉVALUATION (`self_assessment`) — note la posture cryptographique
     déclarée de la plateforme elle-même (groupes TLS, signature du certificat,
     algorithme JWT, auth interne) face à la menace quantique. Déterministe,
     toujours disponible.

  2. CBOM OBSERVÉ (`build_cbom`) — agrège les handshakes TLS vus par Suricata
     dans OpenSearch et classe chaque session (vulnérable / hybride / sûre).
     Repli gracieux si OpenSearch est indisponible.

Modèle de menace :
  - Asymétrique (RSA, DH, ECDH, ECDSA, EdDSA) → cassé par Shor → VULNÉRABLE.
  - KEM/signatures réseau (ML-KEM/Kyber, ML-DSA/Dilithium, Falcon, SLH-DSA) → SÛR.
  - Symétrique (AES-256, ChaCha20) → Grover ne fait que ½ → SÛR ; AES-128 → FAIBLE.
  - Hachage : SHA-384/512/SHA-3 → SÛR ; SHA-256 → ACCEPTABLE ; SHA-1/MD5 → CASSÉ.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel

from api.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Modèles de sortie
# ---------------------------------------------------------------------------
class CryptoComponent(BaseModel):
    name:       str                    # ex. "TLS key exchange"
    value:      str                    # ex. "X25519MLKEM768"
    kind:       str                    # kex | signature | symmetric | hash | token
    status:     str                    # safe | hybrid | weak | vulnerable | broken | unknown
    severity:   str                    # none | low | medium | high | critical
    note:       str = ""


class ReadinessReport(BaseModel):
    timestamp:        str
    readiness_score:  int                       # 0-100 (100 = full PQC)
    grade:            str                        # A..F
    components:       list[CryptoComponent] = []
    summary:          str = ""


class CbomReport(BaseModel):
    timestamp:        str
    period_hours:     int
    sessions_seen:    int = 0
    quantum_safe:     int = 0
    hybrid:           int = 0
    vulnerable:       int = 0
    by_tls_version:   dict[str, int] = {}
    components:       list[CryptoComponent] = []
    source:           str = "opensearch"        # opensearch | unavailable


# ---------------------------------------------------------------------------
# Classifieurs déterministes
# ---------------------------------------------------------------------------
_PQC_KEX   = ("mlkem", "ml-kem", "kyber", "frodo", "bike", "hqc")
_PQC_SIG   = ("mldsa", "ml-dsa", "dilithium", "falcon", "sphincs", "slhdsa", "slh-dsa")
_CLASSICAL_KEX = ("x25519", "x448", "ecdh", "ecdhe", "secp", "prime256", "dh", "ffdhe", "rsa")
_CLASSICAL_SIG = ("rsa", "ecdsa", "ed25519", "ed448", "dsa")


def classify_kex(name: str) -> CryptoComponent:
    n = (name or "").lower().replace("_", "").replace("-", "")
    is_pqc      = any(k.replace("-", "") in n for k in _PQC_KEX)
    is_classical = any(k.replace("-", "") in n for k in _CLASSICAL_KEX)
    if is_pqc and is_classical:
        return CryptoComponent(name="Échange de clés TLS", value=name, kind="kex",
                               status="hybrid", severity="none",
                               note="Hybride classique+PQC (ML-KEM) — résistant à « harvest-now, decrypt-later ».")
    if is_pqc:
        return CryptoComponent(name="Échange de clés TLS", value=name, kind="kex",
                               status="safe", severity="none", note="KEM post-quantique pur.")
    if is_classical:
        return CryptoComponent(name="Échange de clés TLS", value=name, kind="kex",
                               status="vulnerable", severity="high",
                               note="Échange asymétrique classique — cassable par Shor (capture puis déchiffrement différé).")
    return CryptoComponent(name="Échange de clés TLS", value=name or "?", kind="kex",
                           status="unknown", severity="medium")


def classify_signature(name: str) -> CryptoComponent:
    n = (name or "").lower().replace("_", "").replace("-", "")
    if any(s.replace("-", "") in n for s in _PQC_SIG):
        return CryptoComponent(name="Signature", value=name, kind="signature",
                               status="safe", severity="none", note="Signature post-quantique (FIPS 204/205).")
    if any(s in n for s in ("rsa", "ecdsa", "dsa", "ed25519", "ed448")):
        sev = "high" if "rsa" in n or "ecdsa" in n else "medium"
        return CryptoComponent(name="Signature", value=name, kind="signature",
                               status="vulnerable", severity=sev,
                               note="Signature asymétrique classique — cassable par Shor.")
    return CryptoComponent(name="Signature", value=name or "?", kind="signature",
                           status="unknown", severity="medium")


def classify_symmetric(name: str) -> CryptoComponent:
    n = (name or "").lower()
    if "aes256" in n.replace("-", "").replace("_", "") or "chacha20" in n:
        return CryptoComponent(name="Chiffrement symétrique", value=name, kind="symmetric",
                               status="safe", severity="none",
                               note="≥256 bits — Grover ne réduit la sécurité que de moitié, reste robuste.")
    if "aes128" in n.replace("-", "").replace("_", ""):
        return CryptoComponent(name="Chiffrement symétrique", value=name, kind="symmetric",
                               status="weak", severity="low",
                               note="AES-128 → ~64 bits face à Grover ; privilégier AES-256.")
    if "3des" in n or "rc4" in n or "des" in n:
        return CryptoComponent(name="Chiffrement symétrique", value=name, kind="symmetric",
                               status="broken", severity="critical", note="Algorithme obsolète.")
    return CryptoComponent(name="Chiffrement symétrique", value=name or "?", kind="symmetric",
                           status="unknown", severity="low")


def classify_hash(name: str) -> CryptoComponent:
    n = (name or "").lower().replace("-", "").replace("_", "")
    if any(h in n for h in ("sha384", "sha512", "sha3")):
        return CryptoComponent(name="Hachage", value=name, kind="hash",
                               status="safe", severity="none")
    if "sha256" in n:
        return CryptoComponent(name="Hachage", value=name, kind="hash",
                               status="safe", severity="low", note="SHA-256 acceptable post-quantique.")
    if "sha1" in n or "md5" in n:
        return CryptoComponent(name="Hachage", value=name, kind="hash",
                               status="broken", severity="critical", note="Collision pratique — à bannir.")
    return CryptoComponent(name="Hachage", value=name or "?", kind="hash",
                           status="unknown", severity="low")


# ---------------------------------------------------------------------------
# Score de readiness
# ---------------------------------------------------------------------------
_STATUS_WEIGHT = {
    "safe": 100, "hybrid": 90, "unknown": 50, "weak": 40,
    "vulnerable": 20, "broken": 0,
}


def _grade(score: int) -> str:
    if score >= 90: return "A"
    if score >= 75: return "B"
    if score >= 60: return "C"
    if score >= 45: return "D"
    if score >= 25: return "E"
    return "F"


def _score_components(components: list[CryptoComponent]) -> int:
    if not components:
        return 0
    return round(sum(_STATUS_WEIGHT.get(c.status, 50) for c in components) / len(components))


# ---------------------------------------------------------------------------
# 1. Auto-évaluation de la posture déclarée
# ---------------------------------------------------------------------------
def self_assessment() -> ReadinessReport:
    """Évalue la cryptographie déclarée de la plateforme Argus elle-même."""
    tls_groups = getattr(settings, "TLS_GROUPS", "X25519MLKEM768:X25519:secp256r1")
    first_group = tls_groups.split(":")[0] if tls_groups else ""
    pqc_jwt    = bool(getattr(settings, "PQC_JWT", False))
    jwt_alg    = getattr(settings, "JWT_ALGORITHM", "HS256")

    components: list[CryptoComponent] = []

    # Transport — groupe TLS négocié en priorité (edge nginx / pqc-proxy)
    components.append(classify_kex(first_group))

    # Certificat serveur (généré par scripts/generate_certs.sh — RSA par défaut)
    cert_sig = getattr(settings, "TLS_CERT_SIG", "RSA-4096")
    components.append(classify_signature(cert_sig))

    # Suite symétrique TLS de référence
    components.append(classify_symmetric("AES-256-GCM"))
    components.append(classify_hash("SHA-384"))

    # Jeton d'authentification (JWT)
    if pqc_jwt:
        components.append(CryptoComponent(
            name="Signature des jetons (JWT)", value="Ed25519 + ML-DSA-65 (hybride)",
            kind="token", status="hybrid", severity="none",
            note="JWT signé en hybride post-quantique."))
    elif str(jwt_alg).upper().startswith("HS"):
        components.append(CryptoComponent(
            name="Signature des jetons (JWT)", value=str(jwt_alg), kind="token",
            status="safe", severity="low",
            note="HMAC symétrique : résistant au quantique, mais non vérifiable publiquement. "
                 "Activer PQC_JWT pour des signatures asymétriques post-quantiques."))
    else:
        components.append(classify_signature(str(jwt_alg)))

    score = _score_components(components)
    n_vuln = sum(1 for c in components if c.status in ("vulnerable", "broken"))
    summary = (
        f"Posture cryptographique : {score}/100 (note {_grade(score)}). "
        f"{n_vuln} composant(s) vulnérable(s) au quantique sur {len(components)}. "
        + ("Transport déjà hybride PQC. " if components[0].status in ("hybrid", "safe")
           else "Transport encore classique — activer les groupes hybrides ML-KEM. ")
        + ("Certificat à migrer vers ML-DSA." if components[1].status == "vulnerable" else "")
    )

    return ReadinessReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        readiness_score=score,
        grade=_grade(score),
        components=components,
        summary=summary.strip(),
    )


# ---------------------------------------------------------------------------
# 2. CBOM observé depuis OpenSearch (handshakes TLS vus par Suricata)
# ---------------------------------------------------------------------------
async def build_cbom(period_hours: int = 24) -> CbomReport:
    """Agrège les versions/handshakes TLS observés. Repli gracieux si OS down."""
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    base = CbomReport(
        timestamp=now.isoformat(),
        period_hours=period_hours,
    )

    try:
        from api.services.opensearch import OpenSearchClient
        client = await OpenSearchClient().get_client()
        since = (now - timedelta(hours=period_hours)).isoformat()
        resp = await client.search(
            index=settings.OPENSEARCH_INDEX_SURICATA,
            body={
                "size": 0,
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"event_type": "tls"}},
                            {"range": {"timestamp": {"gte": since}}},
                        ]
                    }
                },
                "aggs": {
                    "versions": {"terms": {"field": "tls.version.keyword", "size": 12}},
                    "ciphers":  {"terms": {"field": "tls.cipher_suite.keyword", "size": 20}},
                },
            },
        )
    except Exception as e:
        logger.info("CBOM : OpenSearch indisponible (%s) — auto-évaluation seule", e)
        base.source = "unavailable"
        return base

    aggs = resp.get("aggregations", {})
    by_version: dict[str, int] = {}
    total = 0
    for bucket in aggs.get("versions", {}).get("buckets", []):
        ver = bucket.get("key", "?")
        cnt = bucket.get("doc_count", 0)
        by_version[ver] = cnt
        total += cnt

    safe = hybrid = vuln = 0
    components: list[CryptoComponent] = []
    for bucket in aggs.get("ciphers", {}).get("buckets", []):
        comp = classify_kex(bucket.get("key", ""))
        components.append(comp)
        c = bucket.get("doc_count", 0)
        if comp.status == "hybrid":
            hybrid += c
        elif comp.status == "safe":
            safe += c
        elif comp.status in ("vulnerable", "broken", "weak"):
            vuln += c

    base.sessions_seen = total
    base.quantum_safe  = safe
    base.hybrid        = hybrid
    base.vulnerable    = vuln
    base.by_tls_version = by_version
    base.components    = components[:30]
    return base
