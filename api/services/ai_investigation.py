"""
SOC Platform — Agent d'investigation autonome (pilier Qevlar)
=============================================================

Agent qui investigue une alerte de bout en bout, façon Qevlar, via un
**graphe déterministe typé** (style LangGraph) — sans dépendance lourde :
chaque nœud est une coroutine `(state) -> None` qui enrichit l'état partagé et
journalise une entrée de trace (auditable & rejouable).

    ingest → enrich(OSINT) → correlate(OpenSearch) → retrieve_feedback(RAG)
           → score(déterministe) → decide → report(LLM borné)
           → propose_actions(human-gated) → persist → escalate

Principe Qevlar respecté : **le verdict est calculé en Python** (services.scoring) ;
le **LLM est borné** au récit. Les actions destructrices ne sont JAMAIS exécutées
automatiquement — elles sont proposées avec `requires_confirmation=True`.

Le rapport (état final + trace) est persisté dans OpenSearch `soc-investigations`.
"""
from __future__ import annotations

import ipaddress
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Awaitable, Callable

from api.core.config import settings
from api.services.opensearch import OpenSearchClient
from api.services.investigation import InvestigationService
from api.services.scoring import Evidence, RiskAssessment, compute_verdict
from api.services.llm import analyze as llm_analyze
from api.services import feedback as feedback_svc

logger = logging.getLogger(__name__)

