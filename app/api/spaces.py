from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID

from app.api.auth import get_current_user
from app.models.schemas import SpaceCreate, Space
from app.integrations.supabase import (
    create_space, get_space, get_spaces_by_org, update_space
)

router = APIRouter()


@router.post("/", response_model=dict)
async def create_new_space(
    space: SpaceCreate,
    user: dict = Depends(get_current_user)
):
    """Criar Space"""
    # Verificar permissão (apenas manager e leader)
    if user.get("role") not in ["manager", "leader"]:
        raise HTTPException(status_code=403, detail="Sem permissão para criar Space")
    
    # Spaces pessoais só para manager
    if space.type in ["personal", "study"] and user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Apenas gestores podem criar Spaces pessoais")
    
    created = await create_space(
        name=space.name,
        type=space.type,
        org_id=user["org_id"],
        created_by=user["id"],
        clickup_sync=space.clickup_sync.dict() if space.clickup_sync else None
    )
    
    return created


@router.get("/", response_model=List[dict])
async def list_spaces(user: dict = Depends(get_current_user)):
    """Listar Spaces da organização"""
    spaces = await get_spaces_by_org(user["org_id"])
    
    # Filtrar spaces pessoais (só o criador vê)
    if user.get("role") != "manager":
        spaces = [s for s in spaces if s.get("type") not in ["personal", "study"]]
    
    return spaces


@router.get("/{space_id}", response_model=dict)
async def get_single_space(
    space_id: UUID,
    user: dict = Depends(get_current_user)
):
    """Buscar Space por ID"""
    space = await get_space(str(space_id))
    if not space:
        raise HTTPException(status_code=404, detail="Space não encontrado")
    return space


@router.patch("/{space_id}", response_model=dict)
async def update_single_space(
    space_id: UUID,
    data: SpaceCreate,
    user: dict = Depends(get_current_user)
):
    """Atualizar Space"""
    update_data = {
        "name": data.name,
        "type": data.type,
        "clickup_sync": data.clickup_sync.dict() if data.clickup_sync else None
    }
    
    updated = await update_space(str(space_id), update_data)
    return updated
