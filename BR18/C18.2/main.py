import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
import storage
from models import MetricIn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AGGREGATION_INTERVAL = int(os.getenv("AGGREGATION_INTERVAL", "10"))  # секунд

async def periodic_aggregation():
    while True:
        await asyncio.sleep(AGGREGATION_INTERVAL)
        storage.update_all_aggregates()
        logger.info("Aggregates updated")

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(periodic_aggregation())
    yield
    task.cancel()

app = FastAPI(title="Metrics Dashboard", version="1.0.0", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/metrics")
async def receive_metric(metric: MetricIn):
    storage.add_metric(metric)
    logger.info(f"Received metric {metric.name} = {metric.value}")
    return {"status": "accepted"}

@app.get("/api/metrics")
def list_all_aggregates():
    metrics = storage.list_metrics()
    result = {}
    for name in metrics:
        agg = storage.get_aggregate(name)
        if agg:
            result[name] = agg
    return result

@app.get("/api/metrics/{name}")
def get_metric_aggregate(name: str):
    agg = storage.get_aggregate(name)
    if agg is None:
        raise HTTPException(status_code=404, detail="Metric not found")
    return agg

@app.get("/api/metrics/list")
def list_metric_names():
    return storage.list_metrics()
