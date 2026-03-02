from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID

from app.api.auth import get_current_user
from app.models.schemas import MemberProfile
from app.integrations.supabase import (
    get_members_by_org, get_member_with_user_info, 
    update_member_profile, get_member_workload
)
from app.agents import run_agents

router = APIRouter()


@router.get("/", response_model=List[dict])
async def list_members(user: dict = Depends(get_current_user)):
    """Listar membros do time"""
    members = await get_members_by_org(user["org_id"])
    
    # Enriquecer com workload
    result = []
    for m in members:
        workload = await get_member_workload(m["id"])
        result.append({
            **m,
            "workload": workload
        })
    
    return result


@router.get("/{member_id}", response_model=dict)
async def get_member(
    member_id: UUID,
    user: dict = Depends(get_current_user)
):
    """Buscar membro por ID"""
    member = await get_member_with_user_info(str(member_id))
    if not member:
        raise HTTPException(status_code=404, detail="Membro não encontrado")
    
    workload = await get_member_workload(str(member_id))
    return {**member, "workload": workload}


@router.patch("/{member_id}/profile", response_model=dict)
async def update_profile(
    member_id: UUID,
    profile: MemberProfile,
    user: dict = Depends(get_current_user)
):
    """Atualizar perfil do membro (gestor ou próprio membro)"""
    updated = await update_member_profile(str(member_id), profile.dict())
    return updated


@router.post("/{member_id}/analyze", response_model=dict)
async def analyze_member(
    member_id: UUID,
    user: dict = Depends(get_current_user)
):
    """Analisar perfil do membro com IA"""
    if user.get("role") not in ["manager", "leader"]:
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    result = await run_agents(
        action="profile",
        input_data={"member_id": str(member_id), "profile_action": "analyze"},
        user_context=user
    )
    
    return result.get("profile", {})


@router.get("/{member_id}/workload", response_model=dict)
async def get_workload(
    member_id: UUID,
    user: dict = Depends(get_current_user)
):
    """Obter carga de trabalho do membro"""
    return await get_member_workload(str(member_id))
