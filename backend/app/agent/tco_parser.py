"""
Extrai o bloco estruturado de resultado de TCO da resposta em texto do agente.

O agente é instruído (via system prompt) a emitir um bloco JSON delimitado por
<<<TCO_RESULT>>> ... <<<END_TCO_RESULT>>> quando o cálculo estiver completo.
Esta função separa esse bloco do texto conversacional, para que o frontend
possa renderizar a tabela/gráfico em vez de mostrar o JSON cru.
"""
import json
import re
from typing import Optional, Tuple

_COMPLETE_PATTERN = re.compile(
    r"<<<TCO_RESULT>>>\s*(.*?)\s*<<<END_TCO_RESULT>>>",
    re.DOTALL,
)

# Fallback: bloco aberto mas sem marcador de fechamento (resposta truncada
# por limite de tokens). Captura tudo até o final do texto.
_TRUNCATED_PATTERN = re.compile(
    r"<<<TCO_RESULT>>>\s*(.*)$",
    re.DOTALL,
)


def _try_repair_truncated_json(raw: str) -> Optional[dict]:
    """
    Tenta fechar um JSON cortado no meio, removendo a última propriedade
    incompleta e fechando as chaves/colchetes pendentes.
    Retorna None se não for recuperável.
    """
    raw = raw.strip().rstrip(",")

    # Remove a última linha se ela parecer incompleta (não termina em } , ] ou ")
    lines = raw.split("\n")
    while lines and not re.search(r'[\]}",]\s*$', lines[-1].rstrip()):
        lines.pop()
    candidate = "\n".join(lines).rstrip().rstrip(",")

    # Tenta fechar chaves/colchetes pendentes, contando o que está aberto
    open_braces = candidate.count("{") - candidate.count("}")
    open_brackets = candidate.count("[") - candidate.count("]")

    closing = ("]" * max(open_brackets, 0)) + ("}" * max(open_braces, 0))
    attempt = candidate + closing

    try:
        return json.loads(attempt)
    except json.JSONDecodeError:
        return None


def extract_tco_result(text: str) -> Tuple[str, Optional[dict]]:
    """
    Retorna (texto_sem_o_bloco, dados_estruturados_ou_None).

    Tenta, em ordem:
    1. Bloco completo e bem formado (caso normal).
    2. Bloco aberto mas truncado (limite de tokens) — tenta reparar o JSON.
    3. Nenhum bloco encontrado — retorna o texto original intacto.
    """
    match = _COMPLETE_PATTERN.search(text)
    if match:
        raw_json = match.group(1)
        try:
            data = json.loads(raw_json)
            clean_text = _COMPLETE_PATTERN.sub("", text)
            clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()
            return clean_text, data
        except json.JSONDecodeError:
            return text, None

    # Bloco truncado — tenta recuperar o que for possível
    truncated_match = _TRUNCATED_PATTERN.search(text)
    if truncated_match:
        data = _try_repair_truncated_json(truncated_match.group(1))
        if data:
            clean_text = _TRUNCATED_PATTERN.sub("", text)
            clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()
            return clean_text, data

    return text, None
