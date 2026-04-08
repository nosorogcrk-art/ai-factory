import re
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Пути к логам (можно расширить)
LOG_DIRS = [
    Path("01_ЦЕХ/01_ЖУРНАЛЫ/dialogue_manager.log"),
    Path("01_ЦЕХ/01_ЖУРНАЛЫ/patch_architect.log"),
    Path("01_ЦЕХ/01_ЖУРНАЛЫ/handover.log"),
    Path("01_ЦЕХ/01_ЖУРНАЛЫ/integrator.log"),
    Path("01_ЦЕХ/01_ЖУРНАЛЫ/skill_integrator.log"),
]
REPORTS_DIR = Path("01_ЦЕХ/МЕТРИКИ/daedalus_reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def parse_log_line(line: str) -> Dict[str, Any]:
    """Парсит строку лога, извлекая timestamp, уровень, сообщение и имя логгера."""
    # Пример формата: 2026-04-07 10:00:00,123 - INFO - Message
    pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d{3} - (\w+) - (.+)$'
    match = re.match(pattern, line)
    if match:
        return {
            "timestamp": datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S"),
            "level": match.group(2),
            "message": match.group(3)
        }
    return None

def analyze_log_file(file_path: Path, since: datetime) -> Dict[str, Any]:
    """Анализирует один лог-файл, возвращает статистику."""
    if not file_path.exists():
        return {"errors": [], "warnings": [], "info_count": 0, "error_count": 0, "warning_count": 0, "duration_ops": []}
    errors = []
    warnings = []
    info_count = 0
    error_count = 0
    warning_count = 0
    duration_ops = []  # список кортежей (операция, длительность)
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            parsed = parse_log_line(line)
            if not parsed:
                continue
            if parsed["timestamp"] < since:
                continue
            if parsed["level"] == "ERROR":
                error_count += 1
                errors.append(parsed["message"])
            elif parsed["level"] == "WARNING":
                warning_count += 1
                warnings.append(parsed["message"])
            elif parsed["level"] == "INFO":
                info_count += 1
                # Попробуем извлечь длительность из сообщений (например, "duration_ms: 123")
                dur_match = re.search(r'duration_ms[=:]\s*(\d+)', parsed["message"])
                if dur_match:
                    duration_ops.append(("unknown", int(dur_match.group(1))))
                # Можно добавить другие паттерны
    return {
        "errors": errors[:20],  # ограничим количество
        "warnings": warnings[:20],
        "info_count": info_count,
        "error_count": error_count,
        "warning_count": warning_count,
        "duration_ops": duration_ops
    }

def generate_report(analysis: Dict[str, Any], period_hours: int) -> Dict[str, Any]:
    """Формирует итоговый отчёт."""
    total_errors = sum(a["error_count"] for a in analysis.values())
    total_warnings = sum(a["warning_count"] for a in analysis.values())
    all_durations = []
    for a in analysis.values():
        all_durations.extend(a["duration_ops"])
    avg_duration = sum(d for _, d in all_durations) / len(all_durations) if all_durations else 0
    top_errors = []
    error_counts = defaultdict(int)
    for a in analysis.values():
        for err in a["errors"]:
            # Группировка по первым 50 символам
            key = err[:50]
            error_counts[key] += 1
    top_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    report = {
        "generated_at": datetime.now().isoformat(),
        "period_hours": period_hours,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "average_duration_ms": avg_duration,
        "top_errors": [{"message": msg, "count": cnt} for msg, cnt in top_errors],
        "by_container": analysis
    }
    return report

async def run_analysis(period_hours: int = 24):
    """Запускает анализ логов за указанный период."""
    since = datetime.now() - timedelta(hours=period_hours)
    logger.info(f"Starting log analysis for last {period_hours} hours")
    analysis = {}
    for log_path in LOG_DIRS:
        analysis[str(log_path.name)] = analyze_log_file(log_path, since)
    report = generate_report(analysis, period_hours)
    report_filename = f"report_{datetime.now().strftime('%Y-%m-%d')}.json"
    report_path = REPORTS_DIR / report_filename
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Report saved to {report_path}")
    return report

async def scheduler_loop(interval_seconds: int = 86400, period_hours: int = 24):
    """Фоновый планировщик, запускающий анализ раз в сутки."""
    while True:
        await run_analysis(period_hours)
        await asyncio.sleep(interval_seconds)

if __name__ == "__main__":
    # Для ручного тестирования
    asyncio.run(run_analysis(24))