AI_INDEX = settings.OPENSEARCH_INDEX_AI


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
class AiInvestigationAgent:
    """Orchestrateur de graphe d'investigation autonome."""

    def __init__(self) -> None:
        self.osint = InvestigationService()
        self.os = OpenSearchClient()

    # ------------------------------------------------------------------
    # Runner du graphe
    # ------------------------------------------------------------------
    async def run(self, alert: dict, *, source: str = "auto") -> dict:
        now = datetime.now(timezone.utc)
        state: dict[str, Any] = {
            "id": uuid.uuid4().hex[:16],
            "source": source,                 # auto | manual
            "created_at": now.isoformat(),
            "status": "running",
            "alert": alert,
            "trace": [],
        }

        # Graphe : (nom, coroutine). L'ordre EST le DAG.
        graph: list[tuple[str, Callable[[dict], Awaitable[None]]]] = [
            ("ingest",          self._ingest),
            ("enrich",          self._enrich),
            ("correlate",       self._correlate),
            ("retrieve_feedback", self._retrieve_feedback),
            ("score",           self._score),
            ("decide",          self._decide),
            ("report",          self._report),
            ("propose_actions", self._propose_actions),
            ("persist",         self._persist),
            ("escalate",        self._escalate),
        ]

        for name, node in graph:
            t0 = datetime.now(timezone.utc)
            try:
                await node(state)
                self._trace(state, name, "ok", t0)
            except Exception as e:  # un nœud qui échoue ne casse pas l'investigation
                logger.warning("Nœud IA '%s' échoué: %s", name, e)
                self._trace(state, name, "error", t0, str(e))

        state["status"] = "completed"
        state["finished_at"] = datetime.now(timezone.utc).isoformat()
        return state

    def _trace(self, state: dict, node: str, status: str, t0: datetime, detail: str = "") -> None:
        ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
        state["trace"].append({"node": node, "status": status, "ms": ms, "detail": detail})

    # ------------------------------------------------------------------
    # Nœuds du graphe
    # ------------------------------------------------------------------
    async def _ingest(self, state: dict) -> None:
        alert = state["alert"]
        rule  = alert.get("rule", {}) or {}
        agent = alert.get("agent", {}) or {}
        ip    = alert.get("data", {}).get("srcip") or alert.get("src_ip") or ""
        state["ip"] = ip
        state["alert_meta"] = {
            "alert_id":   alert.get("id", ""),
            "rule_id":    rule.get("id", ""),
            "rule_desc":  rule.get("description", ""),
            "level":      rule.get("level", 0),
            "mitre":      (rule.get("mitre", {}) or {}).get("id", []),
            "agent_name": agent.get("name", ""),
            "agent_ip":   agent.get("ip", ""),
            "src_ip":     ip,
        }

    async def _enrich(self, state: dict) -> None:
        ip = state.get("ip")
        state["osint"] = None
        if not ip:
            return
        try:
            addr = ipaddress.ip_address(ip)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                state["osint_skipped"] = "ip_privee"
                return
        except ValueError:
            state["osint_skipped"] = "ip_invalide"
            return
        # with_ai=False : l'agent rédige lui-même le récit (nœud _report).
        # Évite un second appel LLM coûteux dans InvestigationService.
        report = await self.osint.investigate(ip, with_ai=False)
        state["osint"] = report.model_dump()

    async def _correlate(self, state: dict) -> None:
        ip = state.get("ip")
        corr = {"related_count": 0, "distinct_agents": 0, "subnet_count": 0,
                "beaconing": False, "window_days": 7}
        state["correlation"] = corr
        if not ip:
            return
        try:
            client = await self.os.get_client()
            since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            subnet_prefix = ".".join(ip.split(".")[:3]) + "." if "." in ip else ip
            resp = await client.search(
                index=settings.OPENSEARCH_INDEX_ALERTS,
                body={
                    "size": 0,
                    "query": {"bool": {"filter": [{"range": {"timestamp": {"gte": since}}}],
                                       "should": [
                                           {"term": {"data.srcip": ip}},
                                           {"prefix": {"data.srcip": subnet_prefix}},
                                       ], "minimum_should_match": 1}},
                    "aggs": {
                        "agents": {"cardinality": {"field": "agent.name.keyword"}},
                        "subnet": {"value_count": {"field": "data.srcip.keyword"}},
                        "over_time": {"date_histogram": {"field": "timestamp", "fixed_interval": "1h"}},
                    },
                },
            )
            aggs = resp.get("aggregations", {})
            total = resp.get("hits", {}).get("total", {}).get("value", 0)
            buckets = [b.get("doc_count", 0) for b in aggs.get("over_time", {}).get("buckets", [])]
            active = [c for c in buckets if c > 0]
            # Beaconing heuristique : activité étalée et régulière sur de nombreuses heures
            beaconing = len(active) >= 6 and (sum(active) / len(active)) >= 2
            corr.update({
                "related_count":   total,
                "distinct_agents": aggs.get("agents", {}).get("value", 0),
                "subnet_count":    aggs.get("subnet", {}).get("value", 0),
                "beaconing":       bool(beaconing),
            })
        except Exception as e:
            logger.debug("Corrélation indisponible (%s)", e)

    async def _retrieve_feedback(self, state: dict) -> None:
        ip = state.get("ip", "")
        osint = state.get("osint") or {}
        attack_type = (osint.get("attack_profile") or {}).get("type", "unknown")
        asn = (osint.get("geo") or {}).get("asn", "")
        state["feedback"] = await feedback_svc.retrieve_context(ip, attack_type, asn)

    async def _score(self, state: dict) -> None:
        osint = state.get("osint") or {}
        corr  = state.get("correlation") or {}
        meta  = state.get("alert_meta") or {}

        if osint:
            geo     = osint.get("geo", {}) or {}
            abuse   = osint.get("abuse", {}) or {}
            vt      = osint.get("virustotal", {}) or {}
            profile = osint.get("attack_profile", {}) or {}
            intensity = profile.get("intensity", "low")
            # La corrélation renforce l'intensité
            if corr.get("beaconing"):
                intensity = "critical"
            elif corr.get("related_count", 0) >= 100 and intensity in ("low", "medium"):
                intensity = "high"
            ev = Evidence(
                abuse_confidence=abuse.get("confidence_score", 0),
                abuse_total_reports=abuse.get("total_reports", 0),
                abuse_categories=abuse.get("categories", []),
                vt_malicious=vt.get("malicious", 0),
                vt_suspicious=vt.get("suspicious", 0),
                attack_type=profile.get("type", "unknown"),
                attack_intensity=intensity,
                attack_alert_count=max(profile.get("alert_count", 0), corr.get("related_count", 0)),
                attack_rpm=profile.get("requests_per_minute", 0.0),
                targeted_services=profile.get("targeted_services", []),
                is_proxy=geo.get("is_proxy", False),
                is_hosting=geo.get("is_hosting", False),
                asn=geo.get("asn", ""),
                asn_name=geo.get("asn_name", ""),
                isp=geo.get("isp", ""),
            )
            assessment = compute_verdict(ev)
        else:
            # Alerte basée hôte (pas d'IP publique) : verdict prudent depuis le niveau
            level = meta.get("level", 0)
            score = min(100, level * 6)
            assessment = RiskAssessment(
                score=score,
                level="high" if level >= 12 else "medium" if level >= 8 else "low",
                verdict="inconclusive",
                confidence=35,
                factors=[f"Alerte hôte niveau {level}/15 sans IP publique — OSINT non applicable"],
                recommended_actions=[],
            )

        # Signaux de corrélation explicites dans les facteurs
        if corr.get("beaconing"):
            assessment.factors.append("Comportement de beaconing/C2 régulier détecté (corrélation)")
        if corr.get("related_count", 0) >= 50:
            assessment.factors.append(
                f"{corr['related_count']} alertes liées sur 7j "
                f"({corr.get('distinct_agents', 0)} machines)"
            )

        # Ajustement par feedback analyste (RAG)
        fb = state.get("feedback") or []
        if fb:
            exact = [f for f in fb if f.get("corrected_verdict")]
            if exact:
                last = exact[0]
                assessment.factors.append(
                    f"Décision analyste passée ({last['match']}) : "
                    f"« {last['corrected_verdict']} » — {last.get('rationale','')[:120]}"
                )
                # Un acquittement bénin antérieur sur la même IP tempère le verdict
                if last["corrected_verdict"] == "benign" and assessment.verdict == "malicious":
                    assessment.verdict = "inconclusive"
                    assessment.confidence = max(20, assessment.confidence - 25)

        state["verdict"] = assessment.model_dump()

    async def _decide(self, state: dict) -> None:
        state["decision"] = (state.get("verdict") or {}).get("verdict", "inconclusive")

    async def _report(self, state: dict) -> None:
        osint   = state.get("osint") or {}
        verdict = state.get("verdict") or {}
        geo_all = osint.get("geo", {}) or {}
        corr    = state.get("correlation", {}) or {}
        # Contexte VOLONTAIREMENT compact : un LLM local en CPU évalue le prompt
        # token par token. On ne transmet que l'essentiel — les gros blobs
        # (alerte brute, corrélation complète, feedback) ralentissent fortement
        # l'inférence sans améliorer la rédaction. Le verdict reste déterministe.
        geo = {k: geo_all[k] for k in ("city", "country", "isp", "org", "asn_name")
               if geo_all.get(k)}
        actions = [a.get("label") if isinstance(a, dict) else str(a)
                   for a in (verdict.get("recommended_actions") or [])]
        actions = [a for a in actions if a][:5]
        ctx = {
            "ip": state.get("ip", ""),
            "verdict": verdict.get("verdict", "inconclusive"),
            "score": verdict.get("score", 0),
            "confidence": verdict.get("confidence", 0),
            "level": verdict.get("level", "low"),
            "factors": (verdict.get("factors") or [])[:6],
            "geo": geo,
            "attack_profile": osint.get("attack_profile", {}),
            "related_alerts": corr.get("related_count", 0),
            "recommended_actions": actions,
        }
        ai = await llm_analyze(ctx)
        state["ai"] = ai.model_dump()

    async def _propose_actions(self, state: dict) -> None:
        verdict = (state.get("verdict") or {}).get("verdict", "inconclusive")
        osint   = state.get("osint") or {}
        attack  = (osint.get("attack_profile") or {}).get("type", "unknown")
        ip      = state.get("ip", "")
        agent_id = (state.get("alert") or {}).get("agent", {}).get("id", "")
        actions: list[dict] = []

        if verdict == "malicious":
            if ip:
                actions.append({"action": "block_ip", "label": f"Bloquer l'IP {ip}",
                                "priority": "high", "requires_confirmation": True, "auto": False})
            if agent_id:
                actions.append({"action": "isolate_host", "label": "Isoler la machine (Wazuh AR)",
                                "priority": "high", "requires_confirmation": True, "auto": False})
        if attack == "ddos" and ip:
            actions.append({"action": "rate_limit", "label": "Appliquer un rate-limit agressif",
                            "priority": "medium", "requires_confirmation": True, "auto": False})
        if verdict == "inconclusive":
            actions.append({"action": "escalate", "label": "Revue analyste (verdict incertain)",
                            "priority": "medium", "requires_confirmation": False, "auto": False})
        actions.append({"action": "monitor", "label": "Surveillance renforcée 72h",
                        "priority": "low", "requires_confirmation": False, "auto": False})
        state["proposed_actions"] = actions

    async def _persist(self, state: dict) -> None:
        # Document compact (on ne ré-indexe pas l'alerte brute entière)
        doc = {
            "id":               state["id"],
            "source":           state["source"],
            "created_at":       state["created_at"],
            "finished_at":      state.get("finished_at"),
            "ip":               state.get("ip", ""),
            "alert_meta":       state.get("alert_meta", {}),
            "verdict":          state.get("verdict", {}),
            "decision":         state.get("decision", "inconclusive"),
            "correlation":      state.get("correlation", {}),
            "ai":               state.get("ai", {}),
            "proposed_actions": state.get("proposed_actions", []),
            "feedback_used":    state.get("feedback", []),
            "trace":            state.get("trace", []),
            "timestamp":        datetime.now(timezone.utc).isoformat(),
        }
        try:
            client = await self.os.get_client()
            await client.index(index=AI_INDEX, id=state["id"], body=doc, refresh=True)
        except Exception as e:
            logger.warning("Persistance investigation IA impossible (%s)", e)

    async def _escalate(self, state: dict) -> None:
        if state["source"] != "auto":
            return
        decision = state.get("decision", "inconclusive")
        if decision not in ("malicious", "inconclusive"):
            return
        try:
            from api.services.notifications import NotificationService
            v = state.get("verdict", {})
            meta = state.get("alert_meta", {})
            emoji = "🔴" if decision == "malicious" else "🟠"
            await NotificationService().send_all(
                f"{emoji} Investigation IA autonome — verdict {decision.upper()}\n"
                f"IP: {state.get('ip', 'N/A')}  Score: {v.get('score', 0)}/100 "
                f"(confiance {v.get('confidence', 0)}%)\n"
                f"Alerte: {meta.get('rule_desc', 'N/A')} (niveau {meta.get('level', '?')})\n"
                f"Résumé: {(state.get('ai') or {}).get('summary', '')[:200]}\n"
                f"Rapport: /ai (id {state['id']})",
                priority="critical" if decision == "malicious" else "high",
            )
        except Exception as e:
            logger.debug("Escalade notification impossible (%s)", e)

        # Webhook sortant (sync tickets — n8n/Slack/Jira)
        try:
            from api.services.webhooks import emit
            v = state.get("verdict", {})
            await emit("ai_verdict", {
                "id": state["id"], "ip": state.get("ip", ""), "decision": decision,
                "score": v.get("score", 0), "confidence": v.get("confidence", 0),
                "summary": (state.get("ai") or {}).get("summary", ""),
            })
        except Exception as e:
            logger.debug("Webhook escalade impossible (%s)", e)


# ---------------------------------------------------------------------------
# Accès aux rapports persistés (pour le router)
# ---------------------------------------------------------------------------
async def list_reports(size: int = 50, verdict: str | None = None) -> list[dict]:
    try:
        client = await OpenSearchClient().get_client()
        query: dict = {"match_all": {}}
        if verdict:
            query = {"term": {"decision": verdict}}
        resp = await client.search(
            index=AI_INDEX,
            body={"size": size, "query": query, "sort": [{"timestamp": {"order": "desc"}}]},
        )
        return [h["_source"] for h in resp.get("hits", {}).get("hits", [])]
    except Exception as e:
        logger.info("list_reports indisponible (%s)", e)
        return []


async def get_report(report_id: str) -> dict | None:
    try:
        client = await OpenSearchClient().get_client()
        resp = await client.get(index=AI_INDEX, id=report_id)
        return resp.get("_source")
    except Exception as e:
        logger.info("get_report(%s) indisponible (%s)", report_id, e)
        return None
