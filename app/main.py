"""AMDHack — FastAPI backbone.

Idea-agnostic skeleton: health check + a Fireworks-backed chat endpoint.
Swap/extend routes once the product concept is locked.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.fireworks import chat, DEFAULT_MODEL

app = FastAPI(title="AMDHack", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    system: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "default_model": DEFAULT_MODEL}


@app.post("/api/chat")
def api_chat(req: ChatRequest) -> dict:
    return chat(req.message, model=req.model, system=req.system)
