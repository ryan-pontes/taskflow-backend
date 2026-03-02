-- =============================================
-- TaskFlow Manager - Supabase Schema
-- =============================================

-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- =============================================
-- ORGANIZATIONS
-- =============================================
create table organizations (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  owner_id uuid references auth.users(id) on delete cascade,
  created_at timestamptz default now()
);

-- RLS
alter table organizations enable row level security;

create policy "Users can view own org"
  on organizations for select
  using (owner_id = auth.uid());

-- =============================================
-- MEMBERS
-- =============================================
create table members (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references auth.users(id) on delete cascade,
  org_id uuid references organizations(id) on delete cascade,
  role text check (role in ('manager', 'leader', 'member')) default 'member',
  profile jsonb default '{}'::jsonb,
  created_at timestamptz default now(),
  
  unique(user_id, org_id)
);

-- Index
create index idx_members_org on members(org_id);
create index idx_members_user on members(user_id);

-- RLS
alter table members enable row level security;

create policy "Users can view org members"
  on members for select
  using (
    org_id in (
      select org_id from members where user_id = auth.uid()
    )
  );

-- =============================================
-- INVITES
-- =============================================
create table invites (
  id uuid primary key default uuid_generate_v4(),
  org_id uuid references organizations(id) on delete cascade,
  email text not null,
  role text check (role in ('leader', 'member')) default 'member',
  token text unique default uuid_generate_v4()::text,
  invited_by uuid references auth.users(id),
  accepted_at timestamptz,
  expires_at timestamptz default now() + interval '7 days',
  created_at timestamptz default now()
);

-- Index
create index idx_invites_token on invites(token);
create index idx_invites_org on invites(org_id);

-- =============================================
-- SPACES
-- =============================================
create table spaces (
  id uuid primary key default uuid_generate_v4(),
  org_id uuid references organizations(id) on delete cascade,
  name text not null,
  type text check (type in ('team', 'project', 'personal', 'study')) default 'team',
  clickup_sync jsonb default null,
  created_by uuid references auth.users(id),
  created_at timestamptz default now()
);

-- Index
create index idx_spaces_org on spaces(org_id);

-- RLS
alter table spaces enable row level security;

create policy "Users can view org spaces"
  on spaces for select
  using (
    org_id in (
      select org_id from members where user_id = auth.uid()
    )
    or (type in ('personal', 'study') and created_by = auth.uid())
  );

-- =============================================
-- TASKS
-- =============================================
create table tasks (
  id uuid primary key default uuid_generate_v4(),
  space_id uuid references spaces(id) on delete cascade,
  title text not null,
  description text,
  type text check (type in ('bug', 'urgent', 'project', 'task', 'personal')) default 'task',
  priority text check (priority in ('low', 'medium', 'high', 'critical')) default 'medium',
  status text default 'backlog',
  assignee_id uuid references members(id) on delete set null,
  creator_id uuid references auth.users(id),
  due_date timestamptz,
  subtasks jsonb default '[]'::jsonb,
  clickup_id text,
  source text default 'internal',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Indexes
create index idx_tasks_space on tasks(space_id);
create index idx_tasks_assignee on tasks(assignee_id);
create index idx_tasks_status on tasks(status);
create index idx_tasks_due_date on tasks(due_date);

-- RLS
alter table tasks enable row level security;

create policy "Users can view org tasks"
  on tasks for select
  using (
    space_id in (
      select s.id from spaces s
      inner join members m on s.org_id = m.org_id
      where m.user_id = auth.uid()
    )
  );

create policy "Users can insert tasks"
  on tasks for insert
  with check (
    space_id in (
      select s.id from spaces s
      inner join members m on s.org_id = m.org_id
      where m.user_id = auth.uid()
    )
  );

create policy "Users can update tasks"
  on tasks for update
  using (
    space_id in (
      select s.id from spaces s
      inner join members m on s.org_id = m.org_id
      where m.user_id = auth.uid()
    )
  );

-- =============================================
-- COMMENTS (para tarefas)
-- =============================================
create table comments (
  id uuid primary key default uuid_generate_v4(),
  task_id uuid references tasks(id) on delete cascade,
  user_id uuid references auth.users(id),
  content text not null,
  created_at timestamptz default now()
);

create index idx_comments_task on comments(task_id);

-- =============================================
-- ACTIVITY LOG
-- =============================================
create table activity_log (
  id uuid primary key default uuid_generate_v4(),
  org_id uuid references organizations(id) on delete cascade,
  user_id uuid references auth.users(id),
  entity_type text not null, -- 'task', 'space', 'member'
  entity_id uuid not null,
  action text not null, -- 'created', 'updated', 'deleted', 'assigned'
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create index idx_activity_org on activity_log(org_id);
create index idx_activity_entity on activity_log(entity_type, entity_id);

-- =============================================
-- FUNCTIONS
-- =============================================

-- Função para atualizar updated_at automaticamente
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- Trigger para tasks
create trigger tasks_updated_at
  before update on tasks
  for each row
  execute function update_updated_at();

-- =============================================
-- VIEWS
-- =============================================

-- View de tarefas com info do assignee
create or replace view tasks_with_assignee as
select 
  t.*,
  m.profile->>'name' as assignee_name,
  m.role as assignee_role
from tasks t
left join members m on t.assignee_id = m.id;

-- View de workload por membro
create or replace view member_workload as
select 
  m.id as member_id,
  m.user_id,
  m.org_id,
  m.profile->>'name' as name,
  count(t.id) filter (where t.status != 'done') as open_tasks,
  count(t.id) filter (where t.status != 'done' and t.due_date < now()) as overdue_tasks,
  count(t.id) as total_tasks
from members m
left join tasks t on t.assignee_id = m.id
group by m.id;
