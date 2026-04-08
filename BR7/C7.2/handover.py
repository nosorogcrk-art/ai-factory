#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
import argparse
import os
import requests
from pathlib import Path
from datetime import datetime, timezone

MODEL_PATH = Path("00_КАНОН/ПРОЦЕССЫ/task_model.json")
REGISTRY_PATH = Path("01_ЦЕХ/ТЕКУЩИЕ_ЗАДАЧИ/task_registry.json")
LOG_PATH = Path("01_ЦЕХ/01_ЖУРНАЛЫ/ЭСТАФЕТА.md")
LOG_AGGREGATOR_URL = os.getenv("LOG_AGGREGATOR_URL", "http://log-aggregator:8093/api/logs")

MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

TASK_MODEL = {
    "statuses": ["NEW", "IN_PROGRESS", "ON_REVIEW", "REWORK", "DONE", "BLOCKED"],
    "transitions": [
        {"from": "NEW", "to": "IN_PROGRESS", "allowed_roles": ["АРХИ", "ГЕФЕСТ", "АРГУС"]},
        {"from": "IN_PROGRESS", "to": "ON_REVIEW", "allowed_roles": ["ГЕФЕСТ"]},
        {"from": "ON_REVIEW", "to": "REWORK", "allowed_roles": ["РЕВА"]},
        {"from": "ON_REVIEW", "to": "DONE", "allowed_roles": ["РЕВА"]},
        {"from": "REWORK", "to": "IN_PROGRESS", "allowed_roles": ["ГЕФЕСТ"]},
        {"from": "*", "to": "BLOCKED", "allowed_roles": ["АРГУС", "*"]},
        {"from": "BLOCKED", "to": "NEW", "allowed_roles": ["АРГУС"]}
    ]
}

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def log_event(task_id, action, actor, comment, new_status, target=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n### {timestamp} – Задача [[{task_id}]]\n"
    entry += f"- **Действие:** {action}\n"
    entry += f"- **Актёр:** {actor}\n"
    if comment:
        entry += f"- **Комментарий:** {comment}\n"
    entry += f"- **Новый статус:** {new_status}\n"
    if target:
        entry += f"- **Цель:** {target}\n"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)

def _send_log_to_br18(event_type, details):
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "C7.2",
        "event_type": event_type,
        "details": details
    }
    try:
        requests.post(LOG_AGGREGATOR_URL, json=log_entry, timeout=5.0)
    except Exception as e:
        print(f"Failed to send log to BR18: {e}", file=sys.stderr)

def is_transition_allowed(model, from_status, to_status, actor):
    for t in model.get("transitions", []):
        if (t["from"] == from_status or t["from"] == "*") and t["to"] == to_status:
            allowed = t.get("allowed_roles", [])
            if "*" in allowed or actor in allowed:
                return True
    return False

def handle_command(cmd):
    command = cmd.get("command")
    task_id = cmd.get("task_id")
    actor = cmd.get("actor")
    comment = cmd.get("comment", "")
    target = cmd.get("target")

    if not command or not task_id or not actor:
        return {"success": False, "error": "Missing required fields"}

    try:
        model = load_json(MODEL_PATH)
        registry = load_json(REGISTRY_PATH)
    except Exception as e:
        return {"success": False, "error": f"Failed to load model/registry: {e}"}

    task = next((t for t in registry if t["id"] == task_id), None)
    if command == "take" and task is None:
        task = {
            "id": task_id,
            "status": "NEW",
            "assigned_to": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "history": []
        }
        registry.append(task)
    elif task is None:
        return {"success": False, "error": f"Task {task_id} not found"}

    old_status = task["status"]
    target_status = None
    target_role = None

    if command == "take":
        target_status = "IN_PROGRESS"
        target_role = actor
        task["assigned_to"] = actor
    elif command == "complete":
        target_status = "ON_REVIEW"
    elif command == "delegate":
        target_role = target
        if not target_role:
            return {"success": False, "error": "delegate requires target role"}
        if old_status != "IN_PROGRESS":
            return {"success": False, "error": "Can only delegate a task that is in progress"}
        if task["assigned_to"] != actor and actor != "АРГУС":
            return {"success": False, "error": "Only the current assignee or ARGUS can delegate"}
        task["assigned_to"] = target_role
        target_status = old_status
    elif command == "block":
        target_status = "BLOCKED"
    elif command == "unblock":
        target_status = "NEW"
    else:
        return {"success": False, "error": f"Unknown command: {command}"}

    if target_status != old_status:
        if not is_transition_allowed(model, old_status, target_status, actor):
            return {"success": False, "error": f"Transition from {old_status} to {target_status} not allowed for {actor}"}

    if target_status != old_status:
        task["status"] = target_status
    task["updated_at"] = datetime.now(timezone.utc).isoformat()
    task["history"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "from": old_status,
        "to": target_status,
        "actor": actor,
        "comment": comment
    })

    try:
        save_json(REGISTRY_PATH, registry)
    except Exception as e:
        return {"success": False, "error": f"Failed to save registry: {e}"}

    log_event(task_id, command, actor, comment, target_status, target_role)

    log_data = None
    if command == "take":
        log_data = {
            "event_type": "handover_initiated",
            "details": {
                "task_id": task_id,
                "to_agent": target_role,
                "actor": actor,
                "comment": comment,
                "status": task["history"][-1]["from"]
            }
        }
    elif command == "delegate":
        log_data = {
            "event_type": "handover_initiated",
            "details": {
                "task_id": task_id,
                "from_agent": actor,
                "to_agent": target_role,
                "reason": "delegated",
                "comment": comment
            }
        }
    elif command == "complete":
        created = datetime.fromisoformat(task["created_at"])
        now = datetime.now(timezone.utc)
        duration_ms = int((now - created).total_seconds() * 1000)
        log_data = {
            "event_type": "handover_completed",
            "details": {
                "task_id": task_id,
                "from_agent": task["assigned_to"] if task["assigned_to"] else actor,
                "duration_ms": duration_ms,
                "status": "success"
            }
        }
    elif command == "block":
        log_data = {
            "event_type": "handover_failed",
            "details": {
                "task_id": task_id,
                "reason": comment if comment else "blocked",
                "actor": actor,
                "new_status": target_status
            }
        }
    elif command == "unblock":
        log_data = {
            "event_type": "task_unblocked",
            "details": {
                "task_id": task_id,
                "actor": actor,
                "comment": comment,
                "new_status": target_status
            }
        }

    return {"success": True, "new_status": target_status, "log_data": log_data}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--comment", default="")
    parser.add_argument("--target")
    args = parser.parse_args()

    cmd = {
        "command": args.command,
        "task_id": args.task_id,
        "actor": args.actor,
        "comment": args.comment,
    }
    if args.target:
        cmd["target"] = args.target

    result = handle_command(cmd)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["success"]:
        sys.exit(1)

if __name__ == "__main__":
    main()