"""
Bundlbite Backend — FastAPI Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import chat, orders
from backend.routers import compare

app = FastAPI(
    title="Bundlbite API",
    description="AI-powered group food ordering backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(orders.router, prefix="/orders", tags=["orders"])
app.include_router(compare.router, prefix="/compare", tags=["compare"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "bundlbite-backend"}
