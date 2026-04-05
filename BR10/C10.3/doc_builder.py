#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import subprocess
import sys
import logging
import shutil
from pathlib import Path
from datetime import datetime

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/doc_builder.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def build_docs(source_dir: Path, output_dir: Path, builder: str = "html"):
    config_file = source_dir / "mkdocs.yml"
    if not config_file.exists():
        logging.error(f"MkDocs config not found: {config_file}")
        return False

    if not shutil.which("mkdocs"):
        logging.error("mkdocs not found in PATH")
        return False

    cmd = ["mkdocs", "build", "-f", str(config_file), "-d", str(output_dir)]
    try:
        logging.info(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logging.info("Documentation built successfully.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Build failed: {e.stderr}")
        return False

def main():
    data = json.load(sys.stdin)
    source = Path(data.get("source", "02_ПРОДУКТ/РЕПО/docs"))
    output_base = Path(data.get("output", "02_ПРОДУКТ/РЕЛИЗЫ/docs"))
    builder = data.get("builder", "html")

    version = data.get("version", datetime.now().strftime("%Y%m%d"))
    output_dir = output_base / f"docs-{version}"

    if build_docs(source, output_dir, builder):
        result = {"status": "ok", "output": str(output_dir)}
        print(json.dumps(result))
    else:
        print(json.dumps({"status": "error"}))
        sys.exit(1)

if __name__ == "__main__":
    main()
