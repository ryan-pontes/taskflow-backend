from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from app.config import settings

# State compartilhado entre agentes
class AgentState(TypedDict):
    # Input
    action: str  # "create_task", "chat", "enrich", "delegate", "profile"
    input_data: dict
    user_context: dict
    
    # Output de cada agente
    delegation_result: dict | None
    enrichment_result: dict | None
    assistant_result: dict | None
    profile_result: dict | None
    
    # Final
    final_response: dict | None
    error: str | None


# LLM base (lazy — instanciado só quando necessário)
_llm = None
_llm_fast = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            api_key=settings.OPENAI_API_KEY
        )
    return _llm

def get_llm_fast():
    global _llm_fast
    if _llm_fast is None:
        _llm_fast = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=settings.OPENAI_API_KEY
        )
    return _llm_fast


# Router - decide qual agente chamar
def router(state: AgentState) -> Literal["delegation", "enrichment", "assistant", "profile", "finalize"]:
    action = state.get("action", "")
    
    if action == "create_task":
        # Primeiro enriquecer, depois delegar
        if not state.get("enrichment_result"):
            return "enrichment"
        elif not state.get("delegation_result"):
            return "delegation"
        else:
            return "finalize"

    elif action == "chat":
        return "assistant"

    elif action == "enrich":
        return "enrichment"

    elif action == "delegate":
        return "delegation"

    elif action == "profile":
        return "profile"

    return "finalize"


# Import dos agentes (serão criados em arquivos separados)
from app.agents.delegation import run_delegation_agent
from app.agents.enrichment import run_enrichment_agent
from app.agents.assistant import run_assistant_agent
from app.agents.profile import run_profile_agent


# Nodes do grafo
async def delegation_node(state: AgentState) -> AgentState:
    result = await run_delegation_agent(
        task=state["input_data"],
        user_context=state["user_context"]
    )
    return {"delegation_result": result}


async def enrichment_node(state: AgentState) -> AgentState:
    result = await run_enrichment_agent(
        task=state["input_data"],
        user_context=state["user_context"]
    )
    return {"enrichment_result": result}


async def assistant_node(state: AgentState) -> AgentState:
    result = await run_assistant_agent(
        message=state["input_data"].get("message", ""),
        user_context=state["user_context"]
    )
    return {"assistant_result": result, "final_response": result}


async def profile_node(state: AgentState) -> AgentState:
    data = {**state["input_data"], "openai_key": state["user_context"].get("openai_key")}
    result = await run_profile_agent(
        member_id=state["input_data"].get("member_id"),
        action=state["input_data"].get("profile_action", "analyze"),
        data=data
    )
    return {"profile_result": result}


async def finalize_node(state: AgentState) -> AgentState:
    """Compilar resultado final"""
    response = {
        "success": True,
        "action": state["action"]
    }
    
    if state.get("enrichment_result"):
        response["enrichment"] = state["enrichment_result"]
    
    if state.get("delegation_result"):
        response["delegation"] = state["delegation_result"]
    
    if state.get("assistant_result"):
        response["assistant"] = state["assistant_result"]
    
    if state.get("profile_result"):
        response["profile"] = state["profile_result"]
    
    return {"final_response": response}


# Construir o grafo
def build_graph():
    workflow = StateGraph(AgentState)
    
    # Adicionar nodes
    workflow.add_node("delegation", delegation_node)
    workflow.add_node("enrichment", enrichment_node)
    workflow.add_node("assistant", assistant_node)
    workflow.add_node("profile", profile_node)
    workflow.add_node("finalize", finalize_node)
    
    # Entry point
    workflow.set_conditional_entry_point(router)
    
    # Edges
    workflow.add_edge("enrichment", "delegation")
    workflow.add_edge("delegation", "finalize")
    workflow.add_edge("assistant", "finalize")
    workflow.add_edge("profile", "finalize")
    workflow.add_edge("finalize", END)
    
    return workflow.compile()


# Instância do grafo
agent_graph = build_graph()


# Função principal para invocar
async def run_agents(action: str, input_data: dict, user_context: dict) -> dict:
    """Executar pipeline de agentes"""
    initial_state: AgentState = {
        "action": action,
        "input_data": input_data,
        "user_context": user_context,
        "delegation_result": None,
        "enrichment_result": None,
        "assistant_result": None,
        "profile_result": None,
        "final_response": None,
        "error": None
    }
    
    try:
        result = await agent_graph.ainvoke(initial_state)
        return result.get("final_response", {"error": "No response"})
    except Exception as e:
        return {"error": str(e), "success": False}
