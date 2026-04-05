import os
import json
import git
from pathlib import Path
from datetime import datetime

REPO_PATH = Path("/data/skills-repo")

def get_repo():
    if not REPO_PATH.exists():
        REPO_PATH.mkdir(parents=True)
        repo = git.Repo.init(REPO_PATH)
        readme = REPO_PATH / "README.md"
        readme.write_text("# Skills Repository\n")
        repo.index.add(["README.md"])
        repo.index.commit("Initial commit")
    else:
        repo = git.Repo(REPO_PATH)
    return repo

def commit_skill(skill_id: str, content: dict, message: str) -> str:
    repo = get_repo()
    file_path = REPO_PATH / f"{skill_id}.json"
    file_path.write_text(json.dumps(content, indent=2, ensure_ascii=False))
    repo.index.add([str(file_path.relative_to(REPO_PATH))])
    commit = repo.index.commit(message)
    return commit.hexsha

def get_history(skill_id: str) -> list:
    repo = get_repo()
    file_path = REPO_PATH / f"{skill_id}.json"
    if not file_path.exists():
        return []
    commits = list(repo.iter_commits(paths=str(file_path.relative_to(REPO_PATH))))
    history = []
    for c in commits:
        history.append({
            "hash": c.hexsha,
            "author": str(c.author),
            "date": datetime.fromtimestamp(c.committed_date).isoformat(),
            "message": c.message.strip()
        })
    return history

def get_file_content(skill_id: str, ref: str) -> dict:
    repo = get_repo()
    file_path = REPO_PATH / f"{skill_id}.json"
    try:
        content = repo.git.show(f"{ref}:{file_path.relative_to(REPO_PATH)}")
        return json.loads(content)
    except git.exc.GitCommandError:
        return None

def get_diff(skill_id: str, from_hash: str, to_hash: str) -> str:
    repo = get_repo()
    file_path = REPO_PATH / f"{skill_id}.json"
    diff = repo.git.diff(from_hash, to_hash, '--', str(file_path.relative_to(REPO_PATH)))
    return diff

def rollback(skill_id: str, to_hash: str) -> str:
    repo = get_repo()
    file_path = REPO_PATH / f"{skill_id}.json"
    content = get_file_content(skill_id, to_hash)
    if content is None:
        raise ValueError("Commit not found")
    file_path.write_text(json.dumps(content, indent=2, ensure_ascii=False))
    repo.index.add([str(file_path.relative_to(REPO_PATH))])
    commit = repo.index.commit(f"Rollback to {to_hash}")
    return commit.hexsha