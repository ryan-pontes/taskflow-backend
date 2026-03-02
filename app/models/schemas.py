from pydantic import BaseModel, EmailStr
from typing import Optional, List, Literal
from datetime import datetime
from uuid import UUID

# === Auth ===
class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: UUID
    org_id: Optional[UUID] = None
    role: Literal["manager", "leader", "member"] = "member"
    created_at: datetime

# === Organization ===
class OrgCreate(BaseModel):
    name: str

class Organization(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime

# === Invite ===
class InviteCreate(BaseModel):
    email: EmailStr
    role: Literal["leader", "member"] = "member"

class InviteAccept(BaseModel):
    name: str
    password: str

class Invite(BaseModel):
    id: UUID
    email: str
    role: str
    token: str
    org_id: UUID
    accepted_at: Optional[datetime]
    expires_at: datetime

# === Space ===
class ClickUpSyncConfig(BaseModel):
    enabled: bool = False
    list_id: Optional[str] = None
    folder_id: Optional[str] = None
    direction: Literal["import", "export", "bidirectional"] = "bidirectional"
    frequency: Literal["realtime", "hourly", "manual"] = "hourly"

class SpaceCreate(BaseModel):
    name: str
    type: Literal["team", "project", "personal", "study"]
    clickup_sync: Optional[ClickUpSyncConfig] = None

class Space(BaseModel):
    id: UUID
    name: str
    type: str
    org_id: UUID
    clickup_sync: Optional[dict]
    created_by: UUID
    created_at: datetime

# === Member ===
class MemberProfile(BaseModel):
    skills: List[dict] = []  # [{"name": "React", "level": "advanced"}]
    soft_skills: List[str] = []
    work_style: Optional[str] = None  # "independent", "collaborative", "needs_guidance"
    career_goals: Optional[str] = None
    notes: Optional[str] = None  # Observações do gestor (privadas)

class MemberCreate(BaseModel):
    user_id: UUID
    role: Literal["leader", "member"] = "member"
    profile: Optional[MemberProfile] = None

class Member(BaseModel):
    id: UUID
    user_id: UUID
    org_id: UUID
    role: str
    profile: dict
    created_at: datetime
    # Campos extras para exibição
    name: Optional[str] = None
    email: Optional[str] = None

# === Task ===
class SubTask(BaseModel):
    title: str
    completed: bool = False

class TaskCreate(BaseModel):
    title: str
    type: Literal["bug", "urgent", "project", "task", "personal"] = "task"
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    space_id: UUID
    description: Optional[str] = None
    assignee_id: Optional[UUID] = None
    due_date: Optional[datetime] = None
    subtasks: List[SubTask] = []

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assignee_id: Optional[UUID] = None
    due_date: Optional[datetime] = None
    subtasks: Optional[List[SubTask]] = None

class Task(BaseModel):
    id: UUID
    space_id: UUID
    title: str
    description: Optional[str]
    type: str
    priority: str
    status: str
    assignee_id: Optional[UUID]
    creator_id: UUID
    due_date: Optional[datetime]
    subtasks: List[dict]
    clickup_id: Optional[str]
    source: str
    created_at: datetime
    updated_at: datetime

# === Delegation Suggestion ===
class DelegationSuggestion(BaseModel):
    member_id: UUID
    name: str
    reason: str
    workload_score: float  # 0-1, quanto menor melhor
    skill_match: float  # 0-1, quanto maior melhor

# === Chat ===
class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    actions_taken: List[dict] = []  # Ações executadas pelo agente

# === Metrics ===
class MemberWorkload(BaseModel):
    member_id: UUID
    name: str
    open_tasks: int
    overdue_tasks: int
    workload_percentage: float

class SpaceProgress(BaseModel):
    space_id: UUID
    name: str
    total_tasks: int
    completed_tasks: int
    progress_percentage: float

# === Integrations ===
class OpenAIKeyConfig(BaseModel):
    api_key: str

class IntegrationStatus(BaseModel):
    connected: bool
    metadata: Optional[dict] = None

class IntegrationsStatusResponse(BaseModel):
    clickup: IntegrationStatus
    google_calendar: IntegrationStatus
    openai: dict
