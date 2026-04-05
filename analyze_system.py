#!/usr/bin/env python3
"""
Анализатор состояния системы "Цифровая Фабрика"
Проверяет реальное состояние веток, контейнеров, паспортов, Docker-контейнеров
"""

import os
import json
import subprocess
import sys
from pathlib import Path
import yaml
import re

BASE_DIR = Path("/Users/a1/Dev/ЗАВОД_АГЕНТОВ/ai-factory")

def find_branches():
    """Найти все ветки BR* в корневой директории"""
    branches = []
    for item in BASE_DIR.iterdir():
        if item.is_dir() and item.name.startswith("BR") and item.name[2:].isdigit():
            branches.append(item)
    return sorted(branches, key=lambda x: int(x.name[2:]))

def analyze_container(container_path):
    """Проанализировать контейнер"""
    result = {
        "path": str(container_path),
        "name": container_path.name,
        "has_passport": False,
        "passport_data": None,
        "has_code": False,
        "has_tests": False,
        "has_dockerfile": False,
        "has_requirements": False,
        "files": [],
        "test_files": []
    }
    
    # Проверить наличие паспорта
    passport_file = container_path / f"{container_path.name}.md"
    if passport_file.exists():
        result["has_passport"] = True
        # Попробовать прочитать YAML-шапку
        content = passport_file.read_text(encoding='utf-8', errors='ignore')
        if content.startswith("---"):
            try:
                yaml_end = content.find("\n---", 3)
                if yaml_end != -1:
                    yaml_content = content[3:yaml_end].strip()
                    passport_data = yaml.safe_load(yaml_content)
                    result["passport_data"] = passport_data
            except:
                pass
    
    # Проверить наличие кода
    for file in container_path.rglob("*.py"):
        if file.is_file():
            result["has_code"] = True
            result["files"].append(str(file.relative_to(container_path)))
    
    # Проверить наличие тестов
    test_dir = container_path / "tests"
    if test_dir.exists():
        for file in test_dir.rglob("test_*.py"):
            if file.is_file():
                result["has_tests"] = True
                result["test_files"].append(str(file.relative_to(container_path)))
    
    # Проверить Dockerfile
    if (container_path / "Dockerfile").exists():
        result["has_dockerfile"] = True
    
    # Проверить requirements.txt
    if (container_path / "requirements.txt").exists():
        result["has_requirements"] = True
    
    return result

def analyze_branch(branch_path):
    """Проанализировать ветку"""
    result = {
        "path": str(branch_path),
        "name": branch_path.name,
        "containers": [],
        "has_branch_md": False
    }
    
    # Проверить наличие BR*.md
    branch_md = branch_path / f"{branch_path.name}.md"
    if branch_md.exists():
        result["has_branch_md"] = True
    
    # Найти контейнеры
    for item in branch_path.iterdir():
        if item.is_dir() and item.name.startswith("C") and "." in item.name:
            container_result = analyze_container(item)
            result["containers"].append(container_result)
    
    return result

def get_docker_containers():
    """Получить список запущенных Docker-контейнеров"""
    try:
        cmd = ["docker", "ps", "--format", "{{.Names}}||{{.Status}}||{{.Ports}}"]
        output = subprocess.check_output(cmd, text=True)
        containers = []
        for line in output.strip().split("\n"):
            if line:
                parts = line.split("||")
                if len(parts) >= 3:
                    name, status, ports = parts[0], parts[1], parts[2]
                    # Определить health
                    healthy = "healthy" in status.lower()
                    unhealthy = "unhealthy" in status.lower()
                    health_status = "healthy" if healthy else "unhealthy" if unhealthy else "unknown"
                    
                    containers.append({
                        "name": name,
                        "status": status,
                        "ports": ports,
                        "health": health_status
                    })
        return containers
    except Exception as e:
        print(f"Ошибка при получении Docker-контейнеров: {e}")
        return []

