#!/usr/bin/env python3
"""
Проверка доступных API эндпоинтов системы
"""

import requests
import json
import time
from pathlib import Path

BASE_DIR = Path("/Users/a1/Dev/ЗАВОД_АГЕНТОВ/ai-factory")

# Ключевые API эндпоинты для проверки
API_ENDPOINTS = [
    # C1.2 Patch Architect
    {"name": "C1.2 /api/decompose", "url": "http://localhost:8085/api/decompose", "method": "POST", "data": {"description": "test", "context": {}}},
    
    # C9.4 Dialogue Manager
    {"name": "C9.4 /api/dialog", "url": "http://localhost:8112/api/dialog", "method": "POST", "data": {"message": "test", "session_id": "test_session"}},
    
    # C2.6 Project Memory (Indexer)
    {"name": "C2.6 /api/index", "url": "http://localhost:8108/api/index", "method": "POST", "data": {"text": "test", "metadata": {}}},
    
    # C2.3 Semantic Search
    {"name": "C2.3 /api/search", "url": "http://localhost:8108/api/search", "method": "POST", "data": {"query": "test", "limit": 5}},
    
    # C0.5 System Mapper
    {"name": "C0.5 /map", "url": "http://localhost:8101/map", "method": "GET"},
    
    # C17.1 Skill Registry
    {"name": "C17.1 /skills", "url": "http://localhost:8088/skills", "method": "GET"},
    
    # C10.1 Integrator
    {"name": "C10.1 /health", "url": "http://localhost:8096/health", "method": "GET"},
    
    # C19.4 A/B Tester
    {"name": "C19.4 /health", "url": "http://localhost:8106/health", "method": "GET"},
    
    # C20.3 Deployment Executor
    {"name": "C20.3 /health", "url": "http://localhost:8203/health", "method": "GET"},
    
    # C20.4 Test Runner
    {"name": "C20.4 /health", "url": "http://localhost:8204/health", "method": "GET"},
]

def check_endpoint(endpoint):
    """Проверить один эндпоинт"""
    result = {
        "name": endpoint["name"],
        "url": endpoint["url"],
        "method": endpoint.get("method", "GET"),
        "status": "unknown",
        "status_code": None,
        "response_time": None,
        "error": None,
        "response_sample": None
    }
    
    try:
        start_time = time.time()
        if endpoint.get("method") == "POST":
            data = endpoint.get("data", {})
            headers = {"Content-Type": "application/json"}
            response = requests.post(endpoint["url"], json=data, headers=headers, timeout=5)
        else:
            response = requests.get(endpoint["url"], timeout=5)
        
        response_time = time.time() - start_time
        result["response_time"] = round(response_time, 3)
        result["status_code"] = response.status_code
        
        if response.status_code == 200:
            result["status"] = "ok"
            try:
                result["response_sample"] = response.json()
            except:
                result["response_sample"] = response.text[:200]
        elif response.status_code == 404:
            result["status"] = "not_found"
        elif response.status_code >= 500:
            result["status"] = "server_error"
        else:
            result["status"] = f"http_{response.status_code}"
            
    except requests.exceptions.ConnectionError:
        result["status"] = "connection_error"
        result["error"] = "Connection refused"
    except requests.exceptions.Timeout:
        result["status"] = "timeout"
        result["error"] = "Request timeout"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    return result

def main():
    print("🔌 Проверка API эндпоинтов системы")
    print("=" * 60)
    
    results = []
    for endpoint in API_ENDPOINTS:
        print(f"Проверка {endpoint['name']}...", end=" ")
        result = check_endpoint(endpoint)
        results.append(result)
        
        if result["status"] == "ok":
            print(f"✅ OK ({result['response_time']}s)")
        elif result["status"] == "not_found":
            print(f"❌ 404 Not Found")
        elif result["status"] == "connection_error":
            print(f"🔌 Connection Error")
        else:
            print(f"⚠️ {result['status']}")
        
        time.sleep(0.2)  # Небольшая задержка между запросами
    
    # Сохранить результаты
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "endpoints": results
    }
    
    report_file = BASE_DIR / "api_check_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Отчёт сохранён в: {report_file}")
    
    # Вывести сводку
    print("\n" + "=" * 60)
    print("📊 СВОДКА ПРОВЕРКИ API")
    print("=" * 60)
    
    ok_count = sum(1 for r in results if r["status"] == "ok")
    error_count = sum(1 for r in results if r["status"] != "ok")
    
    print(f"Всего проверено: {len(results)}")
    print(f"✅ Работают: {ok_count}")
    print(f"⚠️  Проблемы: {error_count}")
    
    if error_count > 0:
        print("\n🔧 Проблемные эндпоинты:")
        for r in results:
            if r["status"] != "ok":
                print(f"  • {r['name']}: {r['status']} ({r.get('error', '')})")

if __name__ == "__main__":
    main()