from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.tools import tool
from app.config import settings
from app.integrations import supabase as db

_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-4o", temperature=0.3, api_key=settings.OPENAI_API_KEY)
    return _llm

ASSISTANT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Você é o assistente virtual do TaskFlow Manager.

Você pode executar ações e responder perguntas sobre:
- Tarefas (criar, listar, atualizar)
- Membros do time (carga, perfil)
- Agenda (bloquear horários)
- Relatórios (resumos)

CONTEXTO DO USUÁRIO:
- Nome: {user_name}
- Role: {user_role}
- Organização: {org_name}

AÇÕES DISPONÍVEIS (responda com action quando aplicável):
- create_task: criar tarefa
- list_tasks: listar tarefas
- get_summary: resumo do time
- block_calendar: bloquear agenda
- generate_report: gerar relatório

Responda SEMPRE em JSON:
{{
    "message": "resposta em linguagem natural",
    "action": "action_name ou null",
    "action_params": {{}} ou null,
    "suggestions": ["sugestão 1"] ou []
}}"""),
    ("human", "{message}")
])


async def run_assistant_agent(message: str, user_context: dict) -> dict:
    """Processar mensagem do chat e executar ações"""
    
    chain = ASSISTANT_PROMPT | get_llm() | JsonOutputParser()
    
    result = await chain.ainvoke({
        "message": message,
        "user_name": user_context.get("name", "Usuário"),
        "user_role": user_context.get("role", "member"),
        "org_name": user_context.get("org_name", "Organização")
    })
    
    # Executar ação se solicitada
    action = result.get("action")
    if action:
        action_result = await execute_action(action, result.get("action_params", {}), user_context)
        result["action_result"] = action_result
    
    return result


async def execute_action(action: str, params: dict, user_context: dict) -> dict:
    """Executar ação solicitada pelo assistente"""
    
    org_id = user_context.get("org_id")
    
    if action == "create_task":
        task_data = {
            "title": params.get("title"),
            "type": params.get("type", "task"),
            "priority": params.get("priority", "medium"),
            "space_id": params.get("space_id"),
            "creator_id": user_context.get("user_id"),
            "status": "backlog",
            "source": "assistant"
        }
        task = await db.create_task(task_data)
        return {"success": True, "task": task}
    
    elif action == "list_tasks":
        tasks = await db.get_tasks_by_org(org_id)
        return {"success": True, "count": len(tasks), "tasks": tasks[:10]}
    
    elif action == "get_summary":
        members = await db.get_members_by_org(org_id)
        tasks = await db.get_tasks_by_org(org_id)
        
        open_tasks = [t for t in tasks if t.get("status") != "done"]
        overdue = [t for t in open_tasks if t.get("due_date") and t["due_date"] < "now"]
        
        return {
            "success": True,
            "summary": {
                "total_members": len(members),
                "total_tasks": len(tasks),
                "open_tasks": len(open_tasks),
                "overdue_tasks": len(overdue)
            }
        }
    
    elif action == "block_calendar":
        # TODO: integrar com Google Calendar
        return {"success": True, "message": "Bloco criado (simulado)"}
    
    elif action == "generate_report":
        # TODO: gerar PDF
        return {"success": True, "message": "Relatório será enviado por email"}
    
    return {"success": False, "error": "Ação não reconhecida"}
