from fastapi import FastAPI

app = FastAPI()

@app.get("/costs")
async def get_costs():
    return {
        "total_tokens": 12345,
        "total_cost_usd": 0.15,
        "by_task": {
            "TEST-001": 5000,
            "TEST-002": 7345
        }
    }

@app.get("/health")
async def health():
    return {"status": "ok"}
