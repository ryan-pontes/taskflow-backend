# TaskFlow Manager - Backend

API backend com multi-agentes para gestão de tarefas e times.

## Stack

- **FastAPI** - API REST
- **LangGraph** - Orquestração de agentes
- **OpenAI GPT-4o** - LLM
- **Supabase** - Database + Auth
- **LangSmith** - Observabilidade dos agentes

## Setup

### 1. Clonar e instalar

```bash
cd taskflow-backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar Supabase

1. Criar projeto em [supabase.com](https://supabase.com)
2. Executar `supabase/schema.sql` no SQL Editor
3. Copiar URL e keys

### 3. Configurar variáveis de ambiente

```bash
cp .env.example .env
# Editar .env com suas credenciais
```

### 4. Rodar

```bash
uvicorn app.main:app --reload
```

API disponível em `http://localhost:8000`
Docs em `http://localhost:8000/docs`

## Agentes

| Agente | Função |
|--------|--------|
| **Orchestrator** | Coordena fluxo entre agentes |
| **Delegation** | Sugere responsável para tarefa |
| **Enrichment** | Preenche descrição, subtarefas |
| **Assistant** | Chat geral, executa ações |
| **Profile** | Constrói perfil dos liderados |

## Endpoints Principais

### Auth
- `POST /api/auth/signup` - Criar conta gestor
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Dados do usuário

### Tasks
- `POST /api/tasks` - Criar tarefa (com IA)
- `GET /api/tasks/space/{id}` - Tarefas do Space
- `GET /api/tasks/my` - Minhas tarefas
- `POST /api/tasks/{id}/delegate` - Sugestões delegação

### Invites
- `POST /api/invites` - Convidar membro
- `GET /api/invites/{token}` - Validar convite
- `POST /api/invites/{token}/accept` - Aceitar convite

### Chat
- `POST /api/chat` - Chat com assistente

## LangSmith

Para ver traces dos agentes:
1. Criar conta em [smith.langchain.com](https://smith.langchain.com)
2. Adicionar `LANGCHAIN_API_KEY` ao `.env`
3. Acessar dashboard para ver execuções

## Deploy (Railway)

```bash
railway login
railway init
railway up
```

## Estrutura

```
app/
├── api/          # Endpoints REST
├── agents/       # LangGraph agents
├── integrations/ # Supabase, ClickUp, etc
├── models/       # Pydantic schemas
├── services/     # Business logic
└── main.py       # FastAPI app
```
