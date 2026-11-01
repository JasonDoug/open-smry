"""
LangGraph Multi-Agent StateGraph for Summary AI.
Coordinates:
- Supervisor Node (Task classification & routing)
- Summarizer Node (Single-pass & Map-Reduce 5-mode summaries)
- QA Synthesizer & Citation Verifier Critic Loop (Verifiable exact-passage Q&A)
- Context Analyst Node (Highlighted excerpt deep dives)
- Conversational Chat Node (Interactive reading discussion)
"""
from __future__ import annotations

from typing import Any, Dict, Literal

from langgraph.graph import END, START, StateGraph

from app.agents.context_analyst import run_context_analyst_agent
from app.agents.llm_router import chat_completion
from app.agents.qa_critic import qa_critic_node, qa_synthesizer_node
from app.agents.state import AgentState
from app.agents.summarizer import run_summarizer_agent


def supervisor_node(state: AgentState) -> Dict[str, Any]:
    """
    Validates task type and initializes iteration counter.
    """
    iteration = state.get("iteration", 0)
    return {"iteration": iteration}


def route_task(
    state: AgentState,
) -> Literal["summarizer_node", "qa_synthesizer_node", "context_analyst_node", "chat_node"]:
    task_type = state.get("task_type", "summarize")
    if task_type == "ask_document":
        return "qa_synthesizer_node"
    if task_type == "ask_context":
        return "context_analyst_node"
    if task_type == "chat":
        return "chat_node"
    return "summarizer_node"


def route_critic(state: AgentState) -> Literal["qa_synthesizer_node", "__end__"]:
    verdict = state.get("critic_verdict", "pass")
    iteration = state.get("iteration", 0)
    if verdict == "revise" and iteration <= 1:
        return "qa_synthesizer_node"
    return "__end__"


async def chat_node(state: AgentState) -> AgentState:
    """
    Direct conversational chat node.
    """
    messages = state.get("messages") or []
    provider = state.get("provider")
    model = state.get("model")

    text, provider_used, model_used = await chat_completion(
        messages, provider=provider, model=model
    )
    state["final_output"] = text
    state["provider_used"] = provider_used
    state["model_used"] = model_used
    return state


def build_summary_agent_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("supervisor_node", supervisor_node)
    graph.add_node("summarizer_node", run_summarizer_agent)
    graph.add_node("qa_synthesizer_node", qa_synthesizer_node)
    graph.add_node("qa_critic_node", qa_critic_node)
    graph.add_node("context_analyst_node", run_context_analyst_agent)
    graph.add_node("chat_node", chat_node)

    graph.add_edge(START, "supervisor_node")
    graph.add_conditional_edges(
        "supervisor_node",
        route_task,
        {
            "summarizer_node": "summarizer_node",
            "qa_synthesizer_node": "qa_synthesizer_node",
            "context_analyst_node": "context_analyst_node",
            "chat_node": "chat_node",
        },
    )

    graph.add_edge("summarizer_node", END)
    graph.add_edge("context_analyst_node", END)
    graph.add_edge("chat_node", END)

    # QA Critic loop
    graph.add_edge("qa_synthesizer_node", "qa_critic_node")
    graph.add_conditional_edges(
        "qa_critic_node",
        route_critic,
        {
            "qa_synthesizer_node": "qa_synthesizer_node",
            "__end__": END,
        },
    )

    return graph


compiled_agent_graph = build_summary_agent_graph().compile()
