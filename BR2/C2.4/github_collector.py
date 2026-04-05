#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
github_collector.py – сбор и обновление репозиториев с GitHub.
"""

import os
import json
import logging
from pathlib import Path
from github import Github
from git import Repo
from datetime import datetime

CONFIG_FILE = Path("00_КАНОН/Внешние_источники/sources.json")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/github_collector.log")
STATE_DIR = Path("00_ПАМЯТЬ/Внешние/state")

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if GITHUB_TOKEN:
    g = Github(GITHUB_TOKEN)
else:
    g = Github()

KEEP_EXTENSIONS = {'.md', '.py', '.js', '.ipynb', '.txt', '.rst'}

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_repo_metadata(repo_url):
    parts = repo_url.rstrip('/').split('/')
    owner, repo_name = parts[-2], parts[-1]
    return owner, repo_name

def meets_criteria(repo, min_stars, license_allow):
    if repo.stargazers_count < min_stars:
        return False
    if license_allow:
        license_name = repo.license.name if repo.license else None
        if license_name not in license_allow:
            return False
    return True

def get_last_commit_sha(repo_path):
    repo = Repo(repo_path)
    return repo.head.commit.hexsha

def load_state(repo_name):
    state_file = STATE_DIR / f"{repo_name}.json"
    if state_file.exists():
        with open(state_file, "r") as f:
            return json.load(f)
    return {"last_commit": None}

def save_state(repo_name, last_commit):
    state_file = STATE_DIR / f"{repo_name}.json"
    with open(state_file, "w") as f:
        json.dump({"last_commit": last_commit, "updated": datetime.now().isoformat()}, f)

def collect_repo(repo_url, branch, min_stars, license_allow, clone_base):
    owner, repo_name = get_repo_metadata(repo_url)
    try:
        repo = g.get_repo(f"{owner}/{repo_name}")
    except Exception as e:
        logging.error(f"Failed to access {repo_url}: {e}")
        return

    if not meets_criteria(repo, min_stars, license_allow):
        logging.info(f"Repo {repo_url} does not meet criteria, skipping.")
        return

    clone_path = Path(clone_base) / f"{owner}_{repo_name}"
    state = load_state(f"{owner}_{repo_name}")
    current_head = None

    if clone_path.exists():
        try:
            local_repo = Repo(clone_path)
            origin = local_repo.remotes.origin
            origin.pull()
            current_head = get_last_commit_sha(clone_path)
            if current_head == state.get("last_commit"):
                logging.info(f"No new commits in {repo_url}")
                return
        except Exception as e:
            logging.error(f"Failed to update {repo_url}: {e}")
            return
    else:
        try:
            local_repo = Repo.clone_from(repo_url, clone_path, branch=branch)
            current_head = get_last_commit_sha(clone_path)
        except Exception as e:
            logging.error(f"Failed to clone {repo_url}: {e}")
            return

    processed_files = []
    for root, _, files in os.walk(clone_path):
        for file in files:
            ext = Path(file).suffix.lower()
            if ext in KEEP_EXTENSIONS:
                src = Path(root) / file
                processed_files.append(str(src))
    logging.info(f"Processed {len(processed_files)} files from {repo_url}")

    save_state(f"{owner}_{repo_name}", current_head)
    return processed_files

def main():
    config = load_config()
    clone_base = config["global"]["clone_dir"]
    Path(clone_base).mkdir(parents=True, exist_ok=True)

    all_files = []
    for repo in config["repositories"]:
        files = collect_repo(
            repo["url"],
            repo.get("branch", "main"),
            repo.get("min_stars", 1000),
            repo.get("license_allow"),
            clone_base
        )
        if files:
            all_files.extend(files)

    if all_files:
        out_file = Path(clone_base) / "latest_batch.json"
        with open(out_file, "w") as f:
            json.dump(all_files, f)
        logging.info(f"Saved list of {len(all_files)} files to {out_file}")

if __name__ == "__main__":
    main()
