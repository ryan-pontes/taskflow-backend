import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow

from app.api.auth import get_current_user
from app.config import settings
from app.integrations.token_store import (
    get_org_integration,
    get_user_integration,
    upsert_org_integration,
    upsert_user_integration,
    delete_org_integration,
    delete_user_integration,
)
from app.models.schemas import OpenAIKeyConfig, IntegrationStatus, IntegrationsStatusResponse

router = APIRouter()

GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


# ─────────────────────────────────────────────
# ClickUp OAuth
# ─────────────────────────────────────────────

@router.get("/clickup/auth")
async def clickup_auth(user: dict = Depends(get_current_user)):
    """Iniciar fluxo OAuth do ClickUp. Requer role manager."""
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Apenas gestores podem conectar o ClickUp")
    if not settings.CLICKUP_CLIENT_ID:
        raise HTTPException(status_code=500, detail="CLICKUP_CLIENT_ID não configurado")

    redirect_uri = f"{settings.BACKEND_URL}/api/integrations/clickup/callback"
    url = (
        f"https://app.clickup.com/api"
        f"?client_id={settings.CLICKUP_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&state={user['org_id']}"
    )
    return RedirectResponse(url)


@router.get("/clickup/callback")
async def clickup_callback(code: str, state: str):
    """Callback do OAuth do ClickUp. Salva token e redireciona ao frontend."""
    if not settings.CLICKUP_CLIENT_ID or not settings.CLICKUP_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Credenciais OAuth do ClickUp não configuradas")

    redirect_uri = f"{settings.BACKEND_URL}/api/integrations/clickup/callback"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.clickup.com/api/v2/oauth/token",
            json={
                "client_id": settings.CLICKUP_CLIENT_ID,
                "client_secret": settings.CLICKUP_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            }
        )
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Falha ao trocar código pelo token do ClickUp")
        token_data = response.json()

    # Buscar nome do workspace para metadata
    metadata = {}
    try:
        async with httpx.AsyncClient() as client:
            teams_resp = await client.get(
                "https://api.clickup.com/api/v2/team",
                headers={"Authorization": token_data["access_token"]}
            )
            if teams_resp.status_code == 200:
                teams = teams_resp.json().get("teams", [])
                if teams:
                    metadata = {"team_id": teams[0]["id"], "team_name": teams[0]["name"]}
    except Exception:
        pass

    await upsert_org_integration(
        org_id=state,
        provider="clickup",
        credentials={"access_token": token_data["access_token"]},
        metadata=metadata
    )

    return RedirectResponse(f"{settings.FRONTEND_URL}/settings/integrations?clickup=connected")


@router.delete("/clickup")
async def clickup_disconnect(user: dict = Depends(get_current_user)):
    """Desconectar ClickUp da organização."""
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Apenas gestores podem desconectar o ClickUp")
    await delete_org_integration(user["org_id"], "clickup")
    return {"message": "ClickUp desconectado"}


# ─────────────────────────────────────────────
# Google Calendar OAuth
# ─────────────────────────────────────────────

def _build_google_flow() -> Flow:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Credenciais OAuth do Google não configuradas")

    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=GOOGLE_SCOPES,
        redirect_uri=f"{settings.BACKEND_URL}/api/integrations/google/callback",
    )


@router.get("/google/auth")
async def google_auth(user: dict = Depends(get_current_user)):
    """Iniciar fluxo OAuth do Google Calendar."""
    flow = _build_google_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=user["id"],
    )
    return RedirectResponse(auth_url)


@router.get("/google/callback")
async def google_callback(code: str, state: str):
    """Callback do OAuth do Google. Salva tokens e redireciona ao frontend."""
    import asyncio
    from datetime import datetime, timezone

    flow = _build_google_flow()

    try:
        await asyncio.to_thread(flow.fetch_token, code=code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Falha ao trocar código pelo token do Google: {e}")

    credentials = flow.credentials
    expires_at = credentials.expiry.replace(tzinfo=timezone.utc).isoformat() if credentials.expiry else None

    await upsert_user_integration(
        user_id=state,
        provider="google_calendar",
        credentials={
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "expires_at": expires_at,
        },
        metadata={"email": credentials.id_token.get("email") if credentials.id_token else None}
    )

    return RedirectResponse(f"{settings.FRONTEND_URL}/settings/integrations?google=connected")


@router.delete("/google")
async def google_disconnect(user: dict = Depends(get_current_user)):
    """Desconectar Google Calendar do usuário atual."""
    await delete_user_integration(user["id"], "google_calendar")
    return {"message": "Google Calendar desconectado"}


# ─────────────────────────────────────────────
# OpenAI
# ─────────────────────────────────────────────

@router.post("/openai")
async def openai_configure(data: OpenAIKeyConfig, user: dict = Depends(get_current_user)):
    """Salvar API key da OpenAI para a organização."""
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Apenas gestores podem configurar a chave OpenAI")
    if not data.api_key.startswith("sk-"):
        raise HTTPException(status_code=400, detail="API key inválida. Deve começar com 'sk-'")

    await upsert_org_integration(
        org_id=user["org_id"],
        provider="openai",
        credentials={"api_key": data.api_key}
    )
    return {"message": "Chave OpenAI configurada com sucesso"}


@router.get("/openai")
async def openai_status(user: dict = Depends(get_current_user)):
    """Verificar se OpenAI está configurada (não expõe a chave)."""
    integration = await get_org_integration(user["org_id"], "openai")
    has_env_key = bool(settings.OPENAI_API_KEY)
    configured = bool(integration) or has_env_key
    source = "org" if integration else ("env" if has_env_key else None)
    return {"configured": configured, "source": source}


@router.delete("/openai")
async def openai_remove(user: dict = Depends(get_current_user)):
    """Remover chave OpenAI da organização."""
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Apenas gestores podem remover a chave OpenAI")
    await delete_org_integration(user["org_id"], "openai")
    return {"message": "Chave OpenAI removida"}


# ─────────────────────────────────────────────
# Status geral
# ─────────────────────────────────────────────

@router.get("/status", response_model=IntegrationsStatusResponse)
async def integrations_status(user: dict = Depends(get_current_user)):
    """Status de todas as integrações para a org/usuário atual."""
    import asyncio
    from app.integrations.token_store import get_org_integration, get_user_integration

    clickup_int, google_int, openai_int = await asyncio.gather(
        get_org_integration(user["org_id"], "clickup"),
        get_user_integration(user["id"], "google_calendar"),
        get_org_integration(user["org_id"], "openai"),
    )

    has_env_openai = bool(settings.OPENAI_API_KEY)

    return IntegrationsStatusResponse(
        clickup=IntegrationStatus(
            connected=bool(clickup_int),
            metadata=clickup_int.get("metadata") if clickup_int else None
        ),
        google_calendar=IntegrationStatus(
            connected=bool(google_int),
            metadata=google_int.get("metadata") if google_int else None
        ),
        openai={
            "configured": bool(openai_int) or has_env_openai,
            "source": "org" if openai_int else ("env" if has_env_openai else None)
        }
    )
