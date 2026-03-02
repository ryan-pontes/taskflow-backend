from supabase import create_client, Client
from typing import Optional, List
from uuid import UUID

from app.config import settings

# Client com service key (bypass RLS)
supabase_admin: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

# Client normal (respeita RLS)
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


# === Users ===
async def get_user_by_id(user_id: str) -> Optional[dict]:
    result = supabase_admin.table("users").select("*").eq("id", user_id).single().execute()
    return result.data if result.data else None

async def get_user_by_email(email: str) -> Optional[dict]:
    result = supabase_admin.auth.admin.list_users()
    for user in result:
        if user.email == email:
            return {"id": user.id, "email": user.email}
    return None


# === Organizations ===
async def create_organization(name: str, owner_id: str) -> dict:
    result = supabase_admin.table("organizations").insert({
        "name": name,
        "owner_id": owner_id
    }).execute()
    return result.data[0]

async def get_organization(org_id: str) -> Optional[dict]:
    result = supabase_admin.table("organizations").select("*").eq("id", org_id).single().execute()
    return result.data


# === Members ===
async def create_member(user_id: str, org_id: str, role: str, profile: dict = {}) -> dict:
    result = supabase_admin.table("members").insert({
        "user_id": user_id,
        "org_id": org_id,
        "role": role,
        "profile": profile
    }).execute()
    return result.data[0]

async def get_member_by_user_id(user_id: str) -> Optional[dict]:
    result = supabase_admin.table("members").select("*").eq("user_id", user_id).single().execute()
    return result.data if result.data else None

async def get_members_by_org(org_id: str) -> List[dict]:
    result = supabase_admin.table("members").select("*").eq("org_id", org_id).execute()
    return result.data

async def get_member_with_user_info(member_id: str) -> Optional[dict]:
    result = supabase_admin.table("members").select("*, users(email, name)").eq("id", member_id).single().execute()
    return result.data

async def update_member_profile(member_id: str, profile: dict) -> dict:
    result = supabase_admin.table("members").update({"profile": profile}).eq("id", member_id).execute()
    return result.data[0]


# === Spaces ===
async def create_space(name: str, type: str, org_id: str, created_by: str, clickup_sync: dict = None) -> dict:
    result = supabase_admin.table("spaces").insert({
        "name": name,
        "type": type,
        "org_id": org_id,
        "created_by": created_by,
        "clickup_sync": clickup_sync
    }).execute()
    return result.data[0]

async def get_spaces_by_org(org_id: str) -> List[dict]:
    result = supabase_admin.table("spaces").select("*").eq("org_id", org_id).execute()
    return result.data

async def get_space(space_id: str) -> Optional[dict]:
    result = supabase_admin.table("spaces").select("*").eq("id", space_id).single().execute()
    return result.data

async def update_space(space_id: str, data: dict) -> dict:
    result = supabase_admin.table("spaces").update(data).eq("id", space_id).execute()
    return result.data[0]


# === Tasks ===
async def create_task(task_data: dict) -> dict:
    result = supabase_admin.table("tasks").insert(task_data).execute()
    return result.data[0]

async def get_tasks_by_space(space_id: str) -> List[dict]:
    result = supabase_admin.table("tasks").select("*").eq("space_id", space_id).order("created_at", desc=True).execute()
    return result.data

async def get_tasks_by_assignee(assignee_id: str) -> List[dict]:
    result = supabase_admin.table("tasks").select("*").eq("assignee_id", assignee_id).execute()
    return result.data

async def get_tasks_by_org(org_id: str) -> List[dict]:
    # Buscar tarefas de todos os spaces da org
    result = supabase_admin.table("tasks").select("*, spaces!inner(org_id)").eq("spaces.org_id", org_id).execute()
    return result.data

async def get_task(task_id: str) -> Optional[dict]:
    result = supabase_admin.table("tasks").select("*").eq("id", task_id).single().execute()
    return result.data

async def update_task(task_id: str, data: dict) -> dict:
    data["updated_at"] = "now()"
    result = supabase_admin.table("tasks").update(data).eq("id", task_id).execute()
    return result.data[0]

async def delete_task(task_id: str) -> bool:
    supabase_admin.table("tasks").delete().eq("id", task_id).execute()
    return True

async def get_open_tasks_count_by_assignee(assignee_id: str) -> int:
    result = supabase_admin.table("tasks").select("id", count="exact").eq("assignee_id", assignee_id).neq("status", "done").execute()
    return result.count

async def get_overdue_tasks_by_assignee(assignee_id: str) -> List[dict]:
    from datetime import datetime
    result = supabase_admin.table("tasks").select("*").eq("assignee_id", assignee_id).lt("due_date", datetime.now().isoformat()).neq("status", "done").execute()
    return result.data


# === Invites ===
async def create_invite(org_id: str, email: str, role: str, invited_by: str) -> dict:
    result = supabase_admin.table("invites").insert({
        "org_id": org_id,
        "email": email,
        "role": role,
        "invited_by": invited_by
    }).execute()
    return result.data[0]

async def get_invite_by_token(token: str) -> Optional[dict]:
    result = supabase_admin.table("invites").select("*").eq("token", token).single().execute()
    return result.data if result.data else None

async def mark_invite_accepted(invite_id: str) -> dict:
    from datetime import datetime
    result = supabase_admin.table("invites").update({
        "accepted_at": datetime.now().isoformat()
    }).eq("id", invite_id).execute()
    return result.data[0]

async def get_pending_invites_by_org(org_id: str) -> List[dict]:
    result = supabase_admin.table("invites").select("*").eq("org_id", org_id).is_("accepted_at", "null").execute()
    return result.data


# === Metrics ===
async def get_member_workload(member_id: str) -> dict:
    open_count = await get_open_tasks_count_by_assignee(member_id)
    overdue = await get_overdue_tasks_by_assignee(member_id)
    
    # Calcular workload (simplificado: baseado em número de tarefas)
    max_tasks = 10  # Número ideal máximo de tarefas abertas
    workload_percentage = min(100, (open_count / max_tasks) * 100)
    
    return {
        "member_id": member_id,
        "open_tasks": open_count,
        "overdue_tasks": len(overdue),
        "workload_percentage": workload_percentage
    }
