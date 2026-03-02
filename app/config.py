import os
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # App
    APP_NAME: str = "TaskFlow Manager"
    DEBUG: bool = True
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_KEY: str
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    
    # LangSmith (observabilidade)
    LANGCHAIN_TRACING_V2: str = "true"
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "taskflow-manager"
    
    # ClickUp
    CLICKUP_API_KEY: str = ""
    
    # Google Calendar
    GOOGLE_CREDENTIALS_JSON: str = ""
    
    # Email (Resend)
    RESEND_API_KEY: str = ""
    
    # Redis (para Celery)
    REDIS_URL: str = "redis://localhost:6379"
    
    # Frontend URL (para links de convite)
    FRONTEND_URL: str = "http://localhost:3000"
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()

# Configurar LangSmith
os.environ["LANGCHAIN_TRACING_V2"] = settings.LANGCHAIN_TRACING_V2
os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
