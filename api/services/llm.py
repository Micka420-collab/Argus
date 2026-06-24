"""
SOC Platform — Adaptateur LLM borné (« bounded LLM »)
=====================================================

Principe (cœur de l'approche Qevlar) : le LLM ne décide JAMAIS si une IP est
malveillante. Le verdict est calculé de façon déterministe par
`services.scoring.compute_verdict`. Le LLM est strictement borné à :
  - rédiger un résumé / récit d'investigation lisible
  - proposer des actions de remédiation en langage naturel

Backends interchangeables (`LLM_PROVIDER`) :
  - "ollama" : modèle local auto-hébergé (par défaut, données résidentes / air-gap)
  - "claude" : API Anthropic (qualité maximale)
  - "none"   : repli heuristique déterministe (aucune dépendance, marche toujours)

Tous les imports tiers sont paresseux : la plateforme démarre même si
`anthropic` / `instructor` ne sont pas installés.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel

from api.core.config import settings

logger = logging.getLogger(__name__)


class AiAnalysis(BaseModel):
    summary: str = ""                       # 1-2 phrases
    narrative: str = ""                     # récit d'investigation
    recommended_actions: list[str] = []     # remédiation en langage naturel
    generated_by: str = "heuristic"         # ollama:<model> | claude:<model> | heuristic


_SYSTEM_PROMPT = (
    "Tu es un analyste SOC senior. On te fournit les preuves structurées d'une "
    "investigation OSINT sur une adresse IP ET un verdict DÉJÀ calculé de manière "
    "déterministe. Ta mission est UNIQUEMENT de rédiger une analyse claire en "
    "français : un résumé, un récit d'investigation factuel, et des actions de "
    "remédiation concrètes. NE change JAMAIS le verdict ni le score fournis — "
    "tu les expliques, tu ne les recalcules pas. Réponds STRICTEMENT en JSON avec "
    "les clés : summary (string), narrative (string), recommended_actions (array de strings)."
)


def _build_user_prompt(ctx: dict[str, Any]) -> str:
    return (
        "Preuves de l'investigation (JSON) :\n"
        f"{json.dumps(ctx, ensure_ascii=False, indent=2)}\n\n"
        "Rédige l'analyse. Sois factuel, concis, et oriente l'analyste vers la "
        "prochaine action utile. Format de sortie : JSON uniquement."
    )


# ---------------------------------------------------------------------------
# Repli heuristique — toujours disponible, zéro dépendance
# ---------------------------------------------------------------------------
def _heuristic(ctx: dict[str, Any]) -> AiAnalysis:
    ip       = ctx.get("ip", "?")
    verdict  = ctx.get("verdict", "inconclusive")
    score    = ctx.get("score", 0)
    conf     = ctx.get("confidence", 0)
    geo      = ctx.get("geo", {}) or {}
    profile  = ctx.get("attack_profile", {}) or {}
    factors  = ctx.get("factors", []) or []
    actions  = ctx.get("recommended_actions", []) or []

    verdict_fr = {
        "malicious": "MALVEILLANTE", "benign": "BÉNIGNE", "inconclusive": "INDÉTERMINÉE",
    }.get(verdict, verdict.upper())

    loc = ", ".join(x for x in [geo.get("city"), geo.get("country")] if x) or "localisation inconnue"
    isp = geo.get("isp") or geo.get("org") or "FAI inconnu"

    summary = (
        f"L'IP {ip} est jugée {verdict_fr} (score {score}/100, confiance {conf}%). "
        f"Origine : {loc} via {isp}."
    )

    narrative_parts = [
        f"L'adresse {ip} a été analysée à partir de sources OSINT multiples (AbuseIPDB, "
        f"VirusTotal, RDAP) et de l'historique d'alertes internes.",
    ]
    if profile.get("alert_count"):
        narrative_parts.append(
            f"Elle est associée à {profile.get('alert_count')} alerte(s) internes "
            f"de type « {profile.get('type', 'inconnu')} » (intensité "
            f"{profile.get('intensity', 'low')})."
        )
    if factors:
        narrative_parts.append("Facteurs de risque retenus : " + " ; ".join(factors[:6]) + ".")
    if verdict == "inconclusive":
        narrative_parts.append(
            "Les signaux sont insuffisants ou contradictoires : une revue humaine "
            "est recommandée avant toute action irréversible."
        )

    rec = [a.get("label", "") if isinstance(a, dict) else str(a) for a in actions]
    rec = [r for r in rec if r][:6]

    return AiAnalysis(
        summary=summary,
        narrative=" ".join(narrative_parts),
        recommended_actions=rec,
        generated_by="heuristic",
    )


def _parse_json_block(text: str) -> dict | None:
    """Extrait le premier objet JSON d'une réponse LLM (robuste au bavardage)."""
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Backend Ollama (local, http://ollama:11434)
# ---------------------------------------------------------------------------
async def _ollama(ctx: dict[str, Any]) -> AiAnalysis | None:
    base  = settings.LLM_BASE_URL.rstrip("/")
    model = settings.LLM_MODEL or "qwen2.5:7b"
    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            r = await client.post(
                f"{base}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user",   "content": _build_user_prompt(ctx)},
                    ],
                    "stream": False,
                    "format": "json",
                    "keep_alive": settings.LLM_KEEP_ALIVE,
                    "options": {"temperature": 0.2},
                },
            )
            r.raise_for_status()
            content = r.json().get("message", {}).get("content", "")
    except Exception as e:
        logger.warning("LLM Ollama indisponible (%s) — repli heuristique", e)
        return None

    data = _parse_json_block(content)
    if not data:
        return None
    return AiAnalysis(
        summary=str(data.get("summary", ""))[:600],
        narrative=str(data.get("narrative", ""))[:4000],
        recommended_actions=[str(a) for a in (data.get("recommended_actions") or [])][:8],
        generated_by=f"ollama:{model}",
    )


