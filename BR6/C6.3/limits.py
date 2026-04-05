import json
import logging
from pathlib import Path
from datetime import datetime
import database

CONFIG_PATH = Path("/data/limits_config.json")
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "global": {"daily": 10.0, "monthly": 300.0},
    "branches": {
        "BR1": {"daily": 5.0},
        "BR2": {"daily": 5.0}
    },
    "agents": {
        "ГЕФЕСТ": {"daily": 3.0},
        "АРХИ": {"daily": 2.0},
        "АРГУС": {"daily": 1.0}
    },
    "model_alternatives": {
        "gpt-4": ["gpt-3.5-turbo", "claude-instant"]
    }
}

def load_config():
    if not CONFIG_PATH.exists():
        logger.warning(f"Config not found at {CONFIG_PATH}, using defaults")
        return DEFAULT_CONFIG
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    logger.info("Config saved")

def check_limit(agent: str, model: str, estimated_tokens: int = 0, branch: str = None, task_id: str = None):
    config = load_config()
    now = datetime.now()
    day_start = datetime(now.year, now.month, now.day)
    month_start = datetime(now.year, now.month, 1)

    global_limits = config.get("global", {})
    total_cost = database.get_total_cost_since(day_start)
    if "daily" in global_limits and total_cost + (estimated_tokens / 1000) > global_limits["daily"]:
        return False, None, "Daily global limit exceeded"
    total_month = database.get_total_cost_since(month_start)
    if "monthly" in global_limits and total_month + (estimated_tokens / 1000) > global_limits["monthly"]:
        return False, None, "Monthly global limit exceeded"

    if branch:
        branch_limits = config.get("branches", {}).get(branch, {})
        branch_cost = database.get_branch_cost(branch, day_start)
        if "daily" in branch_limits and branch_cost + (estimated_tokens / 1000) > branch_limits["daily"]:
            return False, None, f"Daily limit for branch {branch} exceeded"

    agent_limits = config.get("agents", {}).get(agent, {})
    agent_cost = database.get_agent_cost(agent, day_start)
    if "daily" in agent_limits and agent_cost + (estimated_tokens / 1000) > agent_limits["daily"]:
        alternatives = config.get("model_alternatives", {}).get(model, [])
        for alt in alternatives:
            return True, alt, f"Agent {agent} daily limit exceeded, suggested {alt}"
        return False, None, f"Daily limit for agent {agent} exceeded"

    return True, None, ""