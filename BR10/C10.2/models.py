from pydantic import BaseModel, Field, validator
import re
from pathlib import Path

class TestRequest(BaseModel):
    product_path: str = Field(default="/app/02_ПРОДУКТ/РЕПО")
    test_suite: str = Field(default="tests")
    image: str = Field(default="python:3.12-slim")
    timeout_seconds: int = Field(default=600, ge=1, le=3600)

    @validator('product_path')
    def validate_path(cls, v):
        p = Path(v)
        if not p.is_absolute():
            raise ValueError("product_path must be absolute")
        if not p.exists():
            raise ValueError(f"product_path does not exist: {v}")
        return str(v)

    @validator('test_suite')
    def validate_suite(cls, v):
        if not re.match(r'^[a-zA-Z0-9_./]+$', v):
            raise ValueError("test_suite must contain only alphanumeric, underscore, dot or slash")
        return v