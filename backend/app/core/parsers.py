"""
Structured output parsing layer.

Two strategies for getting validated Pydantic objects out of an LLM:

1. Primary: `get_structured_response` — uses the provider's native tool/function
   calling via `.with_structured_output(Schema)`. Fast, reliable, minimal token
   overhead, but requires a tool-calling-capable model.
2. Fallback: `get_fallback_structured_response` — prompt-based JSON extraction via
   `PydanticOutputParser`, self-healing on malformed output via `OutputFixingParser`.
   Works with any text-completion model, at the cost of extra latency/tokens.

`get_structured_response_with_fallback` tries (1) and transparently falls back to
(2) on failure — this is the function the rest of the app should call.
"""

import logging
from typing import Type, TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
# from langchain.output_parsers import OutputFixingParser
from langchain_classic.output_parsers import OutputFixingParser
from pydantic import BaseModel, ValidationError


logger = logging.getLogger("sentinel.parsers")

SchemaT = TypeVar("SchemaT", bound=BaseModel)

def get_structured_response(llm: BaseChatModel, schema: Type[SchemaT], text: str) -> SchemaT:
    """
    Primary path: native structured output via provider tool/function calling.

    Requires a tool-calling-capable model (e.g. Groq's llama-3.3-70b-versatile,
    OpenAI's gpt-4o family, Anthropic's Claude 3+). LangChain's
    `with_structured_output` dispatches to whichever mechanism the bound provider
    supports — it is NOT OpenAI-specific despite many tutorials only showing OpenAI.
    """

    structured_llm = llm.with_structured_output(schema)
    result = structured_llm.invoke(
        f"Analyze the following and extract the requested structured data:\n\n{text}"
    )
    logger.info("Primary structured output succeeded foe schema=%s", schema.__name__)
    return result


def get_fallback_structured_response(llm: BaseChatModel, schema: Type[SchemaT], text: str) -> SchemaT:
    """
    Fallback path: prompt-based extraction + self-healing parser.

    Used when the primary path is unavailable (non-tool-calling model) or fails
    validation. Asks the LLM for JSON matching the schema via explicit format
    instructions embedded in the prompt, then validates with PydanticOutputParser.
    If validation fails, OutputFixingParser makes ONE additional LLM call, showing
    the model its own broken output plus the validation error, and asking it to
    fix it — this is what "self-healing" means in practice, not magic.
    """

    base_parser = PydanticOutputParser(pydantic_object=schema)
    fixing_parser = OutputFixingParser.from_llm(parser=base_parser, llm = llm)

    prompt = PromptTemplate(
        template=(
            "Analyze the following and extract the requested structured data.\n\n"
            "{text}\n\n{format_instructions}"
        ),
        input_variables=["text"],
        partial_variables={"format_instructions": base_parser.get_format_instructions()},
    )

    chain = prompt | llm
    raw_output = chain.invoke({"text": text})
    raw_text = raw_output.content if hasattr(raw_output,"content") else str(raw_output)

    try:
        result = base_parser.parse(raw_text)
        logger.info("Fallback structured output succeeded on first parse for schema=%s", schema.__name__)
        return result
    except (OutputParserException, ValidationError) as exc:
        logger.warning(
            "Fallback path: initial parse failed (%s) - invoking OutputFixingParser to repair", exc
        )
        result = fixing_parser.parse(raw_text)
        logger.info("OutputFixingParser repaired output for schema=%s", schema.__name__)
        return result


def get_structured_response_with_fallback(llm: BaseChatModel, schema: Type[SchemaT], text: str) -> SchemaT:
    """
    Public entry point: try native structured output first, fall back to the
    prompt-based + self-healing path on any failure. This is the function the rest
    of the app (later: triage node, diagnosis node) should call — callers should
    not need to know or care which strategy actually served the request.
    """
    try:
        return get_structured_response(llm, schema, text)
    except Exception as exc:
        logger.warning(
            "Primary structured output path failed (%s) - falling back to PydanticOutputParser path",
            exc,
        )
        return get_fallback_structured_response(llm, schema, text)


