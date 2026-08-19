from typing import Literal, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming request body for POST /chat/stream."""
    question: str = Field(min_length = 1, description = "The user's question")
    session_id: str = Field(min_length= 1, description = "Client-generated session identifier for memory continuity")


class ChatStreamEvent(BaseModel):
    """
    Typed representation of a single SSE event sent to the client.
    Mirrors the shape the React frontend's SSE parser expects - keep this
    in sync with hooks/useChatStream.ts when the frontend is built.
    """

    event: Literal["token", "error", "done"]
    data: str
    error_detail: Optional[str] = None