def check_health_endpoints(containers):
    """Проверить healthcheck эндпоинты"""
    import requests
    import time
    
    results = []
    for container in containers:
        # Извлечь порт из строки портов
        ports = container["ports"]
        port_match = re.search(r':(\d+)->', ports)
        if port_match:
            port = int(port_match.group(1))
            url = f"http://localhost:{port}/health"
            try:
                response = requests.get(url, timeout=2)
                status = "ok" if response.status_code == 200 else f"error_{response.status_code}"
                results.append({
                    "container": container["name"],
                    "port": port,
                    "url": url,
                    "status": status,
                    "response": response.json() if response.status_code == 200 else None
                })
            except Exception as e:
                results.append({
                    "container": container["name"],
                    "port": port,
                    "url": url,
                    "status": "error",
                    "error": str(e)
                })
        time.sleep(0.1)  # Небольшая задержка
    
    return results

def main():
    print("🔍 Анализ системы 'Цифровая Фабрика'")
    print("=" * 60)
    
    # 1. Найти ветки
    branches = find_branches()
    print(f"Найдено веток: {len(branches)}")
    
    # 2. Проанализировать каждую ветку
    branch_results = []
    total_containers = 0
    containers_with_passport = 0
    containers_with_tests = 0
    containers_with_dockerfile = 0
    
    for branch_path in branches:
        print(f"\nАнализ ветки: {branch_path.name}")
        branch_result = analyze_branch(branch_path)
        branch_results.append(branch_result)
        
        for container in branch_result["containers"]:
            total_containers += 1
            if container["has_passport"]:
                containers_with_passport += 1
            if container["has_tests"]:
                containers_with_tests += 1
            if container["has_dockerfile"]:
                containers_with_dockerfile += 1
    
    # 3. Получить Docker-контейнеры
    print("\n📦 Проверка Docker-контейнеров...")
    docker_containers = get_docker_containers()
    print(f"Запущено Docker-контейнеров: {len(docker_containers)}")
    
    # 4. Проверить healthcheck
    print("🏥 Проверка healthcheck эндпоинтов...")
    health_results = check_health_endpoints(docker_containers)
    
    # 5. Создать отчёт
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "statistics": {
            "total_branches": len(branches),
            "total_containers": total_containers,
            "containers_with_passport": containers_with_passport,
            "containers_with_tests": containers_with_tests,
            "containers_with_dockerfile": containers_with_dockerfile,
            "docker_containers_running": len(docker_containers),
            "docker_containers_healthy": sum(1 for c in docker_containers if c["health"] == "healthy"),
            "docker_containers_unhealthy": sum(1 for c in docker_containers if c["health"] == "unhealthy")
        },
        "branches": branch_results,
        "docker_containers": docker_containers,
        "health_checks": health_results
    }
    
    # Сохранить отчёт в JSON
    report_file = BASE_DIR / "system_analysis_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Отчёт сохранён в: {report_file}")
    
    # Вывести сводку
    print("\n" + "=" * 60)
    print("📊 СВОДКА АНАЛИЗА")
    print("=" * 60)
    print(f"Ветки (BR): {len(branches)}")
    print(f"Контейнеры (C): {total_containers}")
    print(f"  • С паспортом: {containers_with_passport}")
    print(f"  • С тестами: {containers_with_tests}")
    print(f"  • С Dockerfile: {containers_with_dockerfile}")
    print(f"Docker-контейнеры запущено: {len(docker_containers)}")
    print(f"  • Healthy: {sum(1 for c in docker_containers if c['health'] == 'healthy')}")
    print(f"  • Unhealthy: {sum(1 for c in docker_containers if c['health'] == 'unhealthy')}")
    
    # Вывести список unhealthy контейнеров
    unhealthy = [c for c in docker_containers if c["health"] == "unhealthy"]
    if unhealthy:
        print("\n⚠️  Unhealthy контейнеры:")
        for c in unhealthy:
            print(f"  • {c['name']} - {c['status']}")

if __name__ == "__main__":
    import time
    import requests
    main()