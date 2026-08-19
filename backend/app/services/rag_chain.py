"""
Level 1 conversational RAG chain: retrieval + tool-augmented answers with
per-session memory.

Exposes `conversational_rag`, importable and invokable standalone:

    from app.services.rag_chain import conversational_rag
    conversational_rag.invoke(
        {"question": "..."},
        config={"configurable": {"session_id": "demo"}},
    )
"""

import logging
from pathlib import Path

from dotenv import load_dotenv

from langchain_chroma import Chroma
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from typing import AsyncIterator

from app.core.tools import query_recent_logs

load_dotenv()

logger = logging.getLogger("sentinel.rag_chain")

PERSIST_DIR = Path(__file__).resolve().parents[3]/"chroma_sentinel"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2" # embedding model to genrate vector of user Q. must be same of that we used to create vector of the documents, from where we will taking help.

# Load the existing persisted store - documents are NOT re-embedded here.
# The embedding function is still required at query time, to embed the
# user's question into the same vector space the stored chunks live in.

embeddings = HuggingFaceEmbeddings(model_name = EMBEDDING_MODEL)
vectorstore = Chroma(persist_directory=str(PERSIST_DIR), embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

# llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0) -> depricated
llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
tools=[query_recent_logs]
tools_by_name = {t.name: t for t in tools}
llm_with_tools = llm.bind_tools(tools)

SYSTEM_PROMPT = """You are Sentinel, an SRE assistant.

Rules:
1. Answer ONLY using the provided runbook context below and/or the output of
   the query_recent_logs tool. Never use outside knowledge.
2. Whenever you use information from the context, cite the source file in
   square brackets, e.g. [connection-pool-exhaustion.md].
3. If the user asks about current, recent, or live log activity or errors for
   a named service, call the query_recent_logs tool before answering.
4. If the question is unrelated to DevOps, infrastructure, or the runbook
   knowledge base, politely refuse and explain you can only help with
   incident/runbook questions. Do not attempt to answer it anyway.
5. If the context is insufficient to answer confidently, say so explicitly
   rather than guessing."""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder("history", optional=True),
    ("human", "Context:\n{context}\n\nQuestion: {question}"),
])

def format_docs(docs) -> str:
    if not docs:
        return "(no relevant runbook context found)"
    return "\n\n".join(
    f"[{Path(d.metadata.get('source', 'unknown')).name}] {d.page_content}"
    for d in docs
)

def _run_chain(inputs: dict) -> str:
    """
    Core orchestration step, wrapped as a RunnableLambda.

    Plain LCEL piping (prompt | llm_with_tools | StrOutputParser) cannot
    correctly handle tool calls: when the model decides to call a tool, its
    response has empty `.content` and a populated `.tool_calls` list instead -
    there is nothing for StrOutputParser to parse yet. Executing the tool and
    feeding the result back for a second, final generation requires an
    explicit conditional step, which is what this function does. Returning a
    plain string here is the functional equivalent of StrOutputParser for
    this chain's purposes.
    """

    messages = prompt.invoke(inputs).to_messages()
    ai_msg = llm_with_tools.invoke(messages)

    if not ai_msg.tool_calls:
        logger.info("No tool call - answering directly from context")
        return ai_msg.content

    logger.info("tool call(s) requested: %s", [tc["name"] for tc in ai_msg.tool_calls])
    messages.append(ai_msg)

    for tool_call in ai_msg.tool_calls:
        tool_fn = tools_by_name.get(tool_call["name"])
        result = tool_fn.invoke(tool_call["args"]) if tool_fn else f"Unknown tool: {tool_call['name']}"
        messages.append(ToolMessage(content=str(result), tool_call_id = tool_call["id"]))


    final_msg = llm_with_tools.invoke(messages)
    return final_msg.content

rag_chain = (
    RunnableParallel(
        context=(lambda x: x["question"]) | retriever | RunnableLambda(format_docs),
        question = lambda x: x["question"],
        history = lambda x: x.get("history", []),
    )
    | RunnableLambda(_run_chain)
)

_session_store: dict = {}


def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in _session_store:
        _session_store[session_id] = InMemoryChatMessageHistory()

    return _session_store[session_id]


conversational_rag = RunnableWithMessageHistory(
    rag_chain,
    get_session_history,
    input_messages_key="question",
    history_messages_key="history",
)

async def astream_answer(question:str, session_id: str) -> AsyncIterator[str]:
    """
    Real token-by-token streaming path for the FastAPI SSE endpoint.

    `conversational_rag` above is invoke-only: its final step, `_run_chain`,
    is a plain synchronous function, and LangChain cannot stream through a
    plain function token-by-token — `.astream()` on it just runs the function
    once and yields the whole result as a single chunk.

    This function makes the same tool-decision call as `_run_chain` (still
    blocking — its raw output is never shown to the user, so there's nothing
    to stream there anyway), but the FINAL answer generation calls
    `llm_with_tools.astream()` directly — the chat model object itself, which
    natively supports token streaming — and yields each chunk as it arrives.

    Cost of this design: two LLM calls minimum per request (one to decide on
    a tool call, one to generate the streamed answer), even when no tool
    fires. See docs/decisions.md for why this trade-off is acceptable at
    Level 1's scale, and how Level 2's LangGraph nodes avoid it.

    Session history is shared with `conversational_rag` via the same
    `get_session_history` store, so the streaming endpoint and the
    synchronous CLI/test path stay consistent within one session_id.
    """
    history = get_session_history(session_id)

    docs = await retriever.ainvoke(question)
    context = format_docs

    messages= prompt.invoke(
        {"context": context, "question": question, "history": history.messages}
    ).to_messages()

    ai_msg = await llm_with_tools.ainvoke(messages)

    if ai_msg.tool_calls:
        logger.info("Tool call(s) requested: %s", [tc["name"] for tc in ai_msg.tool_calls])
        messages.append(ai_msg)
        for tool_call in ai_msg.tool_calls:
            tool_fn = tools_by_name.get(tool_call["name"])
            result = (
                await tool_fn.ainvoke(tool_call["args"])
                if tool_fn else f"Unknown tool: {tool_call['name']}"
            )
            messages.append(ToolMessage(content=str(result), tool_call_id = tool_call["id"]))

    full_text = ""
    async for chunk in llm_with_tools.astream(messages):
        piece = chunk.content or ""
        if piece:
            full_text += piece
            yield piece


    history.add_message(HumanMessage(content=question))
    history.add_message(AIMessage(content=full_text))


if __name__ == "__main__":
    logging.basicConfig(level = logging.INFO)
    demo_session = "cli-smoke-test"
    for q in [
        "What do we do when Redis connection pool is exhausted?",
        "Check recent logs for checkout-service in the last 10 minutes",
        "Give me a recipe for chocolate cake",
    ]:
        print(f"\n> {q}")
        answer = conversational_rag.invoke(
            {"question": q}, config={"configurable": {"session_id": demo_session}}

        )
        print(answer)