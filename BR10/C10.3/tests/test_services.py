import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from services import generate_metadata, create_archive, build_docs, generate_release_notes

def test_generate_metadata():
    skills = ["SKILL-001"]
    meta = generate_metadata("v1.0.0", skills)
    assert meta["product_version"] == "v1.0.0"
    assert meta["skills"] == skills
    assert "build_date" in meta

def test_create_archive(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "file.txt").write_text("test")
    output = tmp_path / "out"
    archive = create_archive(source, "v1.0.0", output)
    assert archive.exists()
    assert archive.name == "product-v1.0.0.tar.gz"

def test_build_docs_no_config(tmp_path):
    result = build_docs(tmp_path, tmp_path, "v1.0.0")
    assert result is None

@patch("subprocess.run")
def test_build_docs_success(mock_run, tmp_path):
    config = tmp_path / "mkdocs.yml"
    config.write_text("site_name: test")
    output_base = tmp_path / "releases"
    result = build_docs(tmp_path, output_base, "v1.0.0")
    assert result == output_base / "docs-v1.0.0"
    mock_run.assert_called_once()

@patch("git.Repo")
@pytest.mark.skip(reason="git module not installed")
def test_generate_release_notes_success(mock_repo, tmp_path):
    repo_instance = MagicMock()
    repo_instance.bare = False
    mock_repo.return_value = repo_instance

    commit1 = MagicMock()
    commit1.message = "P10.3.14: add service\n"
    commit1.hexsha = "abc123"
    commit2 = MagicMock()
    commit2.message = "IMP-20260327-001\n"
    commit2.hexsha = "def456"
    repo_instance.iter_commits.return_value = [commit1, commit2]

    output = tmp_path / "RELEASE_NOTES.md"
    result = generate_release_notes(tmp_path, "v1.0.0", output_file=output)
    assert result == output
    text = output.read_text()
    assert "P10.3.14" in text
    assert "IMP-20260327-001" in text
