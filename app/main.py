from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.api import auth, tasks, spaces, members, invites, chat, integrations

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"🚀 {settings.APP_NAME} starting...")
    yield
    # Shutdown
    print(f"👋 {settings.APP_NAME} shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan
)

# CORS
allowed_origins = [settings.FRONTEND_URL] if settings.FRONTEND_URL else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(spaces.router, prefix="/api/spaces", tags=["Spaces"])
app.include_router(members.router, prefix="/api/members", tags=["Members"])
app.include_router(invites.router, prefix="/api/invites", tags=["Invites"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["Integrations"])

@app.get("/health")
async def health():
    return {"status": "healthy", "app": settings.APP_NAME}