# ---------------------------------------------------------------------------
# Backend Claude (Anthropic API)
# ---------------------------------------------------------------------------
async def _claude(ctx: dict[str, Any]) -> AiAnalysis | None:
    if not settings.ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic  # import paresseux
    except ImportError:
        logger.warning("Paquet `anthropic` non installé — repli heuristique")
        return None

    model = settings.LLM_MODEL or "claude-sonnet-4-6"
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        msg = await client.messages.create(
            model=model,
            max_tokens=1024,
            temperature=0.2,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_prompt(ctx)}],
        )
        text = "".join(
            block.text for block in msg.content if getattr(block, "type", "") == "text"
        )
    except Exception as e:
        logger.warning("LLM Claude indisponible (%s) — repli heuristique", e)
        return None

    data = _parse_json_block(text)
    if not data:
        return None
    return AiAnalysis(
        summary=str(data.get("summary", ""))[:600],
        narrative=str(data.get("narrative", ""))[:4000],
        recommended_actions=[str(a) for a in (data.get("recommended_actions") or [])][:8],
        generated_by=f"claude:{model}",
    )


# ---------------------------------------------------------------------------
# Point d'entrée public
# ---------------------------------------------------------------------------
async def complete(system_prompt: str, user_prompt: str) -> str:
    """
    Complétion texte générique bornée (réutilisée par le triage VDP, etc.).
    Renvoie "" si aucun LLM n'est configuré/disponible (repli silencieux).
    """
    provider = (settings.LLM_PROVIDER or "none").lower()
    try:
        if provider == "ollama":
            base = settings.LLM_BASE_URL.rstrip("/")
            model = settings.LLM_MODEL or "qwen2.5:7b"
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
                r = await client.post(
                    f"{base}/api/chat",
                    json={"model": model, "stream": False,
                          "keep_alive": settings.LLM_KEEP_ALIVE,
                          "options": {"temperature": 0.2},
                          "messages": [{"role": "system", "content": system_prompt},
                                       {"role": "user", "content": user_prompt}]},
                )
                r.raise_for_status()
                return r.json().get("message", {}).get("content", "").strip()
        if provider == "claude" and settings.ANTHROPIC_API_KEY:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            msg = await client.messages.create(
                model=settings.LLM_MODEL or "claude-sonnet-4-6",
                max_tokens=512, temperature=0.2, system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    except Exception as e:
        logger.warning("llm.complete indisponible (%s)", e)
    return ""


async def analyze(ctx: dict[str, Any]) -> AiAnalysis:
    """
    Produit une analyse rédigée. Le contexte `ctx` doit contenir au minimum :
    ip, verdict, score, confidence, factors, geo, attack_profile,
    recommended_actions. Garantit TOUJOURS un résultat (repli heuristique).
    """
    provider = (settings.LLM_PROVIDER or "none").lower()
    result: AiAnalysis | None = None

    if provider == "ollama":
        result = await _ollama(ctx)
    elif provider == "claude":
        result = await _claude(ctx)

    return result or _heuristic(ctx)
