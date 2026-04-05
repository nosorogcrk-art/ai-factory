import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
import models
import storage

app = FastAPI(title="Registry Manager", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/branches", response_model=models.BranchInDB)
def create_branch(branch: models.BranchCreate):
    branch_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow()
    new_branch = models.BranchInDB(
        id=branch_id,
        created_at=now,
        updated_at=now,
        soft_deleted=False,
        **branch.dict()
    )
    storage.create_branch(branch_id, new_branch)
    return new_branch

@app.get("/branches", response_model=list[models.BranchInDB])
def list_branches(include_deleted: bool = Query(False)):
    all_branches = storage.get_branches()
    if include_deleted:
        return list(all_branches.values())
    return [b for b in all_branches.values() if not b.soft_deleted]

@app.get("/branches/{branch_id}", response_model=models.BranchInDB)
def get_branch(branch_id: str):
    branch = storage.get_branch(branch_id)
    if not branch or branch.soft_deleted:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch

@app.put("/branches/{branch_id}", response_model=models.BranchInDB)
def update_branch(branch_id: str, update: models.BranchUpdate):
    branch = storage.get_branch(branch_id)
    if not branch or branch.soft_deleted:
        raise HTTPException(status_code=404, detail="Branch not found")

    update_data = update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(branch, field, value)
    branch.updated_at = datetime.utcnow()
    storage.update_branch(branch_id, branch)
    return branch

@app.patch("/branches/{branch_id}", response_model=models.BranchInDB)
def patch_branch(branch_id: str, update: models.BranchUpdate):
    branch = storage.get_branch(branch_id)
    if not branch or branch.soft_deleted:
        raise HTTPException(status_code=404, detail="Branch not found")

    update_data = update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(branch, field, value)
    branch.updated_at = datetime.utcnow()
    storage.update_branch(branch_id, branch)
    return branch

@app.delete("/branches/{branch_id}")
def delete_branch(branch_id: str, hard: bool = Query(False)):
    try:
        storage.delete_branch(branch_id, hard)
        return {"message": "Branch deleted" if hard else "Branch soft-deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
