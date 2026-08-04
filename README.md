# Sentinel: Autonomous SRE Incident Response Copilot
### A Two-Tier Capstone Guide (LangChain → LangGraph → Production Multi-Agent Systems)

---

## 0. Why This Project

Most RAG portfolio projects are "chat with my PDF." That proves retrieval competence but nothing about **state, control flow, or production engineering** — the things that actually separate a junior LangChain user from a Principal AI Engineer.

**Sentinel** is an incident-response copilot for an SRE/DevOps team. It is deliberately chosen because it has a *natural* two-tier story:

- Level 1 is a legitimate, shippable product on its own: "ask questions about runbooks and past incidents, get grounded answers."
- Level 2 is not RAG-with-extra-steps — it requires genuine **stateful orchestration**: parallel investigation across services, a human gate before anything touches production, and durable execution that survives a restart. That's exactly what LangGraph exists for, so the upgrade is motivated by the domain, not bolted on to hit a rubric.

It also maps cleanly onto your required stack: FastAPI async services, a vector DB, WebSocket/SSE streaming, and a React dashboard that actually *needs* real-time updates (an incident timeline) rather than a chat bubble that could've been a REST call.

---

## 1. Project Concept & Evolution

### The premise
An engineering org has a knowledge base of **runbooks, architecture docs, and past incident postmortems**. When a new incident fires (via a webhook or manual entry — e.g., "checkout-service p99 latency spike"), Sentinel should help the on-call engineer.

### Level 1 — "Ask Sentinel" (Foundational RAG + Chains)
A grounded Q&A assistant over the knowledge base:
- Ingests runbooks/postmortems into a vector store.
- Answers "what's the standard mitigation for a Redis connection pool exhaustion?" with citations.
- Has one bound tool (a mock log-query function) so a single LCEL chain can decide to call a tool before answering.
- Conversational memory across a single session.
- Streams tokens to a simple React chat UI over SSE.

This is a complete, demoable product: a smarter internal search bar. **No graph, no persistence beyond one session, no autonomy.**

### Level 2 — "Sentinel Autopilot" (Stateful Multi-Agent System)
The same knowledge base now powers an **autonomous investigation team** triggered by an incident event:

1. **Triage Agent** — classifies severity and affected services from the alert payload.
2. **Diagnostic Agents (parallel subgraph)** — one sub-agent per suspected service (`db`, `api-gateway`, `network`), each independently uses RAG + tools (log/metrics lookups) to gather evidence. They run **concurrently** via LangGraph's `Send` API — a real map-reduce fan-out, not a for-loop.
3. **Synthesis / Root-Cause Agent** — merges sub-agent findings into a single hypothesis.
4. **Remediation Planner** — proposes a concrete action (e.g., "restart pod X", "roll back deploy Y") using RAG over past postmortems for precedent.
5. **Human-in-the-Loop Gate** — the graph **halts** (`interrupt()`dart) and pushes the proposed action to the React dashboard. A human must Approve / Edit / Reject before anything proceeds. This is the crux of "enterprise-grade" — no agent executes a production-impacting action unsupervised.
6. **Execution Agent** — runs the approved action (mocked, but wired like a real tool).
7. **Postmortem Writer** — generates a draft postmortem doc from the full run's transcript.

The entire run is **checkpointed** (SQLite/Postgres) by `thread_id = incident_id`, so if the server restarts mid-investigation, the graph resumes exactly where it left off — including at the human-approval interrupt. This is the single feature that most distinguishes "I built an agent" from "I built a stateful, durable, production system."

---

## 2. Two-Tier Architecture & Learning Roadmap

| # | Concept | Level | Where it lives in Sentinel |
|---|---|---|---|
| 1 | Prompt templates, output parsers (Pydantic) | **L1** | Grounded-answer chain |
| 2 | Embeddings + vector store (Chroma) + retriever | **L1** | Runbook/postmortem ingestion |
| 3 | LCEL: `RunnableSequence`, `RunnableParallel`, `RunnablePassthrough` | **L1** | RAG chain composition |
| 4 | Tool binding (`bind_tools`) + single-hop tool call | **L1** | Mock log-lookup tool |
| 5 | Chat history (trimmed, session-scoped) | **L1** | `RunnableWithMessageHistory` |
| 6 | SSE token streaming | **L1** | FastAPI `/chat/stream` |
| 7 | `StateGraph`, typed state (`TypedDict` + `add_messages`) | **L2** | Core orchestration graph |
| 8 | Conditional edges / routing | **L2** | Triage → route by severity |
| 9 | `Send` API — dynamic parallel fan-out (map-reduce agents) | **L2** | Parallel diagnostic subgraph |
| 10 | Subgraphs (graph-as-a-node) | **L2** | Diagnostic sub-agent is its own compiled graph |
| 11 | Checkpointers (`MemorySaver` → `SqliteSaver`/`PostgresSaver`) | **L2** | Durable, resumable runs per `thread_id` |
| 12 | Human-in-the-loop: `interrupt()` + `Command(resume=...)` | **L2** | Remediation approval gate |
| 13 | Long-term memory / `Store` API (cross-thread) | **L2** | "Sentinel remembers this service has flapped before" |
| 14 | `astream_events` (v2) for node/token-level streaming | **L2** | WebSocket incident timeline |
| 15 | Supervisor / orchestrator pattern | **L2** | Root graph coordinating sub-agents |
| 16 | Multi-thread session management, auth | **L2 → prod** | FastAPI dependency-injected `thread_id` |
| 17 | Observability (LangSmith tracing) | **L2 → prod** | Attach to both levels, but essential once graphs branch |

**Suggested build order:** items 1–6 fully working end-to-end (including the React chat UI) *before* touching LangGraph. Don't let architecture astronautics block you from having a working demo early — Level 1 alone is a legitimate stopping point if time runs out.

---

## 3. Milestones (recommended order)

1. Ingestion + retriever working in Jupyter, sanity-checked with 5 manual queries.
2. Level 1 LCEL chain + tool binding + memory, fully working in Jupyter.
3. Level 1 FastAPI SSE endpoint + React `ChatWindow` — **ship this as a checkpoint.**
4. Level 2 state schema + linear graph (triage → synthesize → plan, no parallelism yet) working in Jupyter.
5. Add the `Send`-based parallel diagnostic subgraph.
6. Add the checkpointer; prove resumability by restarting the kernel mid-run.
7. Add the `interrupt()` human gate; prove resumability *past* an interrupt.
8. Wire the WebSocket router + `IncidentDashboard` + `ApprovalModal` — **ship this as the final deliverable.**
9. Polish: LangSmith tracing screenshots, a README with an architecture diagram, and a 60-second demo GIF showing the approval gate firing.

