from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings
from app.integrations.supabase import get_member_with_user_info, update_member_profile

_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-4o", temperature=0.3, api_key=settings.OPENAI_API_KEY)
    return _llm

PROFILE_CONVERSATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Você é um agente de RH amigável do TaskFlow.

Sua função é conversar com novos membros para entender:
1. Habilidades técnicas (linguagens, frameworks, ferramentas)
2. Soft skills
3. Preferências de trabalho (independente vs colaborativo)
4. Objetivos de carreira
5. Pontos que quer desenvolver

Seja amigável e faça perguntas naturais. 
Extraia informações estruturadas da conversa.

Responda em JSON:
{{
    "message": "sua mensagem amigável",
    "extracted_data": {{
        "skills": [{{"name": "skill", "level": "beginner|intermediate|advanced|expert"}}],
        "soft_skills": ["skill"],
        "work_style": "independent|collaborative|mixed",
        "career_goals": "texto",
        "development_areas": ["área"]
    }},
    "profile_complete": false,
    "next_topic": "skills|soft_skills|work_style|goals|development|complete"
}}"""),
    ("human", """
Histórico da conversa:
{conversation_history}

Perfil atual:
{current_profile}

Última mensagem do membro:
{member_message}

Continue a conversa para completar o perfil.""")
])


PROFILE_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Você é um especialista em análise de perfis profissionais.

Analise o perfil do membro e suas tarefas para gerar insights:
1. Pontos fortes
2. Áreas de oportunidade
3. Tipos de tarefa ideais para esta pessoa
4. Sugestões de desenvolvimento

Responda em JSON:
{{
    "strengths": ["ponto forte 1"],
    "opportunities": ["oportunidade 1"],
    "ideal_task_types": ["bug", "project"],
    "development_suggestions": ["sugestão 1"],
    "fit_score_by_task_type": {{
        "bug": 0.8,
        "project": 0.6,
        "urgent": 0.9,
        "task": 0.7
    }}
}}"""),
    ("human", """
Perfil do membro:
{profile}

Histórico de tarefas:
{task_history}

Analise e gere insights.""")
])


async def run_profile_agent(member_id: str, action: str, data: dict) -> dict:
    """Gerenciar perfil de liderado"""
    
    if action == "conversation":
        return await handle_conversation(member_id, data)
    elif action == "analyze":
        return await analyze_profile(member_id)
    elif action == "update":
        return await update_profile(member_id, data)
    
    return {"error": "Ação não reconhecida"}


async def handle_conversation(member_id: str, data: dict) -> dict:
    """Continuar conversa para construir perfil"""
    
    member = await get_member_with_user_info(member_id)
    if not member:
        return {"error": "Membro não encontrado"}
    
    chain = PROFILE_CONVERSATION_PROMPT | get_llm() | JsonOutputParser()
    
    result = await chain.ainvoke({
        "conversation_history": data.get("history", "Início da conversa"),
        "current_profile": member.get("profile", {}),
        "member_message": data.get("message", "Olá!")
    })
    
    # Atualizar perfil com dados extraídos
    if result.get("extracted_data"):
        current = member.get("profile", {})
        extracted = result["extracted_data"]
        
        # Merge dados
        if extracted.get("skills"):
            current["skills"] = extracted["skills"]
        if extracted.get("soft_skills"):
            current["soft_skills"] = extracted["soft_skills"]
        if extracted.get("work_style"):
            current["work_style"] = extracted["work_style"]
        if extracted.get("career_goals"):
            current["career_goals"] = extracted["career_goals"]
        
        await update_member_profile(member_id, current)
    
    return result


async def analyze_profile(member_id: str) -> dict:
    """Analisar perfil e gerar insights"""
    from app.integrations.supabase import get_tasks_by_assignee
    
    member = await get_member_with_user_info(member_id)
    if not member:
        return {"error": "Membro não encontrado"}
    
    tasks = await get_tasks_by_assignee(member_id)
    
    chain = PROFILE_ANALYSIS_PROMPT | get_llm() | JsonOutputParser()
    
    result = await chain.ainvoke({
        "profile": member.get("profile", {}),
        "task_history": tasks[:20]  # Últimas 20 tarefas
    })
    
    return result


async def update_profile(member_id: str, data: dict) -> dict:
    """Atualizar perfil manualmente (gestor)"""
    
    profile_data = data.get("profile", {})
    updated = await update_member_profile(member_id, profile_data)
    
    return {"success": True, "profile": updated}
