import asyncio
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from uuid import UUID

from app.api.auth import get_current_user
from app.models.schemas import TaskCreate, TaskUpdate, Task, DelegationSuggestion
from app.integrations.supabase import (
    create_task, get_task, get_tasks_by_space,
    get_tasks_by_assignee, update_task, delete_task,
    get_space
)
from app.integrations.token_store import get_openai_key, get_clickup_token, get_google_credentials
from app.services.sync_service import maybe_sync_to_clickup, sync_status_to_clickup
from app.agents import run_agents

router = APIRouter()


@router.post("/", response_model=dict)
async def create_new_task(
    task: TaskCreate,
    user: dict = Depends(get_current_user)
):
    """Criar tarefa com enriquecimento e sugestão de delegação"""
    
    # Verificar se space pertence à org do usuário
    space = await get_space(str(task.space_id))
    if not space or space.get("org_id") != user.get("org_id"):
        raise HTTPException(status_code=403, detail="Space não encontrado")
    
    # Preparar dados
    task_data = {
        "title": task.title,
        "type": task.type,
        "priority": task.priority,
        "space_id": str(task.space_id),
        "description": task.description,
        "assignee_id": str(task.assignee_id) if task.assignee_id else None,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "subtasks": [s.dict() for s in task.subtasks],
        "creator_id": user["id"],
        "status": "backlog",
        "source": "internal"
    }
    
    # Criar tarefa
    created = await create_task(task_data)

    # Carregar tokens em paralelo
    openai_key, clickup_token, google_creds = await asyncio.gather(
        get_openai_key(user["org_id"]),
        get_clickup_token(user["org_id"]),
        get_google_credentials(user["id"]),
    )
    enriched_user = {**user, "openai_key": openai_key, "clickup_token": clickup_token, "google_creds": google_creds}

    # Rodar agentes (enriquecimento + delegação) e sync ClickUp em paralelo
    agent_result, _ = await asyncio.gather(
        run_agents(action="create_task", input_data=task_data, user_context=enriched_user),
        maybe_sync_to_clickup(created, org_id=user["org_id"]),
    )

    return {
        "task": created,
        "enrichment": agent_result.get("enrichment"),
        "delegation": agent_result.get("delegation")
    }


@router.get("/space/{space_id}", response_model=List[dict])
async def get_space_tasks(
    space_id: UUID,
    status: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Listar tarefas de um Space"""
    tasks = await get_tasks_by_space(str(space_id))
    
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    
    return tasks


@router.get("/my", response_model=List[dict])
async def get_my_tasks(
    user: dict = Depends(get_current_user)
):
    """Listar minhas tarefas (como responsável)"""
    if not user.get("member_id"):
        return []
    
    return await get_tasks_by_assignee(user["member_id"])


@router.get("/{task_id}", response_model=dict)
async def get_single_task(
    task_id: UUID,
    user: dict = Depends(get_current_user)
):
    """Buscar tarefa por ID"""
    task = await get_task(str(task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    return task


@router.patch("/{task_id}", response_model=dict)
async def update_single_task(
    task_id: UUID,
    data: TaskUpdate,
    user: dict = Depends(get_current_user)
):
    """Atualizar tarefa"""
    update_data = data.dict(exclude_unset=True)
    
    if data.assignee_id:
        update_data["assignee_id"] = str(data.assignee_id)
    
    updated = await update_task(str(task_id), update_data)

    if data.status:
        await sync_status_to_clickup(str(task_id), data.status, org_id=user["org_id"])

    return updated


@router.delete("/{task_id}")
async def delete_single_task(
    task_id: UUID,
    user: dict = Depends(get_current_user)
):
    """Deletar tarefa"""
    await delete_task(str(task_id))
    return {"success": True}


@router.post("/{task_id}/delegate", response_model=dict)
async def get_delegation_suggestions(
    task_id: UUID,
    user: dict = Depends(get_current_user)
):
    """Obter sugestões de delegação para tarefa existente"""
    task = await get_task(str(task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    
    openai_key = await get_openai_key(user["org_id"])
    enriched_user = {**user, "openai_key": openai_key}
    result = await run_agents(action="delegate", input_data=task, user_context=enriched_user)
    return result.get("delegation", {})


@router.post("/{task_id}/enrich", response_model=dict)
async def enrich_task(
    task_id: UUID,
    user: dict = Depends(get_current_user)
):
    """Enriquecer tarefa com IA"""
    task = await get_task(str(task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    
    openai_key = await get_openai_key(user["org_id"])
    enriched_user = {**user, "openai_key": openai_key}
    result = await run_agents(action="enrich", input_data=task, user_context=enriched_user)
    
    enrichment = result.get("enrichment", {})
    
    # Atualizar tarefa com dados enriquecidos
    if enrichment:
        update_data = {}
        if enrichment.get("description") and not task.get("description"):
            update_data["description"] = enrichment["description"]
        if enrichment.get("subtasks") and not task.get("subtasks"):
            update_data["subtasks"] = enrichment["subtasks"]
        
        if update_data:
            await update_task(str(task_id), update_data)
    
    return enrichment
