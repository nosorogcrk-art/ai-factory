import os
import json
import logging
import sqlite3
import uuid
import re
import gzip
import httpx
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any, Tuple
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, field_validator
import apscheduler.schedulers.background
from apscheduler.triggers.interval import IntervalTrigger
import numpy as np
from sklearn.cluster import KMeans
from embedding_model import get_encoder

# --- Конфигурация ---
LOG_SOURCE_DIR = os.getenv("LOG_SOURCE_DIR", "/data/logs")
DB_PATH = Path(os.getenv("DB_PATH", "/data/analyzer.db"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "7"))
CLUSTER_SAMPLE_LIMIT = int(os.getenv("CLUSTER_SAMPLE_LIMIT", "10000"))
MAX_CLUSTERS = int(os.getenv("MAX_CLUSTERS", "20"))
FIXED_CLUSTERS = int(os.getenv("FIXED_CLUSTERS", "0"))
AUTO_ANALYZE_INTERVAL = int(os.getenv("AUTO_ANALYZE_INTERVAL", "3600"))
PATTERN_SAMPLE_LIMIT = int(os.getenv("PATTERN_SAMPLE_LIMIT", "100000"))
BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
ENABLE_BR18 = os.getenv("ENABLE_BR18", "false").lower() == "true"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/log_analyzer.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_encoder = None
_model_available = False

