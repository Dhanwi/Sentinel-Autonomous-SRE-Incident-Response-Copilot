import { useCallback, useRef, useState } from "react";
import type { ChatMessage, SSEEnvelope } from "../types/chat";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

{/*
    SSE events can arrive split across multiple stream reads (a token's JSON
    might be cut mid-way through a chunk boundary), and a single read can also
    contain several complete events at once. This buffers partial data and
    only parses complete "event: ...\ndata: ...\n\n" blocks, carrying any
    incomplete trailing block over to the next read.
*/}

function extractCompleteEvents(buffer: string): { events: SSEEnvelope[]; rest: string} {
    const events: SSEEnvelope[] = [];
    const boundary = buffer.lastIndexOf('\n\n');
    if(boundary === -1) return {events, rest: buffer};

    const ready = buffer.slice(0, boundary);
    const rest = buffer.slice(boundary + 2);

    for(const block of ready.split("\n\n").filter(Boolean)){
        const dataLine = block
            .split("\n")
            .find((line)=> line.startsWith("data:"));
        if (!dataLine) continue;

        const raw = dataLine.slice(5).trim();
        if(!raw) continue;

        try{
            events.push(JSON.parse(raw) as SSEEnvelope);
        } catch{
            // Shouldn't happen once we only parse complete blocks, but never let
            // one malformed event crash the whole stream.
        }
    }

    return {events, rest};
}

export function useChatStream(){
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [isStreaming, setIsStreaming] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const sessionIdRef = useRef<string>(crypto.randomUUID());

    const sendMessage = useCallback(
        async (question: string) => {
            const trimmed = question.trim();
            if(!trimmed || isStreaming) return;

            setError(null);
            const userMessage: ChatMessage = {
                id: crypto.randomUUID(),
                role: "user",
                content: trimmed,
                timestamp: Date.now(),
            };
            const assistantId = crypto.randomUUID();
            const assistantMessage: ChatMessage = {
                id: assistantId,
                role: "assistant",
                content: "",
                timestamp: Date.now(),
            };

            setMessages((prev)=> [...prev, userMessage,  assistantMessage]);
            setIsStreaming(true);

            const markAssistantError = (message: string) =>{
                setError(message);
                setMessages((prev) =>
                    prev.map((m) =>
                        m.id === assistantId 
                            ? {...m, content: m.content || message, isError: true}
                            : m
                    )
                );
            };
            try{
                const response = await fetch(`${API_BASE_URL}/chat/strem`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ question: trimmed, session_id: sessionIdRef.current }),
                });

                if (response.status === 422) {
                    const body = await response.json().catch(()=>null);
                    const detail = body?.detail?.[0]?.msg ?? "The request was invalid.";
                    throw new Error(detail);
                }
                if (!response.ok || !response.body) {
                    throw new Error(`Request failed with status ${response.status}`);
                }

                const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
                let buffer = "";

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break; // means event agr done aa rha, that means its completed, we have recieved all the tokens(data)

                    buffer += value;
                    const {events, rest} = extractCompleteEvents(buffer);
                    buffer = rest;

                    for(const evt of events) {
                        if(evt.event === "token") {
                            setMessages((prev) => 
                                prev.map((m)=> 
                                    m.id === assistantId ? { ...m, content: m.content + evt.data } : m
                                )
                            );
                        } else if (evt.event === "error") {
                          throw new Error(evt.error_detail ?? "The assistant hit an error while responding.");
                        }
                        // "done" needs no action, loop naturally ends when the reader closes.
                    }
                }
            } catch(err) {
                const message = err instanceof Error ? err.message : "Connection lost. Please try again.";
                markAssistantError(message);
            } finally {
                setIsStreaming(false);
            }

        },
        [isStreaming]
    );

    return { messages, isStreaming, error, sendMessage}
}