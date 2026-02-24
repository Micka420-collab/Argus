"""
Router — Règles Wazuh custom
Lecture et gestion des règles depuis le fichier local_rules.xml.
"""
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

RULES_FILE = Path("/var/ossec/etc/rules/local_rules.xml")


class Rule(BaseModel):
    id: str
    level: int
    description: str
    groups: List[str] = []
    mitre_ids: List[str] = []
    enabled: bool = True


@router.get("", summary="Liste des règles custom")
async def list_rules():
    """Retourne toutes les règles custom Wazuh."""
    if not RULES_FILE.exists():
        return {"rules": [], "total": 0}

    try:
        tree = ET.parse(RULES_FILE)
        root = tree.getroot()
        rules = []

        for rule_elem in root.findall(".//rule"):
            rule_id = rule_elem.get("id", "")
            level = int(rule_elem.get("level", 0))
            desc_elem = rule_elem.find("description")
            group_elem = rule_elem.find("group")
            mitre_elem = rule_elem.find("mitre")

            description = desc_elem.text if desc_elem is not None else "N/A"
            groups = [g.strip() for g in group_elem.text.split(",")] if group_elem is not None and group_elem.text else []
            mitre_ids = [m.text for m in mitre_elem.findall("id")] if mitre_elem is not None else []

            rules.append(Rule(
                id=rule_id,
                level=level,
                description=description,
                groups=groups,
                mitre_ids=mitre_ids,
            ))

        return {"rules": [r.model_dump() for r in rules], "total": len(rules)}
    except ET.ParseError as e:
        raise HTTPException(status_code=500, detail=f"Erreur parsing XML: {e}")


@router.get("/{rule_id}", summary="Détail d'une règle")
async def get_rule(rule_id: str):
    """Retourne le détail d'une règle par son ID."""
    result = await list_rules()
    for rule in result["rules"]:
        if rule["id"] == rule_id:
            return rule
    raise HTTPException(status_code=404, detail=f"Règle {rule_id} introuvable")


@router.get("/raw/xml", summary="Contenu XML brut des règles")
async def get_rules_xml():
    """Retourne le fichier XML des règles brut."""
    if not RULES_FILE.exists():
        raise HTTPException(status_code=404, detail="Fichier de règles introuvable")
    return {"content": RULES_FILE.read_text()}
