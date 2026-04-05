import os
import logging
from fastapi import FastAPI, HTTPException
from models import RuleCreate, RuleUpdate
import storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Alert Manager", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok"}

# CRUD for rules
@app.get("/api/rules")
def list_rules():
    return storage.get_all_rules()

@app.post("/api/rules")
def create_rule(rule: RuleCreate):
    try:
        new_rule = storage.create_rule(rule)
        return new_rule
    except Exception as e:
        logger.error(f"Failed to create rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/rules/{rule_id}")
def get_rule(rule_id: str):
    rule = storage.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule

@app.put("/api/rules/{rule_id}")
def update_rule(rule_id: str, rule_update: RuleUpdate):
    rule = storage.update_rule(rule_id, rule_update)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule

@app.delete("/api/rules/{rule_id}")
def delete_rule(rule_id: str):
    if not storage.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "deleted"}

# Заглушка для тестирования (P18.3.2 будет реализована позже)
@app.get("/api/alerts/history")
def alerts_history():
    return {"message": "Not implemented yet"}

@app.post("/api/test")
def test_notification(channel: str):
    # Заглушка для проверки каналов
    return {"status": "test sent (stub)", "channel": channel}