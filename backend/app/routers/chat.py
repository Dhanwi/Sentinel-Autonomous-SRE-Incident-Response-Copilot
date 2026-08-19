"""
POST /chat/stream — Server-Sent Events endpoint streaming the Level 1
RAG chain's answer token-by-token.
"""
import logging

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.schemas.chat import ChatRequest,ChatStreamEvent
from app.services.rag_chain import astream_answer

logger = logging.getLogger("sentinel.routers.chat")
router = APIRouter(prefix="/chat", tags=["chat"])


def _sse_event(event: str, data: str, error_detail: str | None = None) -> dict:
    """Validate the outgoing event against ChatStreamEvent before sending it."""
    validated = ChatStreamEvent(event = event, data=data, error_detail = error_detail)
    # ChatStreamEvent is a data structure used in AI APIs to send partial AI responses in real-time. 
    # Instead of waiting for a full response, the AI model streams data in smaller chunks. 
    # This lets applications display text, reasoning, or tool usage immediately as they happen.
    return {"event": validated.event, "data": validated.model_dump_json()}

@router.post("/stream")
async def stream_chat(req: ChatRequest):
    async def event_generator():
        try: 
            async for token in astream_answer(req.question, req.session_id):
                yield _sse_event("token", token)
            yield _sse_event("done", "")
        except Exception as exc:
            logger.exception("chat stream failed for session_id=%s", req.session_id)
            yield _sse_event("error", "", error_detail=str(exc))

    return EventSourceResponse(event_generator())

