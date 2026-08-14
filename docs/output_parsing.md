# Structured Output: Native Function Calling vs. Prompt-Based Parsing

Two approaches to getting a validated Pydantic object out of an LLM call.
Sentinel implements both — native as the default, prompt-based as an
automatic fallback — because relying on a single strategy is a single point
of failure once this runs in production against a model or provider you
don't fully control.

## Native structured output — `llm.with_structured_output(Schema)`

**How it works:** the schema is converted to a JSON Schema / tool definition
and passed to the model's native function/tool-calling API. The provider's
own inference-time constrained decoding (or tool-call formatting) guarantees
the output matches the schema's shape at the API level, before it even
reaches LangChain's parsing code.

**Pros**
- One LLM call. Lowest latency and lowest token usage of the two approaches.
- Schema enforcement happens at the model-provider level — malformed output
  is far rarer, because the provider's own serving stack is constraining
  generation, not just asking nicely via prompt instructions.
- No prompt-engineering required to describe the schema — the schema
  definition is the only source of truth about desired output shape.

**Cons**
- Requires a specific model capability (tool/function calling). Not every
  hosted model supports it, and support varies even within one provider's
  model lineup (e.g. some smaller/older Groq-hosted models do not).
- Provider-specific edge cases still exist: some providers handle deeply
  nested schemas, `Enum` types, or `Optional` fields less reliably than
  others — this is not a universally solved problem, just a much better one.
- Harder to debug when it *does* fail — you get an opaque provider-side
  tool-call error rather than a Python-level validation error you can
  inspect line by line.

## Prompt-based parsing — `PydanticOutputParser` + `OutputFixingParser`

**How it works:** the schema's field descriptions are rendered into
plain-English format instructions and appended to the prompt. The model
generates ordinary text (ideally JSON) which is then validated in Python via
Pydantic. If validation fails, `OutputFixingParser` makes a **second** LLM
call, showing the model its own broken output plus the specific validation
error, and asks it to correct it.

**Pros**
- Works with any text-completion model — no tool-calling support required.
  This is the only option for smaller/local models or providers without a
  function-calling API.
- Fully inspectable failure mode: a validation error is a normal Python
  exception with a clear message, not an opaque API-level rejection.
- The self-healing step means a single malformed generation doesn't
  necessarily result in a hard failure for the caller.

**Cons**
- At least one LLM call, up to two if repair is triggered — meaningfully
  higher latency (roughly 1.5-2x in our Cell 6 timing test) and token cost
  in the worst case.
- Schema enforcement is only as good as the model's willingness to follow
  the format instructions in the prompt — there's no hard guarantee at the
  API level, only a strong prompt-level nudge.
- The repair call itself can fail (a second malformed generation), so this
  is a mitigation, not a 100% guarantee — production code should still
  handle a final `OutputFixingParser` failure explicitly rather than assume
  it always succeeds.

## Summary comparison

| Dimension | Native (`with_structured_output`) | Prompt-based (`PydanticOutputParser` + fixing) |
|---|---|---|
| LLM calls (typical) | 1 | 1 (2 if a repair is triggered) |
| Latency | Lowest | Higher, worse in the repair case |
| Token usage | Lowest (no format-instruction text needed in-prompt) | Higher (format instructions + potential repair call) |
| Schema enforcement | Strong (provider-level constraint) | Weaker (prompt-level instruction only) |
| Provider/model support | Requires tool/function-calling capability | Universal — any text-completion model |
| Failure mode | Opaque provider-side error | Inspectable Python `ValidationError` |
| Recoverability | None built-in — caller must retry or fall back | Built-in one-shot self-healing via `OutputFixingParser` |

## Why Sentinel uses both

`get_structured_response_with_fallback` tries native first and only pays the
fallback's latency/token cost when native fails — e.g. if a model is
swapped for one without tool-calling support, or a specific request hits an
edge case the provider's constrained decoding doesn't handle cleanly. This
mirrors a broader production pattern worth naming explicitly: **prefer the
faster, stricter path; degrade gracefully to the slower, more forgiving path;
never let a parsing failure become a user-facing 500 if a recoverable
alternative exists.**