import asyncio
from fastapi import APIRouter, Depends
from app.api.auth import get_current_user
from app.models.schemas import ChatMessage, ChatResponse
from app.integrations.token_store import get_openai_key, get_google_credentials
from app.agents import run_agents

router = APIRouter()


@router.post("/", response_model=dict)
async def chat_with_assistant(
    message: ChatMessage,
    user: dict = Depends(get_current_user)
):
    """Chat com agente assistente"""
    openai_key, google_creds = await asyncio.gather(
        get_openai_key(user["org_id"]),
        get_google_credentials(user["id"]),
    )
    enriched_user = {**user, "openai_key": openai_key, "google_creds": google_creds}

    result = await run_agents(
        action="chat",
        input_data={"message": message.message},
        user_context=enriched_user
    )
    return result.get("assistant", {"message": "Desculpe, não consegui processar."})


@router.post("/profile-conversation", response_model=dict)
async def profile_conversation(
    message: ChatMessage,
    user: dict = Depends(get_current_user)
):
    """Conversa para construir perfil do liderado"""
    openai_key = await get_openai_key(user["org_id"])
    enriched_user = {**user, "openai_key": openai_key}

    result = await run_agents(
        action="profile",
        input_data={
            "member_id": user.get("member_id"),
            "profile_action": "conversation",
            "message": message.message
        },
        user_context=enriched_user
    )
    return result.get("profile", {"message": "Olá! Vamos construir seu perfil."})
