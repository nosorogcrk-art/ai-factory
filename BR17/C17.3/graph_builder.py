import asyncio
import httpx
import logging
from collections import defaultdict
from typing import Dict, List

logger = logging.getLogger(__name__)

class SkillGraph:
    def __init__(self, registry_url: str):
        self.registry_url = registry_url.rstrip('/')
        self.outgoing: Dict[str, List[str]] = defaultdict(list)
        self.incoming: Dict[str, List[str]] = defaultdict(list)
        self.skills_meta: Dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def update(self):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.registry_url}/skills", params={"include_deleted": False, "limit": 1000})
                resp.raise_for_status()
                skills = resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch skills: {e}")
            return

        new_outgoing = defaultdict(list)
        new_incoming = defaultdict(list)
        new_meta = {}

        for skill in skills:
            skill_id = skill["id"]
            new_meta[skill_id] = skill
            for dep in skill.get("depends_on", []):
                if dep:
                    new_outgoing[skill_id].append(dep)
                    new_incoming[dep].append(skill_id)

        async with self._lock:
            self.outgoing = new_outgoing
            self.incoming = new_incoming
            self.skills_meta = new_meta
            logger.info(f"Graph updated: {len(self.skills_meta)} skills, {sum(len(v) for v in self.outgoing.values())} edges")

    def get_graph(self):
        nodes = [{"id": sid, "name": meta.get("name", sid), "version": meta.get("version", ""), "status": meta.get("status", "")}
                 for sid, meta in self.skills_meta.items()]
        edges = [{"source": src, "target": tgt} for src, tgts in self.outgoing.items() for tgt in tgts]
        return {"nodes": nodes, "edges": edges}

    def get_dependencies(self, skill_id: str, transitive: bool = False) -> List[str]:
        if not transitive:
            return self.outgoing.get(skill_id, [])
        visited = set()
        queue = self.outgoing.get(skill_id, [])[:]
        deps = []
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            deps.append(current)
            queue.extend(self.outgoing.get(current, []))
        return deps

    def get_reverse_dependencies(self, skill_id: str) -> List[str]:
        return self.incoming.get(skill_id, [])

    def detect_cycles(self) -> List[List[str]]:
        visited = {}
        cycles = []

        def dfs(node, path):
            if node in visited:
                if visited[node] == 1:
                    start = path.index(node)
                    cycles.append(path[start:] + [node])
                return
            visited[node] = 1
            path.append(node)
            for neighbor in self.outgoing.get(node, []):
                dfs(neighbor, path)
            visited[node] = 2
            path.pop()

        for node in self.outgoing:
            if node not in visited:
                dfs(node, [])
        return cycles