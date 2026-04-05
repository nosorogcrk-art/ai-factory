import pytest
import json
from pathlib import Path
from map_generator import generate_map, save_map

def test_generate_map(tmp_path):
    branch_dir = tmp_path / "BR0"
    branch_dir.mkdir()
    branch_passport = branch_dir / "BR0.md"
    branch_passport.write_text("""---
id: BR0
name: Test Branch
responsible: TEST
status: active
containers: ["C0.1"]
---
""", encoding='utf-8')
    container_dir = branch_dir / "C0.1"
    container_dir.mkdir()
    container_passport = container_dir / "C0.1.md"
    container_passport.write_text("""---
id: C0.1
branch: BR0
name: Test Container
responsible: TEST
status: planned
dependencies: []
---
""", encoding='utf-8')
    map_data = generate_map(tmp_path)
    assert map_data['stats']['total_branches'] == 1
    assert map_data['stats']['total_containers'] == 1
    assert map_data['branches'][0]['id'] == 'BR0'
    assert map_data['containers'][0]['id'] == 'C0.1'

def test_save_map(tmp_path):
    map_data = {'test': 'data'}
    output = tmp_path / "map.json"
    save_map(map_data, output)
    with open(output, 'r') as f:
        loaded = json.load(f)
    assert loaded == map_data