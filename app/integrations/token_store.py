from typing import Optional
from app.integrations.supabase import supabase_admin
from app.config import settings


async def get_org_integration(org_id: str, provider: str) -> Optional[dict]:
    result = supabase_admin.table("integrations").select("*") \
        .eq("org_id", org_id).eq("provider", provider).eq("is_active", True) \
        .maybe_single().execute()
    return result.data if result else None


async def get_user_integration(user_id: str, provider: str) -> Optional[dict]:
    result = supabase_admin.table("integrations").select("*") \
        .eq("user_id", user_id).eq("provider", provider).eq("is_active", True) \
        .maybe_single().execute()
    return result.data if result else None


async def upsert_org_integration(org_id: str, provider: str, credentials: dict, metadata: dict = {}) -> dict:
    existing = await get_org_integration(org_id, provider)
    if existing:
        result = supabase_admin.table("integrations").update({
            "credentials": credentials,
            "metadata": metadata,
            "is_active": True
        }).eq("id", existing["id"]).execute()
    else:
        result = supabase_admin.table("integrations").insert({
            "org_id": org_id,
            "provider": provider,
            "credentials": credentials,
            "metadata": metadata
        }).execute()
    return result.data[0]


async def upsert_user_integration(user_id: str, provider: str, credentials: dict, metadata: dict = {}) -> dict:
    existing = await get_user_integration(user_id, provider)
    if existing:
        result = supabase_admin.table("integrations").update({
            "credentials": credentials,
            "metadata": metadata,
            "is_active": True
        }).eq("id", existing["id"]).execute()
    else:
        result = supabase_admin.table("integrations").insert({
            "user_id": user_id,
            "provider": provider,
            "credentials": credentials,
            "metadata": metadata
        }).execute()
    return result.data[0]


async def delete_org_integration(org_id: str, provider: str) -> bool:
    supabase_admin.table("integrations").delete() \
        .eq("org_id", org_id).eq("provider", provider).execute()
    return True


async def delete_user_integration(user_id: str, provider: str) -> bool:
    supabase_admin.table("integrations").delete() \
        .eq("user_id", user_id).eq("provider", provider).execute()
    return True


async def get_clickup_token(org_id: str) -> Optional[str]:
    """Retorna access_token do ClickUp para a org. Fallback para settings."""
    integration = await get_org_integration(org_id, "clickup")
    if integration:
        return integration["credentials"].get("access_token")
    return settings.CLICKUP_API_KEY or None


async def get_google_credentials(user_id: str) -> Optional[dict]:
    """Retorna credentials completo do Google Calendar para o usuário."""
    integration = await get_user_integration(user_id, "google_calendar")
    if integration:
        return integration["credentials"]
    return None


async def update_google_credentials(user_id: str, new_credentials: dict) -> None:
    """Atualiza tokens após refresh automático."""
    integration = await get_user_integration(user_id, "google_calendar")
    if integration:
        supabase_admin.table("integrations").update({
            "credentials": new_credentials
        }).eq("id", integration["id"]).execute()


async def get_openai_key(org_id: str) -> Optional[str]:
    """Retorna API key da OpenAI para a org. Fallback para settings."""
    integration = await get_org_integration(org_id, "openai")
    if integration:
        return integration["credentials"].get("api_key")
    return settings.OPENAI_API_KEY or None
