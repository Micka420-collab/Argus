"""
Scheduler APScheduler — tâches de fond périodiques
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


async def start_scheduler():
    """Démarre le scheduler et enregistre les tâches."""
    from api.services.enrichment import cleanup_old_enrichments
    from api.services.deduplication import cleanup_dedup_cache
    from api.services.opensearch import OpenSearchClient

    # Nettoyage cache enrichissement toutes les heures
    scheduler.add_job(
        cleanup_old_enrichments,
        trigger=IntervalTrigger(hours=1),
        id="cleanup_enrichments",
        name="Nettoyage cache enrichissements",
        replace_existing=True,
    )

    # Nettoyage cache déduplication toutes les 15 minutes
    scheduler.add_job(
        cleanup_dedup_cache,
        trigger=IntervalTrigger(minutes=15),
        id="cleanup_dedup",
        name="Nettoyage cache déduplication",
        replace_existing=True,
    )

    # Sync ILM OpenSearch — chaque jour à 2h du matin
    scheduler.add_job(
        ensure_ilm_policy,
        trigger=CronTrigger(hour=2, minute=0),
        id="opensearch_ilm",
        name="Vérification politique ILM OpenSearch",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler démarré — %d tâches enregistrées", len(scheduler.get_jobs()))


async def stop_scheduler():
    """Arrête proprement le scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler arrêté")


async def ensure_ilm_policy():
    """
    Crée/met à jour la politique ILM OpenSearch pour la rétention des données.
    - Chaud  : 7 jours (SSD rapide)
    - Tiède  : 30 jours (stockage normal)
    - Froid  : 90 jours (stockage lent)
    - Suppression : > 90 jours
    """
    from api.services.opensearch import OpenSearchClient
    os_client = OpenSearchClient()

    policy = {
        "policy": {
            "description": "SOC Platform — Politique de rétention des logs",
            "default_state": "hot",
            "states": [
                {
                    "name": "hot",
                    "actions": [
                        {
                            "rollover": {
                                "min_index_age": "1d",
                                "min_primary_shard_size": "50gb"
                            }
                        }
                    ],
                    "transitions": [
                        {"state_name": "warm", "conditions": {"min_index_age": "7d"}}
                    ],
                },
                {
                    "name": "warm",
                    "actions": [
                        {"replica_count": {"number_of_replicas": 0}},
                        {"index_priority": {"priority": 50}},
                    ],
                    "transitions": [
                        {"state_name": "cold", "conditions": {"min_index_age": "30d"}}
                    ],
                },
                {
                    "name": "cold",
                    "actions": [{"index_priority": {"priority": 1}}],
                    "transitions": [
                        {"state_name": "delete", "conditions": {"min_index_age": "90d"}}
                    ],
                },
                {
                    "name": "delete",
                    "actions": [{"delete": {}}],
                    "transitions": [],
                },
            ],
        }
    }

    try:
        client = await os_client.get_client()
        await client.transport.perform_request(
            "PUT",
            "/_plugins/_ism/policies/soc-ilm-policy",
            body=policy,
        )
        logger.info("Politique ILM OpenSearch mise à jour")
    except Exception as e:
        logger.error("Erreur mise à jour ILM: %s", e)
