from app.integrations.clickup import get_clickup_client, map_task_to_clickup, map_task_from_clickup
from app.integrations.supabase import get_space, create_task, update_task, get_tasks_by_space


async def maybe_sync_to_clickup(task: dict, org_id: str) -> dict | None:
    """Sincronizar tarefa para ClickUp se configurado"""
    space = await get_space(task["space_id"])

    if not space:
        return None

    sync_config = space.get("clickup_sync")
    if not sync_config or not sync_config.get("enabled"):
        return None

    direction = sync_config.get("direction", "bidirectional")
    if direction == "import":
        return None

    list_id = sync_config.get("list_id")
    if not list_id:
        return None

    client = await get_clickup_client(org_id)
    if not client:
        return None

    try:
        clickup_data = map_task_to_clickup(task, list_id)
        result = await client.create_task(list_id, clickup_data)
        await update_task(task["id"], {"clickup_id": result["id"]})
        return result
    except Exception as e:
        print(f"Erro ao sincronizar com ClickUp: {e}")
        return None


async def sync_from_clickup(space_id: str, org_id: str) -> list:
    """Importar tarefas do ClickUp para um Space"""
    space = await get_space(space_id)

    if not space:
        return []

    sync_config = space.get("clickup_sync")
    if not sync_config or not sync_config.get("enabled"):
        return []

    direction = sync_config.get("direction", "bidirectional")
    if direction == "export":
        return []

    list_id = sync_config.get("list_id")
    if not list_id:
        return []

    client = await get_clickup_client(org_id)
    if not client:
        return []

    try:
        clickup_tasks = await client.get_tasks(list_id)
        existing = await get_tasks_by_space(space_id)
        existing_clickup_ids = {t.get("clickup_id") for t in existing if t.get("clickup_id")}

        imported = []
        for ct in clickup_tasks:
            if ct["id"] in existing_clickup_ids:
                continue

            task_data = map_task_from_clickup(ct)
            task_data["space_id"] = space_id
            task_data["creator_id"] = space.get("created_by")

            created = await create_task(task_data)
            imported.append(created)

        return imported
    except Exception as e:
        print(f"Erro ao importar do ClickUp: {e}")
        return []


async def sync_status_to_clickup(task_id: str, new_status: str, org_id: str):
    """Sincronizar mudança de status para ClickUp"""
    from app.integrations.supabase import get_task

    task = await get_task(task_id)
    if not task or not task.get("clickup_id"):
        return

    client = await get_clickup_client(org_id)
    if not client:
        return

    try:
        await client.update_task(task["clickup_id"], {"status": new_status})
    except Exception as e:
        print(f"Erro ao atualizar status no ClickUp: {e}")
