export type MessageRole = "user" | "assistant";

export interface ChatMessage {
    id: string;
    role: MessageRole;
    content: string;
    timestamp: number;
    isError?: boolean; //? represent that isError is type of boolean
}

// here this must stay in sync with backend/app/schemas/chat.py -> ChatStreamEvent.
export interface SSEEnvelope {
    event: "token" | "error" | "done";
    data: string;
    error_detail?: string | null;
}