# --- Вспомогательные функции для БД ---
def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    with get_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                service TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT,
                task_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS processed_files (
                file_name TEXT PRIMARY KEY,
                last_line INTEGER NOT NULL,
                last_mtime REAL NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS analysis_jobs (
                job_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                result TEXT,
                parameters TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS cluster_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                pattern TEXT NOT NULL,
                count INTEGER NOT NULL,
                last_seen TEXT NOT NULL,
                sample TEXT,
                from_time TEXT,
                to_time TEXT,
                service_filter TEXT,
                actual_total INTEGER,
                UNIQUE(job_id, pattern)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS error_clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL,
                count INTEGER NOT NULL,
                last_seen TEXT NOT NULL,
                sample TEXT,
                UNIQUE(pattern)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sequence TEXT NOT NULL,
                count INTEGER NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                example TEXT,
                service TEXT,
                UNIQUE(sequence, service)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS analysis_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON logs (timestamp)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_service ON logs (service)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_event_type ON logs (event_type)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_task_id ON logs (task_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_cluster_job ON cluster_results (job_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_pattern_count ON patterns (count)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_pattern_service ON patterns (service)')
        conn.execute("INSERT OR IGNORE INTO analysis_state (key, value) VALUES ('last_pattern_analysis', '1970-01-01T00:00:00Z')")
        conn.commit()
    logger.info("Database initialized")

init_db()

# --- Отправка логов в BR18 ---
async def send_log_to_br18(event_type: str, details: dict) -> None:
    if not ENABLE_BR18:
        logger.info(f"BR18 stub: {event_type} {details}")
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                BR18_URL,
                json={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "service": "C19.1",
                    "event_type": event_type,
                    "details": details
                },
                timeout=5.0
            )
            logger.info(f"Log sent to BR18: {event_type}")
    except Exception as e:
        logger.error(f"Failed to send log to BR18: {e}")

# --- Чтение логов из файлов ---
def read_log_file(file_path: Path):
    if file_path.suffix == '.gz':
        with gzip.open(file_path, 'rt', encoding='utf-8') as f:
            for line in f:
                yield line
    else:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                yield line

def normalize_timestamp(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    except Exception:
        return ts

def process_log_file(file_path: Path, conn: sqlite3.Connection) -> int:
    file_key = file_path.name
    mtime = file_path.stat().st_mtime

    cursor = conn.cursor()
    cursor.execute("SELECT last_line FROM processed_files WHERE file_name = ?", (file_key,))
    row = cursor.fetchone()
    processed = row[0] if row else 0

    try:
        lines = []
        for i, line in enumerate(read_log_file(file_path)):
            if i < processed:
                continue
            lines.append(line)
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        return 0

    if not lines:
        return 0

    inserted = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            ts = data.get('timestamp')
            if ts:
                ts = normalize_timestamp(ts)
            service = data.get('service')
            event_type = data.get('event_type')
            details = json.dumps(data.get('details')) if data.get('details') else None
            if ts and service and event_type:
                task_id = None
                if data.get('details'):
                    task_id = data['details'].get('task_id')
                cursor.execute(
                    "INSERT INTO logs (timestamp, service, event_type, details, task_id) VALUES (?, ?, ?, ?, ?)",
                    (ts, service, event_type, details, task_id)
                )
                inserted += 1
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in {file_path}: {line[:100]}")
            continue
        except Exception as e:
            logger.error(f"Error inserting log: {e}")
            continue

    new_line = processed + len(lines)
    cursor.execute(
        "INSERT OR REPLACE INTO processed_files (file_name, last_line, last_mtime) VALUES (?, ?, ?)",
        (file_key, new_line, mtime)
    )
    conn.commit()
    logger.info(f"Processed {inserted} new logs from {file_path}")
    return inserted

def scan_and_process() -> None:
    logger.info("Scanning for new log files...")
    source_dir = Path(LOG_SOURCE_DIR)
    if not source_dir.exists():
        logger.warning(f"Log source directory {source_dir} does not exist")
        return

    with get_connection() as conn:
        for file_path in source_dir.glob("logs-*.jsonl*"):
            process_log_file(file_path, conn)

        cutoff = datetime.now(timezone.utc) - timedelta(days=LOG_RETENTION_DAYS)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM logs WHERE datetime(timestamp) < datetime(?)", (cutoff.isoformat(),))
        deleted = cursor.rowcount
        conn.commit()
        if deleted:
            logger.info(f"Deleted {deleted} old log entries")

# --- Нормализация текста ошибки ---
def normalize_error_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'\d{4}-\d{2}-\d{2}', '<DATE>', text)
    text = re.sub(r'\d{2}:\d{2}:\d{2}', '<TIME>', text)
    text = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<IP>', text)
    text = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '<UUID>', text)
    text = re.sub(r'\b\d{4,}\b', '#', text)
    text = re.sub(r'\b\d{1,2}\b', '#', text)
    text = ' '.join(text.split())
    return text

def extract_error_text(details_str: Optional[str], event_type: str, service: str) -> str:
    if not details_str:
        return f"{service}/{event_type}"
    try:
        details = json.loads(details_str)
        if isinstance(details, dict):
            if 'error' in details:
                return f"{service}/{event_type}: {details['error']}"
            if 'message' in details:
                return f"{service}/{event_type}: {details['message']}"
        return f"{service}/{event_type}: {details_str[:200]}"
    except Exception:
        return f"{service}/{event_type}: {details_str[:200]}"

# --- Блокировка задач ---
def is_job_running(job_type: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM analysis_jobs WHERE type = ? AND status IN ('pending', 'running')", (job_type,))
        count = cursor.fetchone()[0]
        return count > 0

def start_job(job_id: str, job_type: str, parameters: Optional[dict] = None) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO analysis_jobs (job_id, type, status, parameters) VALUES (?, ?, ?, ?)",
            (job_id, job_type, "running", json.dumps(parameters, default=str) if parameters else None)
        )
        conn.commit()

def finish_job(job_id: str, success: bool, result: Optional[dict] = None) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        status = "completed" if success else "failed"
        cursor.execute(
            "UPDATE analysis_jobs SET status = ?, completed_at = CURRENT_TIMESTAMP, result = ? WHERE job_id = ?",
            (status, json.dumps(result, default=str) if result else None, job_id)
        )
        conn.commit()

# --- Кластеризация ---
def cluster_errors(job_id: str, from_time: Optional[datetime] = None, to_time: Optional[datetime] = None, service_filter: Optional[str] = None) -> None:
    global _encoder, _model_available
    if not _model_available:
        raise RuntimeError("Embedding model not available")

    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT id, timestamp, service, event_type, details
            FROM logs
            WHERE (LOWER(event_type) LIKE '%error%'
               OR LOWER(event_type) LIKE '%failed%'
               OR details LIKE '%"error"%')
        """
        params: List[Any] = []
        if from_time:
            query += " AND timestamp >= ?"
            params.append(from_time.isoformat())
        if to_time:
            query += " AND timestamp <= ?"
            params.append(to_time.isoformat())
        if service_filter:
            query += " AND service = ?"
            params.append(service_filter)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(CLUSTER_SAMPLE_LIMIT)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        actual_total = len(rows)
        if actual_total < 2:
            logger.info("Not enough error logs for clustering")
            return

        texts: List[str] = []
        ids: List[int] = []
        for row in rows:
            error_text = extract_error_text(row['details'], row['event_type'], row['service'])
            if not error_text:
                continue
            normalized = normalize_error_text(error_text)
            texts.append(normalized)
            ids.append(row['id'])

        if len(texts) < 2:
            return

        try:
            embeddings = _encoder.encode(texts, batch_size=64, show_progress_bar=False)  # type: ignore
        except Exception as e:
            raise RuntimeError(f"Embedding failed: {e}")

        n_samples = len(texts)
        n_clusters: int
        if FIXED_CLUSTERS > 1:
            n_clusters = min(FIXED_CLUSTERS, n_samples - 1)
        else:
            max_k = min(MAX_CLUSTERS, n_samples - 1)
            if max_k < 2:
                n_clusters = 2
            else:
                inertias = []
                for k in range(2, max_k + 1):
                    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                    kmeans.fit(embeddings)
                    inertias.append(kmeans.inertia_)
                diffs = np.diff(inertias)
                if len(diffs) > 1:
                    elbow: int = np.argmax(diffs < np.mean(diffs)) + 2  # type: ignore
                else:
                    elbow = 2
                n_clusters = min(max_k, elbow)

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings)

        clusters: Dict[int, List[Tuple[int, str, str, str, str, Optional[str]]]] = defaultdict(list)
        for idx, label in enumerate(labels):
            clusters[label].append((ids[idx], texts[idx], rows[idx]['timestamp'], rows[idx]['service'], rows[idx]['event_type'], rows[idx]['details']))

        for label, items in clusters.items():
            cluster_center = kmeans.cluster_centers_[label]
            indices = [i for i, lbl in enumerate(labels) if lbl == label]
            distances = np.linalg.norm(embeddings[indices] - cluster_center, axis=1)
            closest_idx = indices[np.argmin(distances)]
            orig_row = rows[closest_idx]
            sample_text = extract_error_text(orig_row['details'], orig_row['event_type'], orig_row['service'])
            pattern = texts[closest_idx][:200]
            count = len(items)
            last_seen = max(item[2] for item in items)
            cursor.execute(
                "INSERT INTO cluster_results (job_id, pattern, count, last_seen, sample, from_time, to_time, service_filter, actual_total) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (job_id, pattern, count, last_seen, sample_text[:500],
                 from_time.isoformat() if from_time else None,
                 to_time.isoformat() if to_time else None,
                 service_filter,
                 actual_total)
            )

        cursor.execute("DELETE FROM error_clusters")
        cursor.execute("""
            INSERT INTO error_clusters (pattern, count, last_seen, sample)
            SELECT pattern, count, last_seen, sample
            FROM cluster_results
            WHERE job_id = ?
        """, (job_id,))

        logger.info(f"Clustered {len(clusters)} error patterns from {len(texts)} records for job {job_id}")

# --- Анализ паттернов ---
def analyze_patterns(
    job_id: str,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    service_filter: Optional[str] = None,
    min_support: int = 2,
    window_seconds: int = 10,
    event_types: List[str] = ['error', 'failed']
) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()

        if from_time is None:
            cursor.execute("SELECT value FROM analysis_state WHERE key = 'last_pattern_analysis'")
            row = cursor.fetchone()
            last_analysis = datetime.fromisoformat(row[0]) if row else datetime(1970, 1, 1, tzinfo=timezone.utc)
            from_time = last_analysis
        if to_time is None:
            to_time = datetime.now(timezone.utc)

        if from_time >= to_time:
            logger.info("No new logs for pattern analysis")
            return

        event_condition = " OR ".join([f"event_type LIKE '%{et}%'" for et in event_types])
        base_query = f"""
            SELECT id, timestamp, service, event_type, details, task_id
            FROM logs
            WHERE timestamp >= ? AND timestamp < ?
              AND ({event_condition})
        """
        params: List[Any] = [from_time.isoformat(), to_time.isoformat()]
        if service_filter:
            base_query += " AND service = ?"
            params.append(service_filter)
        base_query += " ORDER BY timestamp ASC LIMIT ?"
        params.append(PATTERN_SAMPLE_LIMIT)

        cursor.execute(base_query, params)
        rows = cursor.fetchall()
        if not rows:
            logger.info("No new logs matching criteria")
            return

        sessions: List[List[Any]] = []
        current_session: List[Any] = []
        last_ts: Optional[datetime] = None
        for row in rows:
            ts = datetime.fromisoformat(row['timestamp'])
            task_id = row['task_id']
            if task_id:
                if current_session and (current_session[0]['task_id'] != task_id or
                                        (ts - (last_ts or ts)).total_seconds() > window_seconds):
                    sessions.append(current_session)
                    current_session = []
                current_session.append(row)
                last_ts = ts
            else:
                if current_session and current_session[0]['task_id'] is not None:
                    sessions.append(current_session)
                    current_session = []
                if last_ts is None or (ts - last_ts).total_seconds() > window_seconds:
                    if current_session:
                        sessions.append(current_session)
                        current_session = []
                current_session.append(row)
                last_ts = ts
        if current_session:
            sessions.append(current_session)

        pattern_counts: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(lambda: {"count": 0, "first_seen": None, "last_seen": None, "example": None, "service": None})
        for session in sessions:
            for i in range(len(session) - 1):
                ev1 = session[i]['event_type']
                ev2 = session[i+1]['event_type']
                svc = session[i]['service']
                seq = f"{ev1} → {ev2}"
                ts1 = datetime.fromisoformat(session[i]['timestamp'])
                ts2 = datetime.fromisoformat(session[i+1]['timestamp'])
                key = (seq, svc)
                pattern_counts[key]["count"] += 1
                if pattern_counts[key]["first_seen"] is None or ts1 < pattern_counts[key]["first_seen"]:
                    pattern_counts[key]["first_seen"] = ts1
                if pattern_counts[key]["last_seen"] is None or ts2 > pattern_counts[key]["last_seen"]:
                    pattern_counts[key]["last_seen"] = ts2
                if pattern_counts[key]["example"] is None:
                    pattern_counts[key]["example"] = f"{ev1} → {ev2}"
                pattern_counts[key]["service"] = svc

        pattern_counts = {k: v for k, v in pattern_counts.items() if v["count"] >= min_support}

        if not pattern_counts:
            logger.info("No patterns with sufficient support")
            return

        try:
            for (seq, svc), data in pattern_counts.items():
                cursor.execute("SELECT id, count, first_seen, last_seen FROM patterns WHERE sequence = ? AND service = ?", (seq, svc))
                row = cursor.fetchone()
                if row:
                    new_count = row['count'] + data['count']
                    new_first = min(row['first_seen'], data['first_seen'].isoformat())
                    new_last = max(row['last_seen'], data['last_seen'].isoformat())
                    cursor.execute(
                        "UPDATE patterns SET count = ?, first_seen = ?, last_seen = ? WHERE id = ?",
                        (new_count, new_first, new_last, row['id'])
                    )
                else:
                    cursor.execute(
                        "INSERT INTO patterns (sequence, count, first_seen, last_seen, example, service) VALUES (?, ?, ?, ?, ?, ?)",
                        (seq, data['count'], data['first_seen'].isoformat(), data['last_seen'].isoformat(), data['example'], svc)
                    )
            cursor.execute("UPDATE analysis_state SET value = ? WHERE key = 'last_pattern_analysis'", (to_time.isoformat(),))
        except Exception as e:
            cursor.execute("ROLLBACK")
            logger.error(f"Error updating patterns: {e}")
            raise

        logger.info(f"Updated {len(pattern_counts)} patterns with new logs for job {job_id}")

# --- Планировщики ---
def scheduled_analysis() -> None:
    if is_job_running('pattern_analysis'):
        logger.info("Pattern analysis already running, skipping scheduled run")
        return
    job_id = f"pattern_{uuid.uuid4()}"
    start_job(job_id, 'pattern_analysis', {'scheduled': True})
    try:
        analyze_patterns(job_id=job_id, event_types=['error', 'failed'], min_support=2)
        finish_job(job_id, True, {"message": "Pattern analysis completed"})
        import asyncio
        asyncio.create_task(send_log_to_br18("scheduled_analysis_completed", {"job_id": job_id}))
    except Exception as e:
        logger.error(f"Scheduled pattern analysis failed: {e}")
        finish_job(job_id, False, {"error": str(e)})
        import asyncio
        asyncio.create_task(send_log_to_br18("scheduled_analysis_failed", {"job_id": job_id, "error": str(e)}))

# --- Lifespan для загрузки модели ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _encoder, _model_available
    try:
        _encoder = get_encoder()
        _model_available = True
        logger.info("Embedding model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        _model_available = False
    yield

app = FastAPI(title="Log Analyzer", version="1.0.0", lifespan=lifespan)

# --- Планировщики ---
scheduler = apscheduler.schedulers.background.BackgroundScheduler()
scheduler.add_job(scan_and_process, trigger=IntervalTrigger(seconds=POLL_INTERVAL))
scheduler.add_job(scheduled_analysis, trigger=IntervalTrigger(minutes=30))
scheduler.start()

@app.on_event("shutdown")
def shutdown_event() -> None:
    scheduler.shutdown()

# --- API эндпоинты ---
@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}

class ClusterRequest(BaseModel):
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    service: Optional[str] = None

    @field_validator('from_time', 'to_time', mode='before')
    @classmethod
    def parse_datetime(cls, v: Any) -> Any:
        if v is None or isinstance(v, datetime):
            return v
        if isinstance(v, str):
            if v.endswith('Z'):
                v = v[:-1] + '+00:00'
            return datetime.fromisoformat(v)
        raise ValueError('Invalid datetime format')

@app.post("/cluster")
async def start_clustering(req: ClusterRequest, background_tasks: BackgroundTasks) -> dict:
    if not _model_available:
        raise HTTPException(status_code=503, detail="Embedding model not available")
    if is_job_running('clustering'):
        raise HTTPException(status_code=409, detail="Clustering already in progress")

    job_id = f"cluster_{uuid.uuid4()}"
    params = req.model_dump()
    start_job(job_id, 'clustering', params)

    def run() -> None:
        try:
            cluster_errors(job_id=job_id, from_time=req.from_time, to_time=req.to_time, service_filter=req.service)
            finish_job(job_id, True, {"message": "Clustering completed"})
            background_tasks.add_task(send_log_to_br18, "clustering_completed", {"job_id": job_id})
        except Exception as e:
            logger.error(f"Clustering job {job_id} failed: {e}")
            finish_job(job_id, False, {"error": str(e)})
            background_tasks.add_task(send_log_to_br18, "clustering_failed", {"job_id": job_id, "error": str(e)})

    background_tasks.add_task(run)
    return {"job_id": job_id, "status": "started"}

@app.get("/clusters/statistics")
async def cluster_statistics() -> dict:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM error_clusters")
        total_clusters = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(count) FROM error_clusters")
        total_errors = cursor.fetchone()[0] or 0
        cursor.execute("SELECT pattern, count FROM error_clusters ORDER BY count DESC LIMIT 1")
        top = cursor.fetchone()
        return {
            "total_clusters": total_clusters,
            "total_errors_in_clusters": total_errors,
            "top_cluster": {"pattern": top['pattern'], "count": top['count']} if top else None
        }

@app.get("/clusters")
async def list_clusters(limit: int = 50, offset: int = 0) -> dict:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, pattern, count, last_seen, sample FROM error_clusters ORDER BY count DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = cursor.fetchall()
        return {"clusters": [{"id": r['id'], "pattern": r['pattern'], "count": r['count'], "last_seen": r['last_seen'], "sample": r['sample']} for r in rows]}

@app.get("/clusters/{cluster_id}")
async def get_cluster(cluster_id: int) -> dict:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, pattern, count, last_seen, sample FROM error_clusters WHERE id = ?", (cluster_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cluster not found")
        return {"id": row['id'], "pattern": row['pattern'], "count": row['count'], "last_seen": row['last_seen'], "sample": row['sample']}

class PatternAnalysisRequest(BaseModel):
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    service: Optional[str] = None
    min_support: int = 2
    window_seconds: int = 10
    event_types: List[str] = ['error', 'failed']

    @field_validator('from_time', 'to_time', mode='before')
    @classmethod
    def parse_datetime(cls, v: Any) -> Any:
        if v is None or isinstance(v, datetime):
            return v
        if isinstance(v, str):
            if v.endswith('Z'):
                v = v[:-1] + '+00:00'
            return datetime.fromisoformat(v)
        raise ValueError('Invalid datetime format')

@app.post("/patterns/analyze")
async def run_pattern_analysis(req: PatternAnalysisRequest, background_tasks: BackgroundTasks) -> dict:
    if is_job_running('pattern_analysis'):
        raise HTTPException(status_code=409, detail="Pattern analysis already in progress")

    job_id = f"pattern_{uuid.uuid4()}"
    start_job(job_id, 'pattern_analysis', req.model_dump())

    def run() -> None:
        try:
            analyze_patterns(
                job_id=job_id,
                from_time=req.from_time,
                to_time=req.to_time,
                service_filter=req.service,
                min_support=req.min_support,
                window_seconds=req.window_seconds,
                event_types=req.event_types
            )
            finish_job(job_id, True, {"message": "Pattern analysis completed"})
            background_tasks.add_task(send_log_to_br18, "pattern_analysis_completed", {"job_id": job_id})
        except Exception as e:
            logger.error(f"Pattern analysis job {job_id} failed: {e}")
            finish_job(job_id, False, {"error": str(e)})
            background_tasks.add_task(send_log_to_br18, "pattern_analysis_failed", {"job_id": job_id, "error": str(e)})

    background_tasks.add_task(run)
    return {"job_id": job_id, "status": "started"}

@app.get("/patterns")
async def list_patterns(
    limit: int = 50,
    offset: int = 0,
    min_count: int = 2,
    service: Optional[str] = None,
    from_last_seen: Optional[str] = None
) -> dict:
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT id, sequence, count, first_seen, last_seen, service FROM patterns WHERE count >= ?"
        params: List[Any] = [min_count]
        if service:
            query += " AND service = ?"
            params.append(service)
        if from_last_seen:
            query += " AND last_seen >= ?"
            params.append(from_last_seen)
        query += " ORDER BY count DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return {
            "patterns": [
                {
                    "id": r['id'],
                    "sequence": r['sequence'],
                    "count": r['count'],
                    "first_seen": r['first_seen'],
                    "last_seen": r['last_seen'],
                    "service": r['service']
                }
                for r in rows
            ]
        }

@app.get("/patterns/{pattern_id}")
async def get_pattern(pattern_id: int) -> dict:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, sequence, count, first_seen, last_seen, example, service FROM patterns WHERE id = ?", (pattern_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Pattern not found")
        return {
            "id": row['id'],
            "sequence": row['sequence'],
            "count": row['count'],
            "first_seen": row['first_seen'],
            "last_seen": row['last_seen'],
            "example": row['example'],
            "service": row['service']
        }

@app.get("/jobs")
async def list_jobs(limit: int = 20, offset: int = 0) -> dict:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT job_id, type, status, created_at, completed_at, result FROM analysis_jobs ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = cursor.fetchall()
        return {
            "jobs": [
                {
                    "job_id": r['job_id'],
                    "type": r['type'],
                    "status": r['status'],
                    "created_at": r['created_at'],
                    "completed_at": r['completed_at'],
                    "result": json.loads(r['result']) if r['result'] else None
                }
                for r in rows
            ]
        }