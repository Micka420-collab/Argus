"""
SOC Platform — Signature de jetons hybride post-quantique (pilier CryptoNext)
=============================================================================

Jetons d'authentification signés en **hybride** :
  - **Ed25519** (classique, rapide, toujours présent) — dérivé de SECRET_KEY de
    façon déterministe (stable entre redémarrages tant que SECRET_KEY l'est →
    corrige le bug « clé aléatoire par process »).
  - **ML-DSA-65 / Dilithium3** (post-quantique, FIPS 204) — ajouté si `liboqs`
    (paquet `oqs`) est disponible ; clé persistée dans `PQC_KEYS_DIR`.

Format de jeton compact, façon JWS detached, en 3 ou 4 segments base64url :

    b64(header).b64(payload).b64(ed25519_sig)[.b64(mldsa_sig)]

La vérification exige Ed25519 valide ; ML-DSA est vérifié en plus s'il est
présent ET que la clé publique PQC est disponible. Aucune dépendance native
n'est requise pour le chemin Ed25519 (lib `cryptography` déjà présente).
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature

from api.core.config import settings

logger = logging.getLogger(__name__)

# --- ML-DSA optionnel (liboqs) ---------------------------------------------
try:
    import oqs  # type: ignore
    _HAVE_OQS = True
except Exception:  # ImportError ou lib native absente
    _HAVE_OQS = False

_OQS_ALG_CANDIDATES = ("ML-DSA-65", "Dilithium3")


# ---------------------------------------------------------------------------
# Helpers base64url
# ---------------------------------------------------------------------------
def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ---------------------------------------------------------------------------
# Gestion des clés (singletons par process, mais déterministes)
# ---------------------------------------------------------------------------
_ed_priv: Ed25519PrivateKey | None = None
_ed_pub: Ed25519PublicKey | None = None
_mldsa = None            # objet oqs.Signature (détient la clé privée)
_mldsa_pub: bytes | None = None
_mldsa_alg: str | None = None


def _ed_seed() -> bytes:
    """Graine Ed25519 déterministe (32 octets) dérivée de SECRET_KEY."""
    return hashlib.sha256(b"argus-ed25519-jwt-v1|" + settings.SECRET_KEY.encode()).digest()


def _ensure_ed() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    global _ed_priv, _ed_pub
    if _ed_priv is None:
        _ed_priv = Ed25519PrivateKey.from_private_bytes(_ed_seed())
        _ed_pub = _ed_priv.public_key()
    return _ed_priv, _ed_pub


def _keys_dir() -> str:
    return getattr(settings, "PQC_KEYS_DIR", "") or "/var/lib/argus/pqc"


def _ensure_mldsa():
    """Initialise ML-DSA si liboqs présent ; persiste la clé secrète. Best-effort."""
    global _mldsa, _mldsa_pub, _mldsa_alg
    if not _HAVE_OQS or _mldsa is not None:
        return
    alg = next((a for a in _OQS_ALG_CANDIDATES if a in oqs.get_enabled_sig_mechanisms()), None)
    if not alg:
        return
    try:
        d = _keys_dir()
        os.makedirs(d, exist_ok=True)
        sk_path = os.path.join(d, f"{alg}.sk")
        pk_path = os.path.join(d, f"{alg}.pk")
        if os.path.exists(sk_path) and os.path.exists(pk_path):
            with open(sk_path, "rb") as f:
                secret_key = f.read()
            with open(pk_path, "rb") as f:
                _mldsa_pub = f.read()
            _mldsa = oqs.Signature(alg, secret_key)
        else:
            _mldsa = oqs.Signature(alg)
            _mldsa_pub = _mldsa.generate_keypair()
            with open(sk_path, "wb") as f:
                f.write(_mldsa.export_secret_key())
            with open(pk_path, "wb") as f:
                f.write(_mldsa_pub)
            os.chmod(sk_path, 0o600)
        _mldsa_alg = alg
        logger.info("JWT post-quantique : ML-DSA actif (%s)", alg)
    except Exception as e:
        logger.warning("ML-DSA indisponible (%s) — JWT Ed25519 seul", e)
        _mldsa, _mldsa_pub, _mldsa_alg = None, None, None


def active_algorithm() -> str:
    _ensure_ed()
    _ensure_mldsa()
    return f"Ed25519+{_mldsa_alg}" if _mldsa_alg else "Ed25519"


def public_keys() -> dict:
    """Clés publiques (pour transparence / vérification externe éventuelle)."""
    _ensure_ed()
    _ensure_mldsa()
    from cryptography.hazmat.primitives import serialization
    ed_raw = _ed_pub.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    out = {"algorithm": active_algorithm(), "ed25519_public": _b64u(ed_raw)}
    if _mldsa_pub:
        out["mldsa_public"] = _b64u(_mldsa_pub)
        out["mldsa_alg"] = _mldsa_alg
    return out


# ---------------------------------------------------------------------------
# Création / vérification de jetons
# ---------------------------------------------------------------------------
def create_token(payload: dict, expires: timedelta, token_type: str) -> str:
    ed_priv, _ = _ensure_ed()
    _ensure_mldsa()

    header = {"alg": active_algorithm(), "typ": "JWT+PQ"}
    body = dict(payload)
    body["type"] = token_type
    body["exp"] = int((datetime.now(timezone.utc) + expires).timestamp())

    seg_h = _b64u(json.dumps(header, separators=(",", ":"), sort_keys=True).encode())
    seg_b = _b64u(json.dumps(body, separators=(",", ":"), sort_keys=True).encode())
    signing_input = f"{seg_h}.{seg_b}".encode("ascii")

    parts = [seg_h, seg_b, _b64u(ed_priv.sign(signing_input))]
    if _mldsa is not None:
        try:
            parts.append(_b64u(_mldsa.sign(signing_input)))
        except Exception as e:
            logger.warning("Signature ML-DSA échouée (%s) — jeton Ed25519 seul", e)
    return ".".join(parts)


def decode_token(token: str) -> dict:
    """Vérifie le jeton hybride et renvoie le payload. Lève ValueError si invalide."""
    segs = token.split(".")
    if len(segs) < 3:
        raise ValueError("Format de jeton invalide")
    seg_h, seg_b, seg_ed = segs[0], segs[1], segs[2]
    signing_input = f"{seg_h}.{seg_b}".encode("ascii")

    # 1) Ed25519 obligatoire
    _, ed_pub = _ensure_ed()
    try:
        ed_pub.verify(_b64u_dec(seg_ed), signing_input)
    except InvalidSignature:
        raise ValueError("Signature Ed25519 invalide")

    # 2) ML-DSA si présent et clé dispo
    if len(segs) >= 4:
        _ensure_mldsa()
        if _mldsa is not None and _mldsa_pub is not None:
            try:
                if not _mldsa.verify(signing_input, _b64u_dec(segs[3]), _mldsa_pub):
                    raise ValueError("Signature ML-DSA invalide")
            except ValueError:
                raise
            except Exception as e:
                logger.warning("Vérification ML-DSA ignorée (%s)", e)

    payload = json.loads(_b64u_dec(seg_b))
    exp = payload.get("exp", 0)
    if exp and datetime.now(timezone.utc).timestamp() > exp:
        raise ValueError("Jeton expiré")
    return payload
