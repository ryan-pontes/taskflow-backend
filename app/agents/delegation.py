from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings
from app.integrations.supabase import get_members_by_org, get_member_workload

_llm = None

def get_llm(api_key: str = None):
    if api_key:
        return ChatOpenAI(model="gpt-4o", temperature=0, api_key=api_key)
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=settings.OPENAI_API_KEY)
    return _llm

DELEGATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Você é um agente especializado em delegação de tarefas.
    
Analise a tarefa e os membros disponíveis para sugerir o melhor responsável.

Considere:
1. Habilidades técnicas necessárias vs disponíveis
2. Carga atual de trabalho (menos tarefas = melhor)
3. Disponibilidade na agenda
4. Estilo de trabalho do membro
5. Oportunidade de desenvolvimento

Responda SEMPRE em JSON válido:
{{
    "suggestions": [
        {{
            "member_id": "uuid",
            "name": "nome",
            "reason": "motivo curto",
            "workload_score": 0.3,
            "skill_match": 0.9
        }}
    ],
    "reasoning": "explicação geral"
}}"""),
    ("human", """
Tarefa a ser delegada:
- Título: {title}
- Tipo: {type}
- Prioridade: {priority}
- Descrição: {description}

Membros disponíveis e suas informações:
{members_info}

Sugira 1-3 membros ideais para esta tarefa.""")
])


async def run_delegation_agent(task: dict, user_context: dict) -> dict:
    """Analisar tarefa e sugerir responsáveis"""
    
    org_id = user_context.get("org_id")
    if not org_id:
        return {"suggestions": [], "error": "Organização não encontrada"}
    
    # Buscar membros do time
    members = await get_members_by_org(org_id)
    
    if not members:
        return {"suggestions": [], "error": "Nenhum membro no time"}
    
    # Enriquecer com workload
    members_info = []
    for m in members:
        workload = await get_member_workload(m["id"])
        profile = m.get("profile", {})
        
        members_info.append({
            "id": m["id"],
            "name": profile.get("name", "Sem nome"),
            "role": m["role"],
            "skills": profile.get("skills", []),
            "work_style": profile.get("work_style", "unknown"),
            "open_tasks": workload.get("open_tasks", 0),
            "overdue_tasks": workload.get("overdue_tasks", 0),
            "workload_percentage": workload.get("workload_percentage", 0)
        })
    
    # Chamar LLM
    chain = DELEGATION_PROMPT | get_llm(api_key=user_context.get("openai_key")) | JsonOutputParser()
    
    result = await chain.ainvoke({
        "title": task.get("title", ""),
        "type": task.get("type", "task"),
        "priority": task.get("priority", "medium"),
        "description": task.get("description", "Sem descrição"),
        "members_info": str(members_info)
    })
    
    return result
