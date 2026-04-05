import pytest
from pathlib import Path
from branch_scanner import load_branch_passport, scan_branches

def test_load_branch_passport(tmp_path):
    passport_file = tmp_path / "BR0.md"
    content = """---
id: BR0
name: Infrastructure
responsible: ГЕРМЕС
status: active
containers: ["C0.1", "C0.2"]
---
# Markdown content
"""
    passport_file.write_text(content, encoding='utf-8')
    data = load_branch_passport(passport_file)
    assert data['id'] == 'BR0'
    assert data['name'] == 'Infrastructure'
    assert data['containers'] == ['C0.1', 'C0.2']

def test_load_branch_passport_missing_frontmatter(tmp_path):
    passport_file = tmp_path / "BR0.md"
    passport_file.write_text("# No frontmatter", encoding='utf-8')
    with pytest.raises(ValueError, match="Missing YAML frontmatter"):
        load_branch_passport(passport_file)

def test_scan_branches(tmp_path):
    branch_dir = tmp_path / "BR0"
    branch_dir.mkdir()
    passport = branch_dir / "BR0.md"
    passport.write_text("""---
id: BR0
name: Test
responsible: TEST
status: active
containers: []
---
""", encoding='utf-8')
    branches = scan_branches(tmp_path)
    assert len(branches) == 1
    assert branches[0]['id'] == 'BR0'