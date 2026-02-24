"""
Client OpenSearch — Service de stockage et recherche
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Any

from opensearchpy import AsyncOpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import NotFoundError

from api.core.config import settings

logger = logging.getLogger(__name__)


class OpenSearchClient:
    """Client singleton pour OpenSearch."""

    _instance: Optional["OpenSearchClient"] = None
    _client: Optional[AsyncOpenSearch] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_client(self) -> AsyncOpenSearch:
        """Retourne le client OpenSearch, crée-le si nécessaire."""
        if self._client is None:
            self._client = AsyncOpenSearch(
                hosts=[settings.OPENSEARCH_URL],
                http_auth=(settings.OPENSEARCH_USER, settings.OPENSEARCH_PASSWORD),
                use_ssl=True,
                verify_certs=False,  # Désactiver en prod avec certificat valide
                ssl_show_warn=False,
                connection_class=RequestsHttpConnection,
                timeout=30,
                max_retries=3,
                retry_on_timeout=True,
            )
            logger.info("Client OpenSearch initialisé sur %s", settings.OPENSEARCH_URL)
        return self._client

    async def close(self):
        """Ferme la connexion."""
        if self._client:
            await self._client.close()
            self._client = None

    # ----------------------------------------------------------
    # Alertes
    # ----------------------------------------------------------

    async def get_recent_alerts(
        self,
        min_level: int = 10,
        since: Optional[datetime] = None,
        max_results: int = 100,
    ) -> List[dict]:
        """
        Récupère les alertes récentes niveau >= min_level.
        Utilisé par l'AlertEngine pour le polling.
        """
        if since is None:
            since = datetime.utcnow() - timedelta(seconds=20)

        client = await self.get_client()
        query = {
            "bool": {
                "must": [
                    {"range": {"rule.level": {"gte": min_level}}},
                    {"range": {"timestamp": {"gte": since.isoformat() + "Z"}}},
                ]
            }
        }

        try:
            response = await client.search(
                index=settings.OPENSEARCH_INDEX_ALERTS,
                body={
                    "query": query,
                    "sort": [{"timestamp": {"order": "desc"}}],
                    "size": max_results,
                },
            )
            return [hit["_source"] | {"id": hit["_id"]} for hit in response["hits"]["hits"]]
        except Exception as e:
            logger.error("Erreur get_recent_alerts: %s", e)
            return []

    async def search_alerts(
        self,
        q: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        agent_name: Optional[str] = None,
        mitre_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> dict:
        """Recherche avancée dans les alertes avec filtres multiples."""
        client = await self.get_client()

        must_clauses = []
        filter_clauses = []

        if q:
            must_clauses.append({
                "multi_match": {
                    "query": q,
                    "fields": ["rule.description", "agent.name", "data.srcip", "rule.id"],
                    "type": "best_fields",
                }
            })

        if severity:
            level_ranges = {
                "low":      {"gte": 1,  "lt": 7},
                "medium":   {"gte": 7,  "lt": 10},
                "high":     {"gte": 10, "lt": 14},
                "critical": {"gte": 14},
            }
            if severity in level_ranges:
                filter_clauses.append({"range": {"rule.level": level_ranges[severity]}})

        if agent_name:
            filter_clauses.append({"term": {"agent.name.keyword": agent_name}})

        if mitre_id:
            filter_clauses.append({"term": {"rule.mitre.id": mitre_id}})

        if start_date or end_date:
            date_range = {}
            if start_date:
                date_range["gte"] = start_date.isoformat() + "Z"
            if end_date:
                date_range["lte"] = end_date.isoformat() + "Z"
            filter_clauses.append({"range": {"timestamp": date_range}})

        query = {
            "bool": {
                "must": must_clauses or [{"match_all": {}}],
                "filter": filter_clauses,
            }
        }

        from_offset = (page - 1) * per_page

        try:
            response = await client.search(
                index=settings.OPENSEARCH_INDEX_ALERTS,
                body={
                    "query": query,
                    "sort": [{"timestamp": {"order": "desc"}}],
                    "size": per_page,
                    "from": from_offset,
                    "aggs": {
                        "by_severity": {
                            "range": {
                                "field": "rule.level",
                                "ranges": [
                                    {"key": "low",      "from": 1,  "to": 7},
                                    {"key": "medium",   "from": 7,  "to": 10},
                                    {"key": "high",     "from": 10, "to": 14},
                                    {"key": "critical", "from": 14},
                                ],
                            }
                        },
                        "top_agents": {
                            "terms": {"field": "agent.name.keyword", "size": 10}
                        },
                    },
                },
            )
            total = response["hits"]["total"]["value"]
            hits = [hit["_source"] | {"id": hit["_id"]} for hit in response["hits"]["hits"]]
            return {
                "total": total,
                "items": hits,
                "page": page,
                "per_page": per_page,
                "has_next": (from_offset + per_page) < total,
                "aggregations": response.get("aggregations", {}),
            }
        except Exception as e:
            logger.error("Erreur search_alerts: %s", e)
            return {"total": 0, "items": [], "page": page, "per_page": per_page, "has_next": False}

    async def get_alert(self, alert_id: str) -> Optional[dict]:
        """Récupère une alerte par son ID."""
        client = await self.get_client()
        try:
            response = await client.get(
                index=settings.OPENSEARCH_INDEX_ALERTS,
                id=alert_id,
            )
            return response["_source"] | {"id": response["_id"]}
        except NotFoundError:
            return None
        except Exception as e:
            logger.error("Erreur get_alert(%s): %s", alert_id, e)
            return None

    async def update_alert(self, alert_id: str, fields: dict) -> bool:
        """Met à jour des champs spécifiques d'une alerte."""
        client = await self.get_client()
        try:
            await client.update(
                index=settings.OPENSEARCH_INDEX_ALERTS,
                id=alert_id,
                body={"doc": fields | {"updated_at": datetime.utcnow().isoformat()}},
            )
            return True
        except Exception as e:
            logger.error("Erreur update_alert(%s): %s", alert_id, e)
            return False

    # ----------------------------------------------------------
    # Dashboard — Statistiques
    # ----------------------------------------------------------

    async def get_stats(self, period_hours: int = 24) -> dict:
        """Statistiques globales pour le dashboard."""
        client = await self.get_client()
        since = (datetime.utcnow() - timedelta(hours=period_hours)).isoformat() + "Z"

        try:
            response = await client.search(
                index=settings.OPENSEARCH_INDEX_ALERTS,
                body={
                    "query": {
                        "range": {"timestamp": {"gte": since}}
                    },
                    "size": 0,
                    "aggs": {
                        "total_alerts": {"value_count": {"field": "_id"}},
                        "by_level": {
                            "range": {
                                "field": "rule.level",
                                "ranges": [
                                    {"key": "low",      "from": 1,  "to": 7},
                                    {"key": "medium",   "from": 7,  "to": 10},
                                    {"key": "high",     "from": 10, "to": 14},
                                    {"key": "critical", "from": 14},
                                ],
                            }
                        },
                        "top_rules": {
                            "terms": {"field": "rule.description.keyword", "size": 10}
                        },
                        "top_agents": {
                            "terms": {"field": "agent.name.keyword", "size": 10}
                        },
                        "top_src_ips": {
                            "terms": {"field": "data.srcip.keyword", "size": 10}
                        },
                        "alerts_over_time": {
                            "date_histogram": {
                                "field": "timestamp",
                                "fixed_interval": "1h",
                            }
                        },
                        "mitre_tactics": {
                            "terms": {"field": "rule.mitre.tactic.keyword", "size": 15}
                        },
                    },
                },
            )
            return {
                "period_hours": period_hours,
                "aggregations": response.get("aggregations", {}),
            }
        except Exception as e:
            logger.error("Erreur get_stats: %s", e)
            return {}
