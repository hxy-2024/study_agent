from langgraph.graph import END, StateGraph

from app.domain.session_tutor_graph import nodes
from app.domain.session_tutor_graph.state import SessionTutorGraphState


def build_session_tutor_graph(
    db_session,
    embedding_provider,
    answer_provider,
    checkpointer=None,
):
    async def load_session_context(state):
        return await nodes.load_session_context(state, db_session=db_session)

    async def persist_user_message(state):
        return await nodes.persist_user_message(state, db_session=db_session)

    async def load_chapter_supervision(state):
        return await nodes.load_chapter_supervision(state, db_session=db_session)

    async def retrieve_evidence(state):
        return await nodes.retrieve_evidence(
            state,
            db_session=db_session,
            embedding_provider=embedding_provider,
        )

    async def generate_answer(state):
        return await nodes.generate_answer(state, answer_provider=answer_provider)

    async def persist_assistant_message(state):
        return await nodes.persist_assistant_message(state, db_session=db_session)

    async def record_agent_run(state):
        return await nodes.record_graph_agent_run(state, db_session=db_session)

    graph = StateGraph(SessionTutorGraphState)
    graph.add_node("load_session_context", load_session_context)
    graph.add_node("persist_user_message", persist_user_message)
    graph.add_node("load_chapter_supervision", load_chapter_supervision)
    graph.add_node("retrieve_evidence", retrieve_evidence)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("persist_assistant_message", persist_assistant_message)
    graph.add_node("extract_learning_signals", nodes.extract_learning_signals)
    graph.add_node("record_agent_run", record_agent_run)

    graph.set_entry_point("load_session_context")
    graph.add_edge("load_session_context", "persist_user_message")
    graph.add_edge("persist_user_message", "load_chapter_supervision")
    graph.add_edge("load_chapter_supervision", "retrieve_evidence")
    graph.add_edge("retrieve_evidence", "generate_answer")
    graph.add_edge("generate_answer", "persist_assistant_message")
    graph.add_edge("persist_assistant_message", "extract_learning_signals")
    graph.add_edge("extract_learning_signals", "record_agent_run")
    graph.add_edge("record_agent_run", END)
    return graph.compile(checkpointer=checkpointer)
