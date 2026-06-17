"""
Cliente Claude API — encapsula a chamada ao agente TCO.
"""
from anthropic import AsyncAnthropic
from app.config import settings
from app.agent.prompts import SYSTEM_PROMPT

client = AsyncAnthropic(api_key=settings.anthropic_api_key)


async def ask_agent(messages: list[dict]) -> str:
    """
    Envia o histórico de mensagens ao agente TCO e retorna a resposta em texto.

    messages: lista de dicts no formato [{"role": "user"|"assistant", "content": "..."}]
    """
    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    # A resposta pode conter múltiplos blocos; concatenamos os de texto.
    text_blocks = [block.text for block in response.content if block.type == "text"]
    return "\n".join(text_blocks)
