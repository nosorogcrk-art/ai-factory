import pytest
from pathlib import Path
from container_scanner import load_container_passport, scan_containers

def test_load_container_passport(tmp_path):
    container_dir = tmp_path / "C1.2"
    container_dir.mkdir()
    passport = container_dir / "C1.2.md"
    content = """---
id: C1.2
branch: BR1
name: Test Container
responsible: TEST
status: planned
dependencies: ["C2.6"]
---
# Content
"""
    passport.write_text(content, encoding='utf-8')
    (container_dir / "Dockerfile").touch()
    data = load_container_passport(passport)
    assert data['id'] == 'C1.2'
    assert data['has_dockerfile'] is True
    assert data['has_tests'] is False

def test_scan_containers(tmp_path):
    branch_dir = tmp_path / "BR1"
    branch_dir.mkdir()
    container_dir = branch_dir / "C1.2"
    container_dir.mkdir()
    passport = container_dir / "C1.2.md"
    passport.write_text("""---
id: C1.2
branch: BR1
name: Test
responsible: TEST
status: planned
dependencies: []
---
""", encoding='utf-8')
    containers = scan_containers(tmp_path)
    assert len(containers) == 1
    assert containers[0]['id'] == 'C1.2'