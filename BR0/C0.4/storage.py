import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from models import BranchInDB

REGISTRY_FILE = Path("SYSTEM_REGISTRY.json")
BRANCHES_KEY = "branches"

def _load_registry() -> dict:
    if not REGISTRY_FILE.exists():
        return {BRANCHES_KEY: {}}
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_registry(data: dict):
    # Прямая запись без временного файла
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

def get_branches() -> Dict[str, BranchInDB]:
    data = _load_registry()
    branches_dict = data.get(BRANCHES_KEY, {})
    return {bid: BranchInDB(**bdata) for bid, bdata in branches_dict.items()}

def get_branch(branch_id: str) -> Optional[BranchInDB]:
    branches = get_branches()
    return branches.get(branch_id)

def create_branch(branch_id: str, branch: BranchInDB) -> None:
    data = _load_registry()
    if BRANCHES_KEY not in data:
        data[BRANCHES_KEY] = {}
    if branch_id in data[BRANCHES_KEY]:
        raise ValueError(f"Branch with id {branch_id} already exists")
    data[BRANCHES_KEY][branch_id] = branch.dict()
    _save_registry(data)

def update_branch(branch_id: str, branch: BranchInDB) -> None:
    data = _load_registry()
    if BRANCHES_KEY not in data or branch_id not in data[BRANCHES_KEY]:
        raise ValueError(f"Branch {branch_id} not found")
    data[BRANCHES_KEY][branch_id] = branch.dict()
    _save_registry(data)

def delete_branch(branch_id: str, hard: bool = False) -> None:
    data = _load_registry()
    if BRANCHES_KEY not in data or branch_id not in data[BRANCHES_KEY]:
        raise ValueError(f"Branch {branch_id} not found")
    if hard:
        del data[BRANCHES_KEY][branch_id]
    else:
        data[BRANCHES_KEY][branch_id]["soft_deleted"] = True
        data[BRANCHES_KEY][branch_id]["status"] = "inactive"
    _save_registry(data)
