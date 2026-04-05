from pydantic import BaseModel

class CommandRequest(BaseModel):
    command: str

class CommandResponse(BaseModel):
    success: bool
    output: str