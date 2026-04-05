#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_integrator.py – заглушка для интегратора навыков.
Возвращает фиктивный промпт на основе переданных параметров.
"""

import logging
from fastapi import FastAPI, HTTPException
from models import CompileRequest, CompileResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Skill Integrator (Stub)", version="0.1.0")

@app.post("/compile", response_model=CompileResponse)
async def compile_prompt(req: CompileRequest):
    logger.info(f"Compile request: {req.dict()}")

    used_skills = []
    if req.required_skills:
        used_skills = req.required_skills[:req.limit]
    else:
        # имитация поиска по типу задачи
        if req.task_type == "refactor":
            used_skills = ["SKILL-042", "SKILL-101"]
        elif req.task_type == "test":
            used_skills = ["SKILL-999"]
        else:
            used_skills = ["SKILL-000"]

    if len(used_skills) > req.limit:
        used_skills = used_skills[:req.limit]

    # формируем промпт (заглушка)
    prompt_lines = ["[STUB] Skill integrator is not fully implemented."]
    for skill in used_skills:
        prompt_lines.append(f"- Instruction from {skill}: stub content")
    prompt = "\n".join(prompt_lines)

    return CompileResponse(
        prompt=prompt,
        used_skills=used_skills,
        warnings=["Skill integrator is a stub"],
        total_matched=len(used_skills),
        returned=len(used_skills)
    )

@app.get("/health")
async def health():
    return {"status": "ok"}
