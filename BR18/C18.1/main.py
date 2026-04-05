import os
import json
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError, validator
from typing import Optional
import apscheduler.schedulers.background
from apscheduler.triggers.interval import IntervalTrigger
import gzip
import shutil
from pathlib import Path

LOG_DIR = os.getenv("LOG_DIR", "/data/logs")
LOG_FILE = os.path.join(LOG_DIR, "log_aggregator.log")
COMPRESS_AFTER_DAYS = int(os.getenv("COMPRESS_AFTER_DAYS", "7"))
DELETE_AFTER_DAYS = int(os.getenv("DELETE_AFTER_DAYS", "30"))
ROTATE_CHECK_INTERVAL = int(os.getenv("ROTATE_CHECK_INTERVAL", "3600"))

Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Log Aggregator", version="0.1.0")

_current_date = None
_current_file = None

def get_current_log_file():
    global _current_date, _current_file
    today = datetime.now().strftime("%Y-%m-%d")
    if today != _current_date:
        _current_date = today
        _current_file = Path(LOG_DIR) / f"logs-{today}.jsonl"
        logger.info(f"Switched to new log file: {_current_file}")
    return _current_file

class LogEntry(BaseModel):
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    service: str = Field(..., description="Source service")
    event_type: str = Field(..., description="Type of event")
    details: Optional[dict] = Field(default=None, description="Additional data")

    @validator("timestamp")
    def validate_timestamp(cls, v):
        try:
            datetime.fromisoformat(v)
        except Exception:
            raise ValueError("Invalid ISO 8601 timestamp")
        return v

@app.post("/api/logs")
async def receive_logs(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if isinstance(body, dict):
        logs = [body]
    elif isinstance(body, list):
        logs = body
    else:
        raise HTTPException(status_code=400, detail="Request body must be a JSON object or array")

    validated_logs = []
    errors = []
    for idx, log_data in enumerate(logs):
        try:
            validated = LogEntry(**log_data)
            validated_logs.append(validated.dict())
        except ValidationError as e:
            # Convert errors to serializable format
            serializable_errors = []
            for error in e.errors():
                error_copy = error.copy()
                # Remove non-serializable ctx if it contains exception
                if 'ctx' in error_copy and 'error' in error_copy['ctx']:
                    error_copy['ctx'] = {k: str(v) if isinstance(v, Exception) else v 
                                        for k, v in error_copy['ctx'].items()}
                serializable_errors.append(error_copy)
            errors.append({"index": idx, "errors": serializable_errors})

    if errors:
        logger.warning(f"Validation errors: {errors}")
        raise HTTPException(status_code=400, detail={"message": "Invalid log entries", "errors": errors})

    log_file = get_current_log_file()
    try:
        with open(log_file, "a") as f:
            for log in validated_logs:
                f.write(json.dumps(log, ensure_ascii=False) + "\n")
        logger.info(f"Written {len(validated_logs)} logs to {log_file}")
    except Exception as e:
        logger.error(f"Failed to write logs: {e}")
        raise HTTPException(status_code=500, detail="Log storage failed")

    return {"status": "accepted", "count": len(validated_logs)}

@app.get("/health")
async def health():
    return {"status": "ok"}

def rotate_and_clean():
    logger.info("Running rotation and cleanup task")
    now = datetime.now()
    for file_path in Path(LOG_DIR).glob("logs-*.jsonl"):
        try:
            date_str = file_path.stem.split("-")[1]
            file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (IndexError, ValueError):
            logger.warning(f"Skipping file with unexpected name: {file_path.name}")
            continue

        days_old = (now.date() - file_date).days

        if days_old >= COMPRESS_AFTER_DAYS and not file_path.suffix == ".gz":
            gz_path = file_path.with_suffix(file_path.suffix + ".gz")
            with open(file_path, 'rb') as f_in:
                with gzip.open(gz_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            file_path.unlink()
            logger.info(f"Compressed {file_path.name} -> {gz_path.name}")

        if days_old >= DELETE_AFTER_DAYS:
            if file_path.suffix == ".gz":
                file_path.unlink()
                logger.info(f"Deleted old compressed log: {file_path.name}")
            else:
                file_path.unlink()
                logger.info(f"Deleted old log (not compressed): {file_path.name}")

scheduler = apscheduler.schedulers.background.BackgroundScheduler()
scheduler.add_job(rotate_and_clean, trigger=IntervalTrigger(seconds=ROTATE_CHECK_INTERVAL))
scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8093)))
