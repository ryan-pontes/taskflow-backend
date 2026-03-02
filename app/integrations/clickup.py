import httpx
from typing import Optional, List
from app.config import settings

CLICKUP_BASE_URL = "https://api.clickup.com/api/v2"

class ClickUpClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.CLICKUP_API_KEY
        self.headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }
    
    async def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        async with httpx.AsyncClient() as client:
            url = f"{CLICKUP_BASE_URL}{endpoint}"
            response = await client.request(method, url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()
    
    # === Workspaces/Teams ===
    async def get_workspaces(self) -> List[dict]:
        result = await self._request("GET", "/team")
        return result.get("teams", [])
    
    # === Spaces ===
    async def get_spaces(self, team_id: str) -> List[dict]:
        result = await self._request("GET", f"/team/{team_id}/space")
        return result.get("spaces", [])
    
    # === Folders ===
    async def get_folders(self, space_id: str) -> List[dict]:
        result = await self._request("GET", f"/space/{space_id}/folder")
        return result.get("folders", [])
    
    # === Lists ===
    async def get_lists(self, folder_id: str) -> List[dict]:
        result = await self._request("GET", f"/folder/{folder_id}/list")
        return result.get("lists", [])
    
    async def get_folderless_lists(self, space_id: str) -> List[dict]:
        result = await self._request("GET", f"/space/{space_id}/list")
        return result.get("lists", [])
    
    # === Tasks ===
    async def get_tasks(self, list_id: str, include_closed: bool = False) -> List[dict]:
        params = f"?include_closed={str(include_closed).lower()}"
        result = await self._request("GET", f"/list/{list_id}/task{params}")
        return result.get("tasks", [])
    
    async def get_task(self, task_id: str) -> dict:
        return await self._request("GET", f"/task/{task_id}")
    
    async def create_task(self, list_id: str, task_data: dict) -> dict:
        """
        task_data: {
            "name": str,
            "description": str,
            "priority": int (1=urgent, 2=high, 3=normal, 4=low),
            "due_date": int (timestamp ms),
            "assignees": [user_id],
            "status": str
        }
        """
        return await self._request("POST", f"/list/{list_id}/task", task_data)
    
    async def update_task(self, task_id: str, task_data: dict) -> dict:
        return await self._request("PUT", f"/task/{task_id}", task_data)
    
    async def delete_task(self, task_id: str) -> bool:
        await self._request("DELETE", f"/task/{task_id}")
        return True
    
    # === Members ===
    async def get_workspace_members(self, team_id: str) -> List[dict]:
        result = await self._request("GET", f"/team/{team_id}/member")
        return result.get("members", [])


# Helper functions
def map_priority_to_clickup(priority: str) -> int:
    """Mapear prioridade do TaskFlow para ClickUp"""
    mapping = {
        "critical": 1,
        "high": 2,
        "medium": 3,
        "low": 4
    }
    return mapping.get(priority, 3)

def map_priority_from_clickup(priority: dict) -> str:
    """Mapear prioridade do ClickUp para TaskFlow"""
    if not priority:
        return "medium"
    mapping = {
        1: "critical",
        2: "high",
        3: "medium",
        4: "low"
    }
    return mapping.get(priority.get("id"), "medium")

def map_task_to_clickup(task: dict, list_id: str) -> dict:
    """Converter tarefa TaskFlow para formato ClickUp"""
    clickup_task = {
        "name": task["title"],
        "description": task.get("description", ""),
        "priority": map_priority_to_clickup(task.get("priority", "medium")),
    }
    
    if task.get("due_date"):
        from datetime import datetime
        if isinstance(task["due_date"], str):
            dt = datetime.fromisoformat(task["due_date"].replace("Z", "+00:00"))
        else:
            dt = task["due_date"]
        clickup_task["due_date"] = int(dt.timestamp() * 1000)
    
    return clickup_task

def map_task_from_clickup(clickup_task: dict) -> dict:
    """Converter tarefa ClickUp para formato TaskFlow"""
    from datetime import datetime
    
    due_date = None
    if clickup_task.get("due_date"):
        due_date = datetime.fromtimestamp(int(clickup_task["due_date"]) / 1000).isoformat()
    
    return {
        "title": clickup_task["name"],
        "description": clickup_task.get("description", ""),
        "priority": map_priority_from_clickup(clickup_task.get("priority")),
        "status": clickup_task.get("status", {}).get("status", "backlog"),
        "due_date": due_date,
        "clickup_id": clickup_task["id"],
        "source": "clickup"
    }


# Singleton
clickup_client = ClickUpClient()
