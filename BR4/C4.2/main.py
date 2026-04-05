import os
import json
import logging
import asyncio
import time
import subprocess
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import httpx
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI(title="Graph Visualizer")

GRAPH_FILE = Path("01_ЦЕХ/ГРАФ/links_graph.json")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/graph_api.log")
BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093")

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ===== Логирование в BR18 (middleware) =====
async def send_log_to_br18(log_entry):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{BR18_URL}/api/logs", json=log_entry, timeout=2.0)
    except Exception as e:
        logging.error(f"Failed to send log to BR18: {e}")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000
    asyncio.create_task(send_log_to_br18({
        "timestamp": datetime.now().isoformat(),
        "service": "C4.2",
        "event_type": "api_call",
        "details": {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "response_time_ms": round(duration, 2)
        }
    }))
    return response

# ===== Функции работы с графом =====
def load_graph():
    if not GRAPH_FILE.exists():
        return {"nodes": [], "edges": []}
    try:
        with open(GRAPH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load graph: {e}")
        return {"nodes": [], "edges": []}

# ===== Эндпоинты =====
@app.get("/api/graph")
async def get_graph(graph_type: str = "semantic"):
    """
    Возвращает граф. Поддерживаемые типы:
    - semantic (по умолчанию) – граф ссылок между документами.
    - skills – граф навыков (пока заглушка).
    - patches – граф патчей (пока заглушка).
    """
    if graph_type == "semantic":
        graph = load_graph()
        return graph
    elif graph_type == "skills":
        # TODO: интеграция с C17.3
        return {"nodes": [], "edges": [], "message": "Skills graph not implemented yet"}
    elif graph_type == "patches":
        # TODO: интеграция с GRAPH_DEPENDENCIES.json
        return {"nodes": [], "edges": [], "message": "Patches graph not implemented yet"}
    else:
        raise HTTPException(status_code=400, detail="Invalid graph type")

@app.get("/api/node/{node_id}")
async def get_node(node_id: str):
    graph = load_graph()
    node = next((n for n in graph["nodes"] if n["id"] == node_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    # Дополнительно можно загрузить содержимое файла или метаданные
    return {"id": node["id"], "type": node["type"], "label": node["label"]}

@app.get("/health")
async def health():
    return {"status": "ok"}

# ===== Фоновая задача для обновления графа (раз в час) =====
def update_graph():
    try:
        subprocess.run(["python", "graph_builder.py"], check=True, capture_output=True, text=True)
        logging.info("Graph updated successfully")
    except Exception as e:
        logging.error(f"Failed to update graph: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(update_graph, "interval", hours=1)
scheduler.start()

@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8099)))
