#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
project_scanner.py – сканирование проектов из 01_ЦЕХ/ПРОЕКТЫ/
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from logger import logger

def scan_projects(root_dir: Path) -> List[Dict[str, Any]]:
    """
    Сканирует папку проектов и возвращает список проектов.
    
    Args:
        root_dir: Корневая директория завода
        
    Returns:
        Список словарей с информацией о проектах
    """
    projects_dir = root_dir / "01_ЦЕХ" / "ПРОЕКТЫ"
    if not projects_dir.exists():
        logger.warning(f"Директория проектов не найдена: {projects_dir}")
        return []
    
    projects = []
    
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        
        project_id = project_dir.name
        if not project_id.startswith("proj_"):
            continue
        
        metadata_path = project_dir / "metadata.json"
        project_data = {
            "id": project_id,
            "path": str(project_dir.relative_to(root_dir)),
            "created_at": None,
            "updated_at": None,
            "name": project_id,
            "description": "",
            "status": "active",
            "branches": [],
            "containers": [],
            "patches": 0
        }
        
        # Чтение metadata.json если существует
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # Обновляем данные из metadata
                project_data.update({
                    "name": metadata.get("name", project_id),
                    "description": metadata.get("description", ""),
                    "status": metadata.get("status", "active"),
                    "created_at": metadata.get("created_at"),
                    "updated_at": metadata.get("updated_at")
                })
            except Exception as e:
                logger.error(f"Ошибка чтения {metadata_path}: {e}")
        
        # Подсчет веток, контейнеров и патчей
        branches_dir = project_dir / "branches"
        containers_dir = project_dir / "containers"
        specs_dir = project_dir / "specs"
        
        if branches_dir.exists():
            project_data["branches"] = [
                f.name for f in branches_dir.iterdir() 
                if f.is_file() and f.name.endswith(".md") and f.name.startswith("BR-")
            ]
        
        if containers_dir.exists():
            project_data["containers"] = [
                f.name for f in containers_dir.iterdir() 
                if f.is_file() and f.name.endswith(".md") and f.name.startswith("C")
            ]
        
        if specs_dir.exists():
            project_data["patches"] = len([
                f for f in specs_dir.iterdir() 
                if f.is_file() and f.name.endswith(".md") and f.name.startswith("P-")
            ])
        
        projects.append(project_data)
    
    logger.info(f"Найдено проектов: {len(projects)}")
    return projects

def get_projects_stats(projects: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Собирает статистику по проектам.
    
    Args:
        projects: Список проектов
        
    Returns:
        Словарь со статистикой
    """
    total_projects = len(projects)
    active_projects = sum(1 for p in projects if p.get("status") == "active")
    archived_projects = sum(1 for p in projects if p.get("status") == "archived")
    
    total_branches = sum(len(p.get("branches", [])) for p in projects)
    total_containers = sum(len(p.get("containers", [])) for p in projects)
    total_patches = sum(p.get("patches", 0) for p in projects)
    
    return {
        "total_projects": total_projects,
        "active_projects": active_projects,
        "archived_projects": archived_projects,
        "total_branches_in_projects": total_branches,
        "total_containers_in_projects": total_containers,
        "total_patches_in_projects": total_patches
    }

if __name__ == "__main__":
    from branch_scanner import get_root_dir
    root = get_root_dir()
    projects = scan_projects(root)
    print(f"Найдено проектов: {len(projects)}")
    for p in projects[:3]:  # Показать первые 3
        print(f"  - {p['id']}: {p['name']} (статус: {p['status']})")