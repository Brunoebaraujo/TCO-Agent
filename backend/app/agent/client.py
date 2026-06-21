"""
Cliente Claude API — encapsula a chamada ao agente TCO, incluindo o ciclo
de tool use (function calling) para consultar dados reais da base.
"""
from anthropic import AsyncAnthropic, APIStatusError, APIConnectionError, RateLimitError
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOLS, execute_tool

client = AsyncAnthropic(api_key=settings.anthropic_api_key)

MAX_TOOL_ROUNDS = 5  # limite de segurança contra loops de tool use

# Mensagens de erro amigáveis por tipo de falha — em português, no tom do agente,
# para que o vendedor entenda o que aconteceu sem precisar abrir o console.
_MSG_NO_CREDITS = (
    "⚠️ Os créditos da conta de API da Goodpack estão esgotados. "
    "O agente TCO está temporariamente indisponível. "
    "Por favor, avise o administrador do sistema para recarregar o saldo em console.anthropic.com."
)
_MSG_RATE_LIMIT = (
    "⚠️ Muitas requisições simultâneas no momento. "
    "Aguarde alguns segundos e tente novamente."
)
_MSG_CONNECTION = (
    "⚠️ Não foi possível conectar ao serviço de IA. "
    "Verifique a conexão com a internet e tente novamente."
)
_MSG_GENERIC = (
    "⚠️ Erro inesperado ao chamar o agente. Tente novamente em alguns instantes. "
    "Se o problema persistir, avise o administrador do sistema."
)
_MSG_TRUNCATED = (
    "⚠️ A resposta ficou maior do que o esperado e foi cortada antes de terminar "
    "(geralmente acontece quando há muitas premissas pra listar de uma vez). "
    "Pode mandar de novo — \"continue\" ou repetir o pedido — que normalmente resolve na segunda tentativa."
)


async def ask_agent(messages: list[dict], db: AsyncSession) -> str:
    """
    Envia o histórico de mensagens ao agente TCO e retorna a resposta em texto.

    Suporta tool use: se o agente pedir uma ferramenta, ela é executada
    contra o banco real (db) e o resultado é devolvido ao agente, que pode
    então pedir outra ferramenta ou responder em texto. Repete até obter
    uma resposta final em texto ou atingir MAX_TOOL_ROUNDS.

    Em caso de erro da API, retorna uma mensagem amigável em vez de
    propagar a exceção — o frontend exibe como uma mensagem normal do agente.

    messages: lista de dicts no formato [{"role": "user"|"assistant", "content": "..."}]
    """
    conversation = list(messages)

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=conversation,
                tools=TOOLS,
            )

            if response.stop_reason == "max_tokens":
                # Resposta cortada pela API antes de terminar — não confiamos no
                # texto parcial (pode ter um TCO_RESULT com categoria faltando,
                # o que o reparo heurístico do tco_parser não detectaria como erro).
                # Descartamos e pedimos pro vendedor tentar de novo.
                return _MSG_TRUNCATED

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

        # Limite de rodadas atingido sem resposta final em texto
        return "Não consegui concluir a consulta à base de conhecimento. Pode tentar reformular o pedido?"

    except APIStatusError as e:
        # Crédito esgotado: HTTP 529 ou mensagem específica da Anthropic
        body = str(e).lower()
        if e.status_code == 529 or "credit" in body or "balance" in body or "billing" in body:
            return _MSG_NO_CREDITS
        # Outros erros HTTP da API (ex: 500 do lado da Anthropic)
        return _MSG_GENERIC

    except RateLimitError:
        return _MSG_RATE_LIMIT

    except APIConnectionError:
        return _MSG_CONNECTION

    except Exception:
        return _MSG_GENERIC
