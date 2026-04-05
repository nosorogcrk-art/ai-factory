#!/usr/bin/env python3
import json
import sys
import re
from pathlib import Path

def main():
    patch_id = sys.argv[1] if len(sys.argv) > 1 else "TEST-001"
    patch_file = Path("01_ЦЕХ/ТЕКУЩИЕ_ЗАДАЧИ/task_registry.json")
    if not patch_file.exists():
        print(json.dumps({"error": "No tasks found"}))
        sys.exit(1)

    with open(patch_file) as f:
        tasks = json.load(f)
    for task in tasks:
        if task["id"] == patch_id:
            links = re.findall(r'\[\[([A-Z0-9\-_]+)\]\]', task.get("description", ""))
            print(json.dumps({"patch_id": patch_id, "links": links}))
            return
    print(json.dumps({"patch_id": patch_id, "links": []}))

if __name__ == "__main__":
    main()
