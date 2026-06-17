"""
Cliente Claude API — encapsula a chamada ao agente TCO, incluindo o ciclo
de tool use (function calling) para consultar dados reais da base.
"""
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOLS, execute_tool

client = AsyncAnthropic(api_key=settings.anthropic_api_key)

MAX_TOOL_ROUNDS = 5  # limite de segurança contra loops de tool use


async def ask_agent(messages: list[dict], db: AsyncSession) -> str:
    """
    Envia o histórico de mensagens ao agente TCO e retorna a resposta em texto.

    Suporta tool use: se o agente pedir uma ferramenta, ela é executada
    contra o banco real (db) e o resultado é devolvido ao agente, que pode
    então pedir outra ferramenta ou responder em texto. Repete até obter
    uma resposta final em texto ou atingir MAX_TOOL_ROUNDS.

    messages: lista de dicts no formato [{"role": "user"|"assistant", "content": "..."}]
    """
    conversation = list(messages)

    for _ in range(MAX_TOOL_ROUNDS):
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=conversation,
            tools=TOOLS,
        )

        if response.stop_reason != "tool_use":
            text_blocks = [block.text for block in response.content if block.type == "text"]
            return "\n".join(text_blocks)

        # O agente pediu uma ou mais ferramentas — executa cada uma contra o banco real
        conversation.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = await execute_tool(db, block.name, block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(result),
            })

        conversation.append({"role": "user", "content": tool_results})

    # Limite de rodadas atingido sem resposta final em texto — situação anômala,
    # mas devolvemos algo coerente em vez de travar o vendedor sem resposta.
    return "Não consegui concluir a consulta à base de conhecimento. Pode tentar reformular o pedido?"
