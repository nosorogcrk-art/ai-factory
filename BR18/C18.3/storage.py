import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import uuid

from models import RuleCreate, RuleInDB, RuleUpdate

DATA_DIR = Path("/data")
RULES_FILE = DATA_DIR / "rules.json"
logger = logging.getLogger(__name__)

def _load_rules() -> Dict[str, dict]:
    if not RULES_FILE.exists():
        return {}
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_rules(rules: Dict[str, dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)

def get_all_rules() -> List[RuleInDB]:
    rules_dict = _load_rules()
    return [RuleInDB(**data) for data in rules_dict.values()]

def get_rule(rule_id: str) -> Optional[RuleInDB]:
    rules = _load_rules()
    data = rules.get(rule_id)
    if data:
        return RuleInDB(**data)
    return None

def create_rule(rule: RuleCreate) -> RuleInDB:
    rules = _load_rules()
    rule_id = str(uuid.uuid4())[:8]
    now = datetime.now()
    rule_dict = rule.dict()
    rule_dict.update({
        "id": rule_id,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat()
    })
    rules[rule_id] = rule_dict
    _save_rules(rules)
    logger.info(f"Created rule {rule_id}: {rule.name}")
    return RuleInDB(**rule_dict)

def update_rule(rule_id: str, rule_update: RuleUpdate) -> Optional[RuleInDB]:
    rules = _load_rules()
    if rule_id not in rules:
        return None
    data = rules[rule_id]
    update_data = rule_update.dict(exclude_unset=True)
    data.update(update_data)
    data["updated_at"] = datetime.now().isoformat()
    rules[rule_id] = data
    _save_rules(rules)
    logger.info(f"Updated rule {rule_id}")
    return RuleInDB(**data)

def delete_rule(rule_id: str) -> bool:
    rules = _load_rules()
    if rule_id not in rules:
        return False
    del rules[rule_id]
    _save_rules(rules)
    logger.info(f"Deleted rule {rule_id}")
    return True
