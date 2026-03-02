from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime
from uuid import UUID

from app.api.auth import get_current_user
from app.models.schemas import InviteCreate, InviteAccept
from app.integrations.supabase import (
    create_invite, get_invite_by_token, mark_invite_accepted,
    get_pending_invites_by_org, create_member, get_organization,
    supabase_admin
)
from app.integrations.email import send_invite_email

router = APIRouter()


@router.post("/", response_model=dict)
async def create_new_invite(
    invite: InviteCreate,
    user: dict = Depends(get_current_user)
):
    """Criar convite para novo membro"""
    if user.get("role") not in ["manager", "leader"]:
        raise HTTPException(status_code=403, detail="Sem permissão para convidar")
    
    # Criar convite
    created = await create_invite(
        org_id=user["org_id"],
        email=invite.email,
        role=invite.role,
        invited_by=user["id"]
    )
    
    # Enviar email
    org = await get_organization(user["org_id"])
    try:
        await send_invite_email(
            to_email=invite.email,
            invite_token=created["token"],
            org_name=org.get("name", "Organização"),
            inviter_name=user.get("name", "Gestor")
        )
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
    
    return {
        "invite_id": created["id"],
        "token": created["token"],
        "invite_url": f"/invite/{created['token']}",
        "message": f"Convite enviado para {invite.email}"
    }


@router.get("/pending", response_model=List[dict])
async def list_pending_invites(user: dict = Depends(get_current_user)):
    """Listar convites pendentes"""
    return await get_pending_invites_by_org(user["org_id"])


@router.get("/{token}", response_model=dict)
async def validate_invite(token: str):
    """Validar token de convite (público)"""
    invite = await get_invite_by_token(token)
    
    if not invite:
        raise HTTPException(status_code=404, detail="Convite não encontrado")
    
    if invite.get("accepted_at"):
        raise HTTPException(status_code=400, detail="Convite já utilizado")
    
    if datetime.fromisoformat(invite["expires_at"].replace("Z", "+00:00")) < datetime.now(tz=datetime.now().astimezone().tzinfo):
        raise HTTPException(status_code=400, detail="Convite expirado")
    
    # Buscar nome da organização
    org = await get_organization(invite["org_id"])
    
    return {
        "valid": True,
        "email": invite["email"],
        "role": invite["role"],
        "org_name": org.get("name", "Organização")
    }


@router.post("/{token}/accept", response_model=dict)
async def accept_invite(token: str, data: InviteAccept):
    """Aceitar convite e criar conta"""
    invite = await get_invite_by_token(token)
    
    if not invite:
        raise HTTPException(status_code=404, detail="Convite não encontrado")
    
    if invite.get("accepted_at"):
        raise HTTPException(status_code=400, detail="Convite já utilizado")
    
    try:
        # Criar usuário no Supabase Auth
        auth_response = supabase_admin.auth.admin.create_user({
            "email": invite["email"],
            "password": data.password,
            "user_metadata": {"name": data.name},
            "email_confirm": True
        })
        
        user = auth_response.user
        
        # Criar member
        member = await create_member(
            user_id=user.id,
            org_id=invite["org_id"],
            role=invite["role"],
            profile={"name": data.name}
        )
        
        # Marcar convite como aceito
        await mark_invite_accepted(invite["id"])
        
        # Login automático
        login_response = supabase_admin.auth.sign_in_with_password({
            "email": invite["email"],
            "password": data.password
        })
        
        return {
            "success": True,
            "access_token": login_response.session.access_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": data.name,
                "role": invite["role"]
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{invite_id}")
async def cancel_invite(
    invite_id: UUID,
    user: dict = Depends(get_current_user)
):
    """Cancelar convite pendente"""
    supabase_admin.table("invites").delete().eq("id", str(invite_id)).execute()
    return {"success": True}
