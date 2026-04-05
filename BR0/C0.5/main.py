import os
import json
import subprocess
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from map_generator import generate_map, save_map

app = FastAPI(title="System Mapper", version="1.2.0")

SYSTEM_MAP_PATH = Path("SYSTEM_MAP.json")
STATIC_DIR = Path("static")

def load_cached_map():
    if SYSTEM_MAP_PATH.exists():
        with open(SYSTEM_MAP_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return generate_map()

def refresh_map():
    map_data = generate_map()
    save_map(map_data)
    return map_data

@app.on_event("startup")
def startup():
    refresh_map()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/map")
async def get_map(refresh: bool = False):
    if refresh:
        map_data = refresh_map()
    else:
        map_data = load_cached_map()
    return map_data

@app.get("/view", response_class=HTMLResponse)
async def view_map():
    """Человеко-читаемая страница карты завода."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>View not available</h1>", status_code=404)

@app.get("/branches")
async def get_branches():
    return load_cached_map().get('branches', [])

@app.get("/containers")
async def get_containers():
    return load_cached_map().get('containers', [])

@app.get("/patches")
async def get_patches():
    return load_cached_map().get('patches', [])

@app.get("/stats")
async def get_stats():
    return load_cached_map().get('stats', {})

@app.get("/ports")
async def get_ports():
    """Вернуть карту портов всех запущенных контейнеров."""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--format', 'json'],
            capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=503, detail="Docker daemon not reachable")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Docker not installed")

    containers_info = []
    port_counter = defaultdict(list)
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        try:
            data = json.loads(line)
        except:
            continue
        name = data.get('Names', 'unknown')
        status = data.get('State', 'unknown')
        ports_raw = data.get('Ports', '') or ''
        ports = []
        seen_ports = set()  # Для отслеживания уникальных портов
        if ports_raw:
            for part in ports_raw.split(', '):
                if '->' in part:
                    external, internal = part.split('->')
                    # Очищаем external от IP-адреса (может быть 0.0.0.0:8101 или [::]:8101)
                    external_port = external.split(':')[-1].replace('[', '').replace(']', '')
                    internal_port = internal.split('/')[0]
                    protocol = internal.split('/')[-1]
                    port_key = f"{external_port}:{internal_port}:{protocol}"
                    if port_key not in seen_ports:
                        seen_ports.add(port_key)
                        ports.append({
                            'external': int(external_port),
                            'internal': int(internal_port),
                            'protocol': protocol,
                            'external_ip': external.split(':')[0] if ':' in external else external
                        })
                        port_counter[external_port].append(name)
        health = 'unknown'
        containers_info.append({
            'name': name,
            'id_short': data.get('ID', '')[:12],
            'status': status,
            'health': health,
            'ports': ports,
            'config': {}
        })
    map_data = load_cached_map()
    container_map = {c['id']: c for c in map_data.get('containers', [])}
    for ci in containers_info:
        parts = ci['name'].split('-')
        if len(parts) >= 3:
            candidate_id = parts[2].upper()
            if candidate_id in container_map:
                ci['config'] = {
                    'container_id': candidate_id,
                    'branch': container_map[candidate_id].get('branch', '')
                }
    # Убираем дубликаты в конфликтах (если один контейнер указан несколько раз для одного порта)
    cleaned_conflicts = []
    for port, containers in port_counter.items():
        unique_containers = list(dict.fromkeys(containers))  # Сохраняем порядок, убираем дубли
        if len(unique_containers) > 1:
            cleaned_conflicts.append({'port': port, 'containers': unique_containers})
    
    return {
        'timestamp': datetime.now().isoformat(),
        'containers': containers_info,
        'conflicts': cleaned_conflicts
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8098"))
    uvicorn.run(app, host="0.0.0.0", port=port)
