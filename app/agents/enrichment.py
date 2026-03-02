from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings

_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, api_key=settings.OPENAI_API_KEY)
    return _llm

ENRICHMENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Você é um agente especializado em enriquecer tarefas.

Baseado no título e tipo da tarefa, gere:
1. Uma descrição clara e útil
2. Subtarefas relevantes (se aplicável)
3. Critérios de aceite (para bugs e features)
4. Estimativa de horas

Responda SEMPRE em JSON válido:
{{
    "description": "descrição gerada",
    "subtasks": [
        {{"title": "subtarefa 1", "completed": false}},
        {{"title": "subtarefa 2", "completed": false}}
    ],
    "acceptance_criteria": ["critério 1", "critério 2"],
    "estimated_hours": 4,
    "tags_suggested": ["tag1", "tag2"]
}}"""),
    ("human", """
Tarefa:
- Título: {title}
- Tipo: {type}
- Prioridade: {priority}

Contexto adicional:
{context}

Enriqueça esta tarefa com informações úteis.""")
])


async def run_enrichment_agent(task: dict, user_context: dict) -> dict:
    """Enriquecer tarefa com descrição, subtarefas, etc."""
    
    chain = ENRICHMENT_PROMPT | get_llm() | JsonOutputParser()
    
    # Contexto baseado no tipo de tarefa
    context = ""
    if task.get("type") == "bug":
        context = "É um bug. Inclua subtarefas para reprodução, análise, correção e teste."
    elif task.get("type") == "project":
        context = "É um projeto maior. Divida em fases e marcos."
    elif task.get("type") == "urgent":
        context = "É urgente. Foque em ações imediatas."
    
    result = await chain.ainvoke({
        "title": task.get("title", ""),
        "type": task.get("type", "task"),
        "priority": task.get("priority", "medium"),
        "context": context
    })
    
    return result
