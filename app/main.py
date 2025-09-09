from fastapi import FastAPI
from app.api.api import api_router

app = FastAPI(
    title="Airdrop Manager API",
    description="API for managing crypto airdrop projects and tasks.",
    version="0.1.0",
)

@app.get("/")
def read_root():
    return {"message": "Welcome to Airdrop Manager API"}

app.include_router(api_router, prefix="/api/v1")

