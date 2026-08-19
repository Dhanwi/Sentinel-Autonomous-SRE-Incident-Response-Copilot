import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from app.routers import health, chat

load_dotenv()

app = FastAPI(
    title="Sentinel API",
    description="Backend for the Sentinel incident-response copilot.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)

# from app.routers import chat, incidents
# app.include_router(chat.router)
# app.include_router(incidents